# Subway Surfers — Motion Controller

  ## Architecture

  Phone (Flutter Android) ──[WebSocket/WiFi]──► PC (Python)
    Camera → JPEG frames                        Pose Detection (MediaPipe)
    UI: login, connect, prepare, game           Pygame game engine
                                                SQLite users DB

  ## Setup

  ### PC (server)
  ```bash
  cd server
  pip install -r requirements.txt
  python main.py
  The game window opens showing a 6-digit pair code.

  Phone (client — Flutter)

  Build APK:
  cd client2
  flutter pub get
  flutter build apk --debug
  Install build/app/outputs/flutter-apk/app-debug.apk on your Android phone.

  Run in browser (for testing):
  cd client2
  flutter run -d chrome

  How to play

  1. Start server/main.py on the PC.
  2. Open the app on your phone → Sign Up or Login.
  3. Enter the PC's local IP address and the 6-digit code shown on the PC screen.
  4. On the Prepare screen, stand so your full body is visible in the camera.
  5. Press START — the game begins on the PC screen!

  Gesture controls

  ┌───────────────────────┬────────────────────┐
  │        Gesture        │       Action       │
  ├───────────────────────┼────────────────────┤
  │ Lean left             │ Move left lane     │
  ├───────────────────────┼────────────────────┤
  │ Lean right            │ Move right lane    │
  ├───────────────────────┼────────────────────┤
  │ Jump                  │ Jump over barriers │
  ├───────────────────────┼────────────────────┤
  │ Crouch                │ Duck under bars    │
  ├───────────────────────┼────────────────────┤
  │ Both hands above head │ Pause              │
  └───────────────────────┴────────────────────┘

  Keyboard shortcuts (PC, testing without phone)

  ← → — change lane · ↑ — jump · ↓ — duck · P — pause · R — resume · Space — start