[app]
title = Subway Surfers Controller
package.name = subwaysurfers
package.domain = com.yourname

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

icon.filename = %(source.dir)s/icon.png

# No opencv — frame encoding uses Pillow only
requirements = python3,kivy,pillow,websockets,android

orientation = portrait

android.permissions = CAMERA,INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 26
android.ndk = 25b
android.sdk = 33
android.archs = arm64-v8a
android.allow_backup = True
android.enable_androidx = True
android.build_tools_version = 34.0.0
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 0
