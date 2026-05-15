# Subway Surfers — Motion Controller

## Architecture

```
Phone (Kivy Android) ──[WebSocket/WiFi]──► PC (Python)
  Camera → JPEG frames                    Pose Detection (MediaPipe)
  UI: login, connect, prepare, game       Pygame game engine
                                          SQLite users DB
```

## Setup

### PC (server)

```bash
cd server
pip install -r requirements.txt
python main.py
```

The game window opens showing a 6-digit pair code and QR code.

### Phone (client)

**Run directly (Python)**:
```bash
cd client
pip install -r requirements.txt
python main.py
```

**Build APK (Android)**:
```bash
cd client
pip install buildozer
buildozer android debug
```

## How to play

1. Start `server/main.py` on the PC.
2. Open the app on your phone → **Sign Up** or **Login**.
3. Enter the PC's IP address and the 6-digit code shown on screen.
4. On the Prepare screen, stand so your full body is visible in camera.
5. Press **START** — the game begins!

## Gesture controls

| Gesture | Action |
|---------|--------|
| Step / lean left | Move left lane |
| Step / lean right | Move right lane |
| Jump up | Jump |
| Crouch | Duck |
| Both hands above head | Pause |

## Keyboard shortcuts (PC, for testing without phone)

`← →` — change lane · `↑` — jump · `↓` — duck · `P` — pause · `R` — resume · `Space` — start
