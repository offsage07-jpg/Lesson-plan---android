[app]
title = NPS Lesson Planner
package.name = npslessonplanner
package.domain = org.npsschool
source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,atlas,json,html,css,ttf
version = 1.0.0
requirements = python3,kivy,pyjnius
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.api = 36
android.minapi = 24
android.ndk = 28c
android.archs = arm64-v8a
android.accept_sdk_license = True
android.enable_androidx = True
android.add_src = 
p4a.bootstrap = sdl2
p4a.branch = master
android.private_storage = True
android.allow_backup = True
android.extra_manifest_application_arguments = ./android_manifest_application_arguments.xml
log_level = 2

[buildozer]
log_level = 2
warn_on_root = 1
