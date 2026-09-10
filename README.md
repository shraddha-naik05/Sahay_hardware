# SAHAY — Software-Only MVP (for review demo)

This is a **software-only build** of SAHAY, using only your laptop's built-in webcam, mic, and speaker.
No external hardware is required to run this demo. The physical panic button, buzzer, and PIR
sensor are simulated with keyboard keys and console/speaker output, and can be swapped for the real
Arduino circuit later without changing the module logic.

## What's included
- `enroll_faces.py` — one-time script to register known visitors (family/caretakers) by capturing their face from the webcam
- `main.py` — the core dual-camera detection loop, Arduino panic listener, visitor recognition, fall detection, wellbeing check-in, and software panic fallback
- `alerts.py` — shared alert/log helper (writes to SQLite, posts to the local Flask server)
- `server.py` — Flask backend + a simple auto-refreshing web dashboard (stands in for the Caregiver Companion App for the demo)
- `templates/dashboard.html` — the dashboard page
- `arduino_panic.ino` — Arduino sketch for a physical panic button (with optional buzzer)
- `requirements.txt` — all Python dependencies

## Setup

```bash
cd sahay
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

**Terminal 1 — start the backend + dashboard:**
```bash
python server.py
```
Then open `http://localhost:5000/dashboard` in a browser — this is your live "caregiver app" view for the demo.

**Terminal 2 — enroll a known visitor (do this once, before the review):**
```bash
python enroll_faces.py
```
Follow the prompts: enter a name and relation, then it captures a few frames of your face via the webcam.
Do this for 1–2 "known" people (e.g., yourself as "team member" or a friend as "daughter").

**Terminal 2 — run the main detection loop:**
```bash
python main.py
```

## What to demo on review day
1. **Visitor recognition**: Stand in front of the webcam — enrolled face → hear *"[Name] is at the door"*. Have an unenrolled teammate step in front → hear *"Unknown person at the door"* and see it appear on the dashboard with a snapshot.
2. **Fall detection**: The fall camera is monitored continuously. Simulate a fall safely in its field of view — hear the check-in prompt, then either say "I'm fine" (cancels) or stay silent (escalates — check the dashboard for the alert). **Do not press `F`; it is no longer needed.**
3. **Panic button**: Press the physical Arduino panic button — it sends `PANIC` over serial and triggers the existing emergency alert immediately. Press `p` only as a software fallback if the Arduino is disconnected.
4. **Wellbeing check-in**: Lower the idle threshold to ~30 seconds in `main.py` (`IDLE_THRESHOLD_SECONDS`) just for the demo, step away from the camera and stay silent, and show the check-in prompt firing and the soft alert appearing on the dashboard.

## Debugging Module 2 (fall) and Module 3 (check-in) if they seem "not working"

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

**Wellbeing check-in (Module 3) — most common cause:**
- It was defaulting to a **3-hour** idle threshold, which is now set to **60 seconds for the
  demo** (`IDLE_THRESHOLD_SECONDS = 60` in `main.py`). Remember to set it back to
  `3 * 60 * 60` before your real deployment.
- Also note: **just sitting in front of the camera continuously resets the idle timer**, because
  both face and pose detection count as "activity." To actually test the check-in, you need to
  **step out of frame and stay silent** for longer than the threshold.
- Watch for `[CHECKIN DEBUG] idle_for=...s threshold=...s active_hours_ok=...` printed every
  10 seconds — this tells you exactly how close it is to firing.

If after this you still see nothing happening and no debug lines at all for a module, that means
the loop/thread for that module isn't running — check the terminal for a Python traceback near
startup.

## After the review — adding real hardware
Swap `p` key detection in `main.py` for `pyserial` reading a signal from the Arduino (panic button + buzzer +
PIR sensor). The rest of the pipeline (face recognition, fall detection, alerts, dashboard) doesn't change —
only the input/output at the edges does. This is intentional: software and hardware are decoupled.
