# NPS Lesson Planner — offline Android APK

This project preserves the original single-file Python lesson generator, original HTML/CSS/JS interface, and custom PDF engine. The Android wrapper hosts that unchanged interface in an embedded Android WebView and runs the Python server only on `127.0.0.1`.

## Included features retained from the source
- Mathematics daily lesson cards and Science monthly + day-wise 5E plans
- Single day and period generation, topic splitting, date ranges and holidays
- Editable saved plans, library, refill, add/remove day
- Teacher, period and academic session settings
- Original offline PDF rendering engine
- Local JSON database and no cloud/network API calls

## Important
The APK itself works offline. The first Android build requires the Android SDK/NDK and internet access to fetch build dependencies. Building a Kivy APK directly inside Android Termux is not a supported/reliable Buildozer host workflow. Use the included GitHub Actions workflow to build from a Git repository; Termux is used to prepare and upload the project. No paid service is required for the GitHub Actions free allowance, subject to account limits.

## Termux preparation
Copy this folder to `~/NPS_Android`, then run:

```bash
cd ~/NPS_Android
pkg install git -y
git init
git add .
git commit -m "Initial NPS Android app"
```

Create a GitHub repository, add it as `origin`, then:

```bash
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

GitHub Actions builds the APK. Open the repository's Actions tab, open the successful `Build NPS Lesson Planner APK` run, and download the `nps-lesson-planner-debug-apk` artifact. Extract the APK on your phone and install it.

## Preserve existing Termux lesson data
Before the first build, if you already have the old database in Termux, copy it into the project so it is bundled into the APK:

```bash
mkdir -p ~/NPS_Android/assets
cp ~/.nps_lesson_planner/data.json ~/NPS_Android/assets/nps_seed_data.json
```

If the file does not exist, the project includes an empty starter database. The app copies this seed to its private app database on first launch. Later data is stored inside the Android app's private storage.

## Notes
- PDF exports are written to Android `Download/NPS_Lesson_Plans` using MediaStore.
- The app's Python HTTP server binds only to `127.0.0.1`.
- The HTML UI remains the original source UI; it is not redesigned in Kivy widgets.
