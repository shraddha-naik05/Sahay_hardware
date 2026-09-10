"""
Core SAHAY detection loop — software-only version for the review demo.
Runs visitor recognition, fall detection, a passive wellbeing check-in,
and listens for a simulated panic-button keypress ('p'), all using the
laptop's built-in webcam, mic (via TTS/STT), and speaker.

After the review, the panic-button block can be swapped for a pyserial
read from the real Arduino circuit without touching anything else.
"""

import cv2
import face_recognition
import mediapipe as mp
import numpy as np
import pickle
import sqlite3
import threading
import time
import pyttsx3

from pynput import keyboard
from alerts import init_db, log_event, escalate_emergency, DB_PATH

from fall_detector import FallDetector
from fall_response import wait_for_response
# ---------- Config (tune these before the review demo) ----------
CAM_INDEX = 0
PROCESS_EVERY_N_FRAMES = 5
FACE_MATCH_TOLERANCE = 0.6
FALL_DROP_RATIO = 0.5          # hip drop > 50% of body height within FALL_WINDOW_SECONDS
FALL_WINDOW_SECONDS = 1.0
FALL_GRACE_PERIOD_SECONDS = 15
IDLE_THRESHOLD_SECONDS = 60             # DEMO VALUE (60s). Set to 3*60*60 (3 hrs) for real use.
ACTIVE_HOURS = (0, 24)                   # DEMO VALUE (always active). Set to (7, 22) for real use.
DEBUG = True                             # prints extra diagnostics for fall/check-in — set False later
# ------------------------------------------------------------------

tts_lock = threading.Lock()


def speak(text: str):
    """
    Thread-safe TTS. IMPORTANT: pyttsx3 is not reliably thread-safe when a
    single shared engine is reused across threads (fall detection and the
    wellbeing check-in each run in their own thread) — on many systems this
    silently does nothing or throws 'run loop already started'. Creating a
    fresh engine instance per call and fully tearing it down afterward is
    slightly slower but far more reliable across platforms.
    """
    with tts_lock:
        print(f"[SPEAKER] {text}")
        try:
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"[SPEAKER ERROR] TTS failed: {e}")


# ---------- Shared state ----------
last_activity_time = time.time()
activity_lock = threading.Lock()


def mark_activity():
    global last_activity_time
    with activity_lock:
        last_activity_time = time.time()


def wait_for_response(timeout_seconds: float) -> bool:
    """Wait for a console confirmation during the fall grace period."""
    response = []
    finished = threading.Event()

    def listen_for_response():
        try:
            answer = input("Type 'I'm fine' if you are okay: ")
            response.append(answer.strip().lower())
        except (EOFError, OSError):
            pass
        finally:
            finished.set()

    threading.Thread(target=listen_for_response, daemon=True).start()
    finished.wait(timeout_seconds)
    return bool(response and response[0] in {"i'm fine", "im fine", "fine", "okay", "ok"})


# ---------- Module 1: Visitor & Intrusion Recognition ----------
def load_known_faces():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, relation, encoding FROM known_faces")
    rows = c.fetchall()
    conn.close()
    names, relations, encodings = [], [], []
    for name, relation, enc_blob in rows:
        names.append(name)
        relations.append(relation)
        encodings.append(pickle.loads(enc_blob))
    return names, relations, encodings


class VisitorRecognizer:
    def __init__(self):
        self.names, self.relations, self.encodings = load_known_faces()
        self.last_announced = {}   # name -> timestamp, to avoid repeating every frame
        self.cooldown = 15         # seconds before re-announcing the same person

    def process(self, rgb_frame):
        locations = face_recognition.face_locations(rgb_frame)
        if not locations:
            return
        mark_activity()
        encodings = face_recognition.face_encodings(rgb_frame, locations)

        for enc in encodings:
            if self.encodings:
                matches = face_recognition.compare_faces(self.encodings, enc, tolerance=FACE_MATCH_TOLERANCE)
                distances = face_recognition.face_distance(self.encodings, enc)
                best_idx = int(np.argmin(distances)) if len(distances) else None
            else:
                matches = []
                best_idx = None

            now = time.time()
            if best_idx is not None and matches[best_idx]:
                name = self.names[best_idx]
                relation = self.relations[best_idx]
                if now - self.last_announced.get(name, 0) > self.cooldown:
                    speak(f"Your {relation}, {name}, is at the door.")
                    log_event("visitor", f"{name} ({relation}) recognized at the door", severity="info")
                    self.last_announced[name] = now
            else:
                if now - self.last_announced.get("__unknown__", 0) > self.cooldown:
                    speak("Unknown person at the door.")
                    log_event("visitor", "Unknown person detected at the door", severity="soft")
                    self.last_announced["__unknown__"] = now


# ---------- Module 2: Fall & Emergency Detection ----------
class FallDetector:
    def __init__(self):
        self.pose = mp.solutions.pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.hip_history = []   # list of (timestamp, normalized_hip_y, frame_height_estimate)
        self.fall_in_progress = False

    def process(self, rgb_frame, frame_height):
        results = self.pose.process(rgb_frame)
        if not results.pose_landmarks:
            if DEBUG:
                print("[FALL DEBUG] No pose landmarks detected this frame "
                      "(make sure your head+shoulders+torso are visible and well-lit).")
            return

        mark_activity()
        landmarks = results.pose_landmarks.landmark
        left_hip = landmarks[mp.solutions.pose.PoseLandmark.LEFT_HIP]
        right_hip = landmarks[mp.solutions.pose.PoseLandmark.RIGHT_HIP]
        left_shoulder = landmarks[mp.solutions.pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = landmarks[mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER]

        hip_y = (left_hip.y + right_hip.y) / 2
        shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
        now = time.time()

        self.hip_history.append((now, hip_y))
        self.hip_history = [(t, y) for t, y in self.hip_history if now - t <= FALL_WINDOW_SECONDS]

        if self.fall_in_progress:
            return

        if len(self.hip_history) >= 2:
            oldest_y = self.hip_history[0][1]
            drop = hip_y - oldest_y   # normalized coords: larger y = lower in frame
            body_span = abs(shoulder_y - hip_y) + 1e-6
            torso_horizontal = abs(shoulder_y - hip_y) < 0.08  # shoulders/hips roughly level = lying down

            if DEBUG:
                print(f"[FALL DEBUG] drop={drop:.3f} threshold={FALL_DROP_RATIO * body_span:.3f} "
                      f"torso_horizontal={torso_horizontal}")

            if drop > FALL_DROP_RATIO * body_span and torso_horizontal:
                print("[FALL DETECTED] Triggering fall handler.")
                self.fall_in_progress = True
                threading.Thread(target=self.handle_fall, daemon=True).start()

    def handle_fall(self):
        try:
            speak(
                "I detected a fall. "
                "Are you okay? "
                "Please say I'm fine if you are okay."
            )

            log_event(
                "fall",
                "Fall detected — waiting for resident response",
                severity="soft"
            )

            safe = wait_for_response(
                timeout_seconds=FALL_GRACE_PERIOD_SECONDS
            )

            if safe:
                speak(
                    "Okay. I will not send an emergency alert."
                )

                log_event(
                    "fall",
                    "Resident confirmed they are okay.",
                    severity="info"
                )
            else:
                speak(
                    "No response received. "
                    "Alerting your caregiver now."
                )

                escalate_emergency(
                    "Possible fall detected. "
                    "No response received from the resident."
                )

        except Exception as e:
            print(f"[FALL HANDLER ERROR] {e}")
        finally:
            self.fall_in_progress = False


# ---------- Module 3: Passive Wellbeing Check-in ----------
def wellbeing_checkin_loop():
    while True:
        time.sleep(10)  # check every 10s for the demo; production would check less often
        with activity_lock:
            idle_for = time.time() - last_activity_time

        hour = time.localtime().tm_hour
        within_active_hours = ACTIVE_HOURS[0] <= hour < ACTIVE_HOURS[1]

        if DEBUG:
            print(f"[CHECKIN DEBUG] idle_for={idle_for:.0f}s "
                  f"threshold={IDLE_THRESHOLD_SECONDS}s active_hours_ok={within_active_hours}")

        if idle_for > IDLE_THRESHOLD_SECONDS and within_active_hours:
            speak("Are you there? Please say something or move in front of the camera.")
            log_event("checkin", f"No activity for {int(idle_for)}s — check-in triggered", severity="soft")

            response_window_start = time.time()
            responded = False
            while time.time() - response_window_start < 120:  # 2 minute grace period
                time.sleep(2)
                with activity_lock:
                    if last_activity_time > response_window_start:
                        responded = True
                        break

            if not responded:
                escalate_emergency("No response to wellbeing check-in — notifying caregiver.")
            else:
                log_event("checkin", "Resident responded to check-in", severity="info")
                mark_activity()


# ---------- Panic Button (simulated with 'p' keypress; swap for Arduino serial later) ----------
def on_key_press(key):
    try:
        if key.char == 'p':
            speak("Panic button pressed. Alerting your caregiver immediately.")
            escalate_emergency("Panic button pressed by resident.")
    except AttributeError:
        pass


def start_panic_listener():
    listener = keyboard.Listener(on_press=on_key_press)
    listener.start()
    return listener


# ---------- Main loop ----------
def main():
    init_db()
    print("Starting SAHAY software-only demo. Press 'p' anytime to simulate the panic button.")
    print("Press 'q' in the camera window to quit.")

    start_panic_listener()
    threading.Thread(target=wellbeing_checkin_loop, daemon=True).start()

    visitor_recognizer = VisitorRecognizer()
    fall_detector = FallDetector()

    cap = cv2.VideoCapture(CAM_INDEX)
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Webcam not available.")
            break

        frame_count += 1
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Fall detection needs to run on (close to) every frame for reliable timing
        # FallDetector handles fall responses internally.
        fall_detector.process(rgb, frame.shape[0])

        # Face recognition is heavier — run every Nth frame to keep things smooth
        if frame_count % PROCESS_EVERY_N_FRAMES == 0:
            visitor_recognizer.process(rgb)

        cv2.imshow("SAHAY (demo view — resident does not need to see this)", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
