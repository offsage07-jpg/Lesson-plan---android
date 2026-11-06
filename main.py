# -*- coding: utf-8 -*-
"""
NPS Lesson Planner Android wrapper.
The original HTML/CSS/JS interface and Python lesson/PDF engines are retained.
A local-only HTTP server feeds the original interface into Android WebView.
"""
import os
import threading
import shutil
from urllib.parse import urlparse, unquote

from kivy.app import App
from kivy.clock import Clock
from kivy.utils import platform

import nps_lesson_planner as engine
os.environ["NPS_ANDROID_APP"] = "1"

PORT = 8765
SERVER = None
WEBVIEW = None


def _android_export_pdf(path, open_after=False):
    """Copy a generated PDF to public Downloads through MediaStore (Android 10+)."""
    if platform != "android":
        return path
    from jnius import autoclass
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    activity = PythonActivity.mActivity
    ContentValues = autoclass("android.content.ContentValues")
    MediaStoreDownloads = autoclass("android.provider.MediaStore$Downloads")
    Environment = autoclass("android.os.Environment")
    Intent = autoclass("android.content.Intent")
    Uri = autoclass("android.net.Uri")
    FileInputStream = autoclass("java.io.FileInputStream")
    BufferedInputStream = autoclass("java.io.BufferedInputStream")
    ByteArrayOutputStream = autoclass("java.io.ByteArrayOutputStream")

    name = os.path.basename(path)
    resolver = activity.getContentResolver()
    values = ContentValues()
    values.put("_display_name", name)
    values.put("mime_type", "application/pdf")
    values.put("relative_path", "Download/NPS_Lesson_Plans")
    values.put("is_pending", 1)
    collection = MediaStoreDownloads.EXTERNAL_CONTENT_URI
    uri = resolver.insert(collection, values)
    if uri is None:
        raise RuntimeError("Android could not create the PDF in Downloads")

    stream = resolver.openOutputStream(uri)
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                # Convert Python bytes to Java byte[].
                stream.write(chunk)
        stream.flush()
    finally:
        stream.close()

    done = ContentValues()
    done.put("is_pending", 0)
    resolver.update(uri, done, None, None)

    if open_after:
        intent = Intent(Intent.ACTION_VIEW)
        intent.setDataAndType(uri, "application/pdf")
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        activity.startActivity(intent)
    return str(uri.toString())


# The existing server's /api/open route calls this hook on Android.
engine._android_export_pdf = _android_export_pdf


def _prepare_data():
    """Seed the app's private database from the optional Termux export."""
    target = engine.DB_PATH
    if os.path.exists(target):
        return
    candidates = [
        os.path.join(os.path.dirname(__file__), "nps_seed_data.json"),
        os.path.join(os.path.dirname(__file__), "assets", "nps_seed_data.json"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(candidate, target)
            return


def _start_server():
    global SERVER
    if SERVER is not None:
        return
    _prepare_data()
    SERVER = engine.ThreadingHTTPServer(("127.0.0.1", PORT), engine.Handler)
    SERVER.daemon_threads = True
    threading.Thread(target=SERVER.serve_forever, daemon=True,
                     name="NPS-local-server").start()


def _open_native_webview():
    """Place a native Android WebView over the Kivy surface, preserving the UI."""
    from jnius import autoclass, PythonJavaClass, java_method
    from android.runnable import run_on_ui_thread

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    WebView = autoclass("android.webkit.WebView")
    WebViewClient = autoclass("android.webkit.WebViewClient")
    FrameLayout = autoclass("android.widget.FrameLayout")
    ViewGroup = autoclass("android.view.ViewGroup")
    LayoutParams = autoclass("android.view.ViewGroup$LayoutParams")
    AndroidView = autoclass("android.view.View")
    BuildVersion = autoclass("android.os.Build$VERSION")
    activity = PythonActivity.mActivity

    class PdfDownloadListener(PythonJavaClass):
        __javainterfaces__ = ["android/webkit/DownloadListener"]
        __javacontext__ = "app"

        @java_method("(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;J)V")
        def onDownloadStart(self, url, user_agent, content_disposition, mimetype, content_length):
            parsed = urlparse(str(url))
            name = unquote(parsed.path.rsplit("/", 1)[-1])
            path = engine.find_pdf(name)
            if path:
                try:
                    _android_export_pdf(path, open_after=False)
                except Exception as exc:
                    print("NPS PDF export failed:", exc)

    @run_on_ui_thread
    def install():
        global WEBVIEW
        content_id = autoclass("android.R$id").content
        content = activity.findViewById(content_id)
        webview = WebView(activity)
        webview.getSettings().setJavaScriptEnabled(True)
        webview.getSettings().setDomStorageEnabled(True)
        webview.getSettings().setAllowFileAccess(False)
        webview.setWebViewClient(WebViewClient())
        webview.setDownloadListener(PdfDownloadListener())
        if int(BuildVersion.SDK_INT) >= 21:
            webview.getSettings().setMixedContentMode(0)
        # Keep the original Kivy view attached underneath the WebView. This
        # avoids replacing the activity's SDL surface while retaining the
        # original app's exact HTML/CSS/JS presentation.
        frame = FrameLayout(activity)
        old = content.getChildAt(0)
        if old is not None:
            content.removeView(old)
            frame.addView(old, FrameLayout.LayoutParams(
                LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT))
        frame.addView(webview, FrameLayout.LayoutParams(
            LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT))
        content.addView(frame, LayoutParams(
            LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT))
        webview.bringToFront()
        WEBVIEW = webview
        webview.loadUrl("http://127.0.0.1:%d/" % PORT)

    install()


class NPSAndroidApp(App):
    title = "NPS Lesson Planner"

    def build(self):
        # The Kivy surface remains as the host activity's underlying view.
        from kivy.uix.widget import Widget
        return Widget()

    def on_start(self):
        _start_server()
        if platform == "android":
            Clock.schedule_once(lambda _dt: _open_native_webview(), 0.8)
        else:
            print("Android packaging entry point. For desktop testing, run:")
            print("python nps_lesson_planner.py --no-open")

    def on_stop(self):
        global SERVER
        if SERVER is not None:
            try:
                SERVER.shutdown()
                SERVER.server_close()
            except Exception:
                pass
            SERVER = None


if __name__ == "__main__":
    NPSAndroidApp().run()
