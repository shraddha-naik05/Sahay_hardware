# SAHAY — Software-Only MVP (for review demo)

SAHAY is an AI-powered safety and monitoring system that integrates dual cameras, face recognition, fall detection, wellbeing check-ins, and a physical Arduino panic button. It provides real-time alerts, visitor logging, and emergency notifications through a Flask dashboard, Telegram, and voice output.

🚀 Features
👀 Dual Camera Integration — one camera for visitor recognition, another for fall detection
🧑‍💻 Face Enrollment & Recognition — register known visitors and detect unknown persons
⚡ Fall Detection — detects accidents using MediaPipe Pose and triggers alerts
🔴 Arduino Panic Button — hardware-triggered emergency response with buzzer support
📲 Telegram Notifications — instant caregiver alerts with snapshots
🔊 Text-to-Speech (TTS) — voice feedback for accessibility

## What's included
-enroll_faces.py — register known visitors via webcam
- `main.py` — dual-camera detection loop, Arduino panic listener, visitor recognition, fall detection, wellbeing check-in
- `alerts.py` — shared alert/log helper (writes to SQLite, posts to the local Flask server)
- `server.py` — Flask backend + a simple auto-refreshing web dashboard (stands in for the Caregiver Companion App for the demo)
- `templates/dashboard.html` — the dashboard page
- `arduino_panic.ino` — Arduino sketch for a physical panic button (with optional buzzer)
- tts.py — text-to-speech helper
- `requirements.txt` — all Python dependencies

## Setup

```bash
cd SAHAY_dual_camera_hardware_integrated
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Camera and Arduino configuration

Set these values in `.env`:

```env
VISITOR_CAMERA_INDEX=0
FALL_CAMERA_INDEX=1
ARDUINO_ENABLED=true
ARDUINO_PORT=COM3
ARDUINO_BAUD_RATE=115200
```

If Windows assigns different camera indexes or a different Arduino COM port, change them accordingly.
To find the camera indexes, you can temporarily test OpenCV indexes `0`, `1`, `2`, etc.

The Arduino sends one line, `PANIC`, whenever the physical button is pressed. SAHAY then calls the
existing `handle_panic()` function, so the Telegram/database/dashboard panic workflow is unchanged.

**Note on `face_recognition`/`dlib`:** if `pip install dlib` fails on Windows, install
[CMake](https://cmake.org/download/) and Visual Studio Build Tools first, or use
`pip install face_recognition_models` alternatives — this is the one library that occasionally
needs extra setup. If you're short on time before the review, `pip install cmake dlib` (in that
order) inside the venv usually resolves it on both Windows and Linux/Mac.

## Running the demo

**Terminal 1 — enroll a known visitor (do this once, before the review):**
```bash
python enroll_faces.py
```
Follow the prompts: enter a name and relation, then it captures a few frames of your face via the webcam.
Do this for 1–2 "known" people (e.g., yourself as "team member" or a friend as "daughter").

**Terminal 1 — run the main detection loop:**
```bash
python main.py
```

## Demo Scenarios
-Visitor Recognition — enrolled faces trigger name alerts; unknown faces trigger “Unknown person” alerts with snapshots.
-Fall Detection — simulate a safe fall in camera view; system prompts check-in, escalates if silent.
-Panic Button — press Arduino panic button → immediate emergency alert. Use p key only as fallback.
-Wellbeing Check-in — idle threshold (default 60s for demo) triggers soft alerts if no activity is detected.

## Debugging Module 2 (fall) if it seem "not working"

`DEBUG = True` is on by default in `main.py` — watch the terminal running `main.py` closely,
it now prints diagnostics every frame/check so you can see exactly what's happening.

**Fall detection (Module 2) — most common causes:**
1. **Your full torso isn't in frame.** A laptop webcam pointed at your face while you sit close
   to it usually only sees head/shoulders, not hips — MediaPipe Pose then either finds no
   landmarks (`[FALL DEBUG] No pose landmarks detected`) or estimates hip position poorly, so
   the fall condition never becomes true. **Sit or stand further back so your hips are visible**,
   or point the webcam across the room, to test this properly.
2. Watch for `[FALL DEBUG] drop=... threshold=... torso_horizontal=...` lines — if `drop` never
   gets close to `threshold`, or `torso_horizontal` never becomes `True`, that confirms it's a
   framing/threshold issue, not a crash. Try an exaggerated, safe "fall" (sit down fast onto a
   mat) fully in frame to trigger it.
3. If you instead see `[FALL HANDLER ERROR] ...` with a traceback, that's a real code
   exception (often `pyttsx3` on some systems) — that traceback tells us exactly what to fix.


