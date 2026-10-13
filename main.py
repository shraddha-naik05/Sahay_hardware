
"""
SAHAY - Smart AI Safety Assistant for Visually Impaired

Integrated dual-camera + hardware demonstration.

CAMERAS
-------
1. VISITOR CAMERA
   - Dedicated camera for face recognition at the entry/door.

2. FALL CAMERA
   - Dedicated camera for MediaPipe pose/fall detection.
   - Fall detection runs continuously; F is no longer required.

PANIC
-----
- Physical Arduino button sends "PANIC" over USB serial.
- P remains as a software fallback.

QUIT
----
- Press Q in a camera window.
"""

import os
import cv2
import time
import threading
import pyttsx3

try:
    import serial
except ImportError:
    serial = None

from dotenv import load_dotenv
from pynput import keyboard

from database import (
    init_db,
    log_activity,
    create_alert
)

from face_service import VisitorRecognizer
from fall_detector import FallDetector
from fall_response import wait_for_response

from notifications import (
    send_telegram_message,
    send_telegram_photo
)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

# Two independent cameras:
#   VISITOR_CAMERA_INDEX -> camera facing the main door/entry
#   FALL_CAMERA_INDEX    -> camera covering the resident's body
VISITOR_CAMERA_INDEX = int(
    os.getenv("VISITOR_CAMERA_INDEX", "0")
)

FALL_CAMERA_INDEX = int(
    os.getenv("FALL_CAMERA_INDEX", "1")
)

# Arduino hardware interface. The Arduino should send the line
# "PANIC" over USB serial when the physical panic button is pressed.
ARDUINO_ENABLED = (
    os.getenv("ARDUINO_ENABLED", "true").lower() == "true"
)
ARDUINO_PORT = os.getenv("ARDUINO_PORT", "COM3")
ARDUINO_BAUD_RATE = int(os.getenv("ARDUINO_BAUD_RATE", "115200"))

# Visitor recognition frequency
FACE_PROCESS_INTERVAL = int(
    os.getenv(
        "FACE_PROCESS_INTERVAL",
        "5"
    )
)

VISITOR_COOLDOWN_SECONDS = int(
    os.getenv(
        "VISITOR_COOLDOWN_SECONDS",
        "15"
    )
)

# Fall response
FALL_RESPONSE_TIMEOUT = int(
    os.getenv(
        "FALL_RESPONSE_TIMEOUT",
        "15"
    )
)

# Fall detection processing frequency
FALL_PROCESS_INTERVAL = int(
    os.getenv(
        "FALL_PROCESS_INTERVAL",
        "2"
    )
)

# Wellbeing
WELLBEING_ENABLED = (
    os.getenv(
        "WELLBEING_ENABLED",
        "true"
    ).lower() == "true"
)

WELLBEING_TIMEOUT_MINUTES = int(
    os.getenv(
        "WELLBEING_TIMEOUT_MINUTES",
        "30"
    )
)

WELLBEING_TIMEOUT_SECONDS = (
    WELLBEING_TIMEOUT_MINUTES * 60
)

WELLBEING_ACTIVE_START = os.getenv(
    "WELLBEING_ACTIVE_START",
    "07:00"
)

WELLBEING_ACTIVE_END = os.getenv(
    "WELLBEING_ACTIVE_END",
    "22:00"
)

WELLBEING_CHECK_INTERVAL = 10

# Snapshots
SNAPSHOT_DIR = "snapshots"

os.makedirs(
    SNAPSHOT_DIR,
    exist_ok=True
)

DEBUG = True


# ============================================================
# GLOBAL MODE
# ============================================================

VISITOR_MODE = "VISITOR"
FALL_MODE = "FALL"
DUAL_MODE = "DUAL"

# With dedicated cameras, both modules run continuously.
current_mode = DUAL_MODE

mode_lock = threading.Lock()


def get_current_mode():

    with mode_lock:

        return current_mode


def set_mode(mode):

    global current_mode

    with mode_lock:

        current_mode = mode

    print()
    print(
        "========================================"
    )

    print(
        f"          MODE -> {mode}"
    )

    print(
        "========================================"
    )

    print()


# ============================================================
# TEXT TO SPEECH
# ============================================================

tts_lock = threading.Lock()


def speak(text):

    with tts_lock:

        print(
            f"[SPEAKER] {text}"
        )

        try:

            engine = pyttsx3.init()

            engine.setProperty(
                "rate",
                150
            )

            engine.setProperty(
                "volume",
                1.0
            )

            engine.say(text)

            engine.runAndWait()

            engine.stop()

        except Exception as e:

            print(
                f"[SPEAKER ERROR] {e}"
            )


# ============================================================
# SHARED ACTIVITY STATE
# ============================================================

last_activity_time = time.time()

activity_lock = threading.Lock()


def mark_activity():

    global last_activity_time

    with activity_lock:

        last_activity_time = time.time()


def get_idle_time():

    with activity_lock:

        return (
            time.time()
            - last_activity_time
        )


# ============================================================
# SNAPSHOT
# ============================================================

def save_snapshot(
    frame,
    event_type
):

    if frame is None:

        print(
            "[SNAPSHOT ERROR] "
            "Frame is None."
        )

        return None

    try:

        frame_to_save = frame.copy()

        timestamp = time.strftime(
            "%Y%m%d_%H%M%S"
        )

        milliseconds = int(
            (time.time() % 1) * 1000
        )

        filename = (
            f"{event_type}_"
            f"{timestamp}_"
            f"{milliseconds:03d}.jpg"
        )

        path = os.path.abspath(
            os.path.join(
                SNAPSHOT_DIR,
                filename
            )
        )

        success = cv2.imwrite(
            path,
            frame_to_save
        )

        if success and os.path.exists(path):

            print(
                "[SNAPSHOT] Saved successfully:"
            )

            print(
                f"           {path}"
            )

            return path

        print(
            "[SNAPSHOT ERROR] "
            "Could not save image."
        )

        return None

    except Exception as e:

        print(
            "[SNAPSHOT ERROR] "
            f"{e}"
        )

        return None


# ============================================================
# UNKNOWN VISITOR TELEGRAM
# ============================================================

def send_unknown_visitor_telegram(
    snapshot,
    timestamp
):

    print()
    print(
        "========================================"
    )

    print(
        "      UNKNOWN VISITOR TELEGRAM"
    )

    print(
        "========================================"
    )

    try:

        message = (
            "SAHAY SECURITY ALERT\n\n"
            "Unknown person detected "
            "at the door.\n\n"
            f"Time: {timestamp}\n"
            "Zone: Main Door\n"
            "Status: UNKNOWN VISITOR"
        )

        # ----------------------------------------------------
        # TEXT
        # ----------------------------------------------------

        result = send_telegram_message(
            message
        )

        print(
            f"[TELEGRAM] Message result: "
            f"{result}"
        )

        # ----------------------------------------------------
        # PHOTO
        # ----------------------------------------------------

        if snapshot is None:

            print(
                "[TELEGRAM] "
                "No snapshot available."
            )

            return

        if not os.path.exists(snapshot):

            print(
                "[TELEGRAM] "
                f"Snapshot not found: {snapshot}"
            )

            return

        print(
            "[TELEGRAM] "
            "Sending unknown visitor photo..."
        )

        photo_result = send_telegram_photo(
            snapshot,
            (
                "SAHAY SECURITY ALERT\n"
                "Unknown visitor detected "
                "at Main Door."
            )
        )

        print(
            f"[TELEGRAM] Photo result: "
            f"{photo_result}"
        )

        if photo_result:

            print(
                "[TELEGRAM] "
                "Unknown visitor photo sent successfully."
            )

        else:

            print(
                "[TELEGRAM ERROR] "
                "Could not send visitor photo."
            )

    except Exception as e:

        print(
            "[TELEGRAM UNKNOWN ERROR]"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

    print(
        "========================================"
    )


# ============================================================
# VISITOR HANDLER
# ============================================================

class VisitorEventHandler:

    def __init__(self):

        print(
            "[VISITOR] Initializing "
            "ArcFace visitor recognizer..."
        )

        self.recognizer = (
            VisitorRecognizer()
        )

        self.last_announced = {}

        self.cooldown = (
            VISITOR_COOLDOWN_SECONDS
        )

        print(
            "[VISITOR] Recognizer ready."
        )


    def process(self, frame):

        # ----------------------------------------------------
        # Safety check
        # ----------------------------------------------------

        if get_current_mode() not in (VISITOR_MODE, DUAL_MODE):

            return


        try:

            results = (
                self.recognizer.recognize(
                    frame
                )
            )

        except Exception as e:

            print(
                "[VISITOR ERROR] "
                f"{e}"
            )

            return


        if not results:

            return

        # A detected person counts as activity for wellbeing monitoring.
        mark_activity()

        now = time.time()


        for result in results:

            # =================================================
            # KNOWN PERSON
            # =================================================

            if result["known"]:

                name = (
                    result.get("name")
                    or "Known visitor"
                )

                relation = (
                    result.get("relation")
                    or ""
                )

                score = (
                    result.get("score", 0)
                )

                event_key = (
                    f"known_{name}"
                )


                if (
                    now
                    - self.last_announced.get(
                        event_key,
                        0
                    )
                    < self.cooldown
                ):

                    continue


                print()
                print(
                    "[VISITOR] Known visitor:"
                )

                print(
                    f"           Name: {name}"
                )

                print(
                    f"           Relation: {relation}"
                )

                print(
                    f"           Score: {score:.3f}"
                )


                if relation:

                    speak(
                        f"Your {relation}, "
                        f"{name}, is at the door."
                    )

                else:

                    speak(
                        f"{name} "
                        f"is at the door."
                    )


                log_activity(
                    "visitor",
                    "Main Door",
                    (
                        f"{name} "
                        f"({relation}) recognized. "
                        f"Face score: {score:.3f}"
                    )
                )


                self.last_announced[
                    event_key
                ] = now


            # =================================================
            # UNKNOWN PERSON
            # =================================================

            else:

                event_key = "unknown"


                if (
                    now
                    - self.last_announced.get(
                        event_key,
                        0
                    )
                    < self.cooldown
                ):

                    continue


                print()
                print(
                    "========================================"
                )

                print(
                    "       UNKNOWN VISITOR DETECTED"
                )

                print(
                    "========================================"
                )


                speak(
                    "Unknown person "
                    "at the door."
                )


                # ------------------------------------------------
                # SAVE SNAPSHOT
                # ------------------------------------------------

                snapshot = save_snapshot(
                    frame.copy(),
                    "unknown_visitor"
                )


                # ------------------------------------------------
                # DATABASE
                # ------------------------------------------------

                create_alert(
                    "visitor",
                    (
                        "Unknown person "
                        "detected at the door."
                    ),
                    severity="MEDIUM",
                    snapshot=snapshot
                )


                log_activity(
                    "visitor",
                    "Main Door",
                    "Unknown person detected."
                )


                # ------------------------------------------------
                # TELEGRAM
                # ------------------------------------------------

                timestamp = time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )


                threading.Thread(
                    target=send_unknown_visitor_telegram,
                    args=(
                        snapshot,
                        timestamp
                    ),
                    daemon=True
                ).start()


                self.last_announced[
                    event_key
                ] = now


# ============================================================
# FALL HANDLER
# ============================================================

class FallEventHandler:

    def __init__(self):

        print(
            "[FALL] Initializing "
            "MediaPipe fall detector..."
        )

        self.detector = (
            FallDetector()
        )

        self.processing_lock = (
            threading.Lock()
        )

        self.emergency_in_progress = False

        print(
            "[FALL] Fall detector ready."
        )


    # ========================================================
    # FALL MONITORING
    # ========================================================

    def process(
        self,
        rgb_frame,
        bgr_frame
    ):

        # ----------------------------------------------------
        # Only process MediaPipe while in FALL MODE.
        # ----------------------------------------------------

        if get_current_mode() not in (FALL_MODE, DUAL_MODE):

            return


        # ----------------------------------------------------
        # Do not monitor while handling a confirmed fall.
        # ----------------------------------------------------

        with self.processing_lock:

            if self.emergency_in_progress:

                return


        try:

            fall_detected = (
                self.detector.process(
                    rgb_frame
                )
            )

        except Exception as e:

            print(
                "[FALL ERROR] "
                f"{e}"
            )

            return


        # ----------------------------------------------------
        # IMPORTANT:
        #
        # F DOES NOT MEAN FALL DETECTED.
        #
        # F only switches to FALL MODE.
        #
        # This function waits for FallDetector.process()
        # to return True.
        # ----------------------------------------------------

        if not fall_detected:

            return


        # ----------------------------------------------------
        # ACTUAL FALL CONFIRMED
        # ----------------------------------------------------

        with self.processing_lock:

            if self.emergency_in_progress:

                return

            self.emergency_in_progress = True


        print()
        print(
            "========================================"
        )

        print(
            "        ACTUAL FALL DETECTED"
        )

        print(
            "========================================"
        )


        snapshot_frame = (
            bgr_frame.copy()
        )


        threading.Thread(
            target=self.handle_fall,
            args=(snapshot_frame,),
            daemon=True
        ).start()


    # ========================================================
    # HANDLE CONFIRMED FALL
    # ========================================================

    def handle_fall(
        self,
        fall_frame
    ):

        try:

            print()
            print(
                "========================================"
            )

            print(
                "          FALL EVENT TRIGGERED"
            )

            print(
                "========================================"
            )


            # ------------------------------------------------
            # SAVE SNAPSHOT
            # ------------------------------------------------

            snapshot = save_snapshot(
                fall_frame,
                "fall"
            )


            # ------------------------------------------------
            # DATABASE
            # ------------------------------------------------

            log_activity(
                "fall",
                "Main Camera",
                (
                    "Fall detected. "
                    "Waiting for resident response."
                )
            )


            create_alert(
                "fall",
                (
                    "Possible fall detected. "
                    "Waiting for resident response."
                ),
                severity="HIGH",
                snapshot=snapshot
            )


            # ------------------------------------------------
            # TTS
            # ------------------------------------------------

            speak(
                "I detected a fall. "
                "Are you okay? "
                "Please say I'm fine "
                "if you are okay."
            )


            # ------------------------------------------------
            # STT
            # ------------------------------------------------

            print()
            print(
                "[FALL] Waiting for resident response..."
            )

            print(
                "[FALL] Say: I am fine"
            )


            safe = wait_for_response(
                timeout_seconds=(
                    FALL_RESPONSE_TIMEOUT
                )
            )


            # =================================================
            # SAFE
            # =================================================

            if safe:

                print()
                print(
                    "========================================"
                )

                print(
                    "             RESIDENT SAFE"
                )

                print(
                    "========================================"
                )


                speak(
                    "Okay. "
                    "I will not send "
                    "an emergency alert."
                )


                log_activity(
                    "fall",
                    "Main Camera",
                    (
                        "Resident confirmed "
                        "they are okay."
                    )
                )


                create_alert(
                    "fall",
                    (
                        "Resident confirmed "
                        "they are okay."
                    ),
                    severity="LOW",
                    snapshot=snapshot
                )


            # =================================================
            # EMERGENCY
            # =================================================

            else:

                print()
                print(
                    "========================================"
                )

                print(
                    "          FALL EMERGENCY"
                )

                print(
                    "========================================"
                )


                speak(
                    "No response received. "
                    "Alerting your caregiver now."
                )


                timestamp = time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )


                message = (
                    "SAHAY EMERGENCY ALERT\n\n"
                    "Possible fall detected.\n"
                    "The resident did not respond "
                    "to the safety check.\n\n"
                    f"Time: {timestamp}\n"
                    "Zone: Main Camera\n"
                    "Status: EMERGENCY"
                )


                # ------------------------------------------------
                # TELEGRAM TEXT
                # ------------------------------------------------

                print(
                    "[TELEGRAM] "
                    "Sending fall emergency message..."
                )


                result = (
                    send_telegram_message(
                        message
                    )
                )


                print(
                    f"[TELEGRAM] "
                    f"Message result: {result}"
                )


                # ------------------------------------------------
                # TELEGRAM PHOTO
                # ------------------------------------------------

                if snapshot:

                    if os.path.exists(
                        snapshot
                    ):

                        print(
                            "[TELEGRAM] "
                            "Sending fall photo..."
                        )


                        photo_result = (
                            send_telegram_photo(
                                snapshot,
                                (
                                    "SAHAY EMERGENCY\n"
                                    "Fall detected - "
                                    "no safe response."
                                )
                            )
                        )


                        print(
                            f"[TELEGRAM] "
                            f"Photo result: "
                            f"{photo_result}"
                        )


                    else:

                        print(
                            "[TELEGRAM ERROR] "
                            "Fall snapshot does not exist."
                        )


                create_alert(
                    "fall",
                    (
                        "Possible fall detected. "
                        "Resident did not respond."
                    ),
                    severity="CRITICAL",
                    snapshot=snapshot
                )


                log_activity(
                    "emergency",
                    "Main Camera",
                    (
                        "Fall detected and "
                        "resident did not respond."
                    )
                )


                print(
                    "[FALL] "
                    "Emergency notification complete."
                )


        except Exception as e:

            print(
                "[FALL HANDLER ERROR]"
            )

            print(
                f"{type(e).__name__}: {e}"
            )


        finally:

            # ------------------------------------------------
            # Reset detector state.
            #
            # This is important before returning to
            # visitor mode.
            # ------------------------------------------------

            try:

                self.detector.reset()

            except Exception as e:

                print(
                    "[FALL RESET ERROR] "
                    f"{e}"
                )


            with self.processing_lock:

                self.emergency_in_progress = False


            # ------------------------------------------------
            # Dedicated cameras mean there is no mode switch.
            # Visitor recognition continues on its own camera and
            # fall detection continues on its own camera.
            # ------------------------------------------------

            print(
                "[SYSTEM] Fall event completed."
            )

            print(
                "[SYSTEM] Both cameras remain active."
            )


    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        try:

            self.detector.close()

        except Exception as e:

            print(
                "[FALL CLEANUP ERROR] "
                f"{e}"
            )


# ============================================================
# SWITCH TO FALL MODE
# ============================================================

def activate_fall_mode(
    fall_handler
):

    if get_current_mode() == FALL_MODE:

        print(
            "[MODE] "
            "Already in FALL MODE."
        )

        return


    print()
    print(
        "========================================"
    )

    print(
        "       FALL MODE ACTIVATED"
    )

    print(
        "========================================"
    )

    print(
        "[MODE] Visitor recognition STOPPED."
    )

    print(
        "[MODE] MediaPipe fall detection STARTED."
    )

    print(
        "[MODE] Monitoring body movement..."
    )

    print(
        "[MODE] Monitoring body angle..."
    )

    print(
        "[MODE] Monitoring hip displacement..."
    )

    print(
        "[MODE] Monitoring horizontal posture..."
    )

    print(
        "========================================"
    )


    # --------------------------------------------------------
    # Reset detector before starting a new monitoring session.
    # --------------------------------------------------------

    try:

        fall_handler.detector.reset()

    except Exception as e:

        print(
            "[FALL] Reset error:"
            f" {e}"
        )


    set_mode(
        FALL_MODE
    )


# ============================================================
# PASSIVE WELLBEING
# ============================================================

def is_within_active_hours():

    now = time.localtime()

    current_minutes = (
        now.tm_hour * 60
        + now.tm_min
    )


    try:

        start_hour, start_minute = map(
            int,
            WELLBEING_ACTIVE_START.split(":")
        )

        end_hour, end_minute = map(
            int,
            WELLBEING_ACTIVE_END.split(":")
        )

    except ValueError:

        return True


    start_minutes = (
        start_hour * 60
        + start_minute
    )

    end_minutes = (
        end_hour * 60
        + end_minute
    )


    if start_minutes < end_minutes:

        return (
            start_minutes
            <= current_minutes
            < end_minutes
        )


    return (
        current_minutes >= start_minutes
        or current_minutes < end_minutes
    )


def wellbeing_checkin_loop():

    if not WELLBEING_ENABLED:

        print(
            "[CHECKIN] "
            "Wellbeing monitoring disabled."
        )

        return


    print(
        "[CHECKIN] "
        "Wellbeing monitoring started."
    )


    while True:

        try:

            time.sleep(
                WELLBEING_CHECK_INTERVAL
            )


            idle_for = get_idle_time()

            active = (
                is_within_active_hours()
            )


            if DEBUG:

                print(
                    "[CHECKIN DEBUG] "
                    f"idle_for={idle_for:.0f}s "
                    f"threshold="
                    f"{WELLBEING_TIMEOUT_SECONDS}s "
                    f"active={active}"
                )


            if (
                idle_for
                > WELLBEING_TIMEOUT_SECONDS
                and active
            ):

                print(
                    "[CHECKIN] "
                    "No activity detected."
                )


                speak(
                    "Are you there? "
                    "Please say something "
                    "or move in front "
                    "of the camera."
                )


                log_activity(
                    "checkin",
                    "Main Camera",
                    (
                        "No activity detected. "
                        "Wellbeing check triggered."
                    )
                )


                checkin_start = time.time()

                response_window = 30

                responded = False


                while (
                    time.time()
                    - checkin_start
                    < response_window
                ):

                    time.sleep(2)


                    with activity_lock:

                        if (
                            last_activity_time
                            > checkin_start
                        ):

                            responded = True

                            break


                if responded:

                    print(
                        "[CHECKIN] "
                        "Resident appears active."
                    )

                    log_activity(
                        "checkin",
                        "Main Camera",
                        (
                            "Resident responded "
                            "to wellbeing check."
                        )
                    )

                    mark_activity()


                else:

                    print(
                        "[CHECKIN] "
                        "No response received."
                    )


                    speak(
                        "I could not confirm "
                        "that you are okay. "
                        "I am notifying "
                        "your caregiver."
                    )


                    timestamp = time.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )


                    message = (
                        "SAHAY WELLBEING ALERT\n\n"
                        "No activity was detected "
                        "for an extended period.\n"
                        "The resident did not respond "
                        "to the wellbeing check.\n\n"
                        f"Time: {timestamp}\n"
                        "Status: CHECK-IN FAILED"
                    )


                    send_telegram_message(
                        message
                    )


                    create_alert(
                        "checkin",
                        (
                            "No response to "
                            "wellbeing check-in."
                        ),
                        severity="HIGH"
                    )


                    log_activity(
                        "emergency",
                        "Main Camera",
                        (
                            "No response to "
                            "wellbeing check-in."
                        )
                    )


                    mark_activity()


        except Exception as e:

            print(
                "[CHECKIN ERROR] "
                f"{e}"
            )


# ============================================================
# PANIC
# ============================================================

def handle_panic():

    print()
    print(
        "========================================"
    )

    print(
        "             PANIC BUTTON"
    )

    print(
        "========================================"
    )


    speak(
        "Panic button pressed. "
        "Alerting your caregiver "
        "immediately."
    )


    timestamp = time.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    message = (
        "SAHAY EMERGENCY ALERT\n\n"
        "Panic button was pressed "
        "by the resident.\n\n"
        f"Time: {timestamp}\n"
        "Status: IMMEDIATE EMERGENCY"
    )


    try:

        result = send_telegram_message(
            message
        )

        print(
            f"[PANIC] Telegram result: "
            f"{result}"
        )

    except Exception as e:

        print(
            "[PANIC TELEGRAM ERROR] "
            f"{e}"
        )


    create_alert(
        "panic",
        "Panic button pressed by resident.",
        severity="CRITICAL"
    )


    log_activity(
        "emergency",
        "Panic Button",
        "Panic button pressed."
    )


# ============================================================
# ARDUINO PANIC BUTTON
# ============================================================

def arduino_panic_listener(stop_event):
    """Listen for a PANIC line from the Arduino over USB serial."""

    if not ARDUINO_ENABLED:
        print("[ARDUINO] Hardware panic input disabled.")
        return

    if serial is None:
        print("[ARDUINO ERROR] pyserial is not installed. Install: pip install pyserial")
        return

    try:
        device = serial.Serial(
            ARDUINO_PORT,
            ARDUINO_BAUD_RATE,
            timeout=1
        )

        print(
            f"[ARDUINO] Connected on {ARDUINO_PORT} @ {ARDUINO_BAUD_RATE}."
        )
        print("[ARDUINO] Waiting for physical PANIC button signal...")

        # Give boards such as Arduino UNO R4 time to finish resetting
        # when the serial port is opened.
        time.sleep(2)
        device.reset_input_buffer()

        while not stop_event.is_set():
            try:
                line = device.readline().decode("utf-8", errors="ignore").strip().upper()
            except Exception as e:
                print(f"[ARDUINO READ ERROR] {e}")
                break

            if line == "PANIC":
                print("[ARDUINO] Physical panic button pressed -> PANIC")
                threading.Thread(
                    target=handle_panic,
                    daemon=True
                ).start()

        device.close()
        print("[ARDUINO] Serial listener stopped.")

    except Exception as e:
        print(
            f"[ARDUINO ERROR] Could not open {ARDUINO_PORT}: {e}"
        )
        print(
            "[ARDUINO] Software panic (P) will remain available as a fallback."
        )


# ============================================================
# GLOBAL KEYBOARD HANDLER
# ============================================================

fall_handler_global = None

latest_frame = None

latest_frame_lock = threading.Lock()


def get_latest_frame():

    with latest_frame_lock:

        if latest_frame is None:

            return None

        return latest_frame.copy()


def on_key_press(key):

    global fall_handler_global

    try:

        if not hasattr(key, "char"):

            return


        if not key.char:

            return


        character = (
            key.char.lower()
        )


        # ====================================================
        # P -> PANIC
        # ====================================================

        if character == "p":

            print(
                "[KEYBOARD] "
                "P pressed -> PANIC"
            )

            threading.Thread(
                target=handle_panic,
                daemon=True
            ).start()

            return


        # ====================================================
        # F -> no longer required
        # ====================================================

        if character == "f":

            print(
                "[KEYBOARD] F ignored -> fall detection is already "
                "running continuously on the dedicated fall camera."
            )

            return


    except Exception as e:

        print(
            "[KEYBOARD ERROR] "
            f"{e}"
        )


def start_keyboard_listener():

    listener = keyboard.Listener(
        on_press=on_key_press
    )

    listener.daemon = True

    listener.start()


    print(
        "[KEYBOARD] Controls:"
    )

    print(
        "           F = Not required (fall camera is always active)"
    )

    print(
        "           P = Panic"
    )

    print(
        "           Q = Quit"
    )


    return listener

# ============================================================
# ARDUINO / NODEMCU HARDWARE LISTENER
# ============================================================

def handle_panic():
    """
    Handles a physical panic-button press from NodeMCU.

    The NodeMCU sends:
        PANIC

    This function uses the same SAHAY Telegram
    notification system already used by the project.
    """

    print()
    print("========================================")
    print("        PHYSICAL PANIC BUTTON")
    print("========================================")

    timestamp = time.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    message = (
        "SAHAY PANIC ALERT\n\n"
        "Physical panic button was pressed.\n\n"
        f"Time: {timestamp}\n"
        "Source: NodeMCU V3\n"
        "Location: Home"
    )

    try:

        # ----------------------------------------------------
        # Voice alert
        # ----------------------------------------------------

        speak(
            "Emergency panic button pressed. "
            "Sending an alert."
        )

        # ----------------------------------------------------
        # Database
        # ----------------------------------------------------

        log_activity(
            "panic",
            "Hardware",
            "Physical panic button pressed."
        )

        create_alert(
            "panic",
            "Physical panic button pressed.",
            severity="CRITICAL"
        )

        # ----------------------------------------------------
        # Telegram
        # ----------------------------------------------------

        result = send_telegram_message(
            message
        )

        print(
            f"[PANIC] Telegram result: {result}"
        )

        if result:

            print(
                "[PANIC] Telegram alert sent successfully."
            )

        else:

            print(
                "[PANIC] Telegram alert failed."
            )

    except Exception as e:

        print(
            "[PANIC ERROR]"
        )

        print(
            f"{type(e).__name__}: {e}"
        )


def arduino_listener():
    """
    Continuously listens to the NodeMCU USB serial port.

    Expected messages:

        PANIC
        DISTANCE:120.5
        DISTANCE:75.2
        DISTANCE:35.8
    """

    if not ARDUINO_ENABLED:

        print(
            "[ARDUINO] Hardware interface disabled."
        )

        return

    if serial is None:

        print(
            "[ARDUINO ERROR] PySerial is not installed."
        )

        print(
            "Run: pip install pyserial"
        )

        return

    try:

        print()
        print(
            "========================================"
        )

        print(
            "[ARDUINO] Connecting to NodeMCU..."
        )

        print(
            f"[ARDUINO] Port: {ARDUINO_PORT}"
        )

        print(
            f"[ARDUINO] Baud: {ARDUINO_BAUD_RATE}"
        )

        print(
            "========================================"
        )

        arduino = serial.Serial(
            ARDUINO_PORT,
            ARDUINO_BAUD_RATE,
            timeout=1
        )

        # NodeMCU resets when serial connection opens.
        time.sleep(2)

        print(
            "[ARDUINO] NodeMCU connected."
        )

        print(
            "[ARDUINO] Listening for hardware events..."
        )

        while True:

            try:

                line = (
                    arduino
                    .readline()
                    .decode(
                        "utf-8",
                        errors="ignore"
                    )
                    .strip()
                )

                if not line:
                    continue

                print(
                    f"[ARDUINO] {line}"
                )

                # =================================================
                # PANIC BUTTON
                # =================================================

                if line == "PANIC":

                    print(
                        "[ARDUINO] PANIC signal received!"
                    )

                    # Run in separate thread so the serial
                    # listener remains responsive.

                    threading.Thread(
                        target=handle_panic,
                        daemon=True
                    ).start()

                # =================================================
                # ULTRASONIC DISTANCE
                # =================================================

                elif line.startswith(
                    "DISTANCE:"
                ):

                    distance_value = (
                        line.split(
                            ":",
                            1
                        )[1]
                    )

                    try:

                        distance = float(
                            distance_value
                        )

                        print(
                            f"[ULTRASONIC] "
                            f"{distance:.1f} cm"
                        )

                    except ValueError:

                        print(
                            "[ARDUINO] Invalid "
                            f"distance: {distance_value}"
                        )

            except Exception as e:

                print(
                    "[ARDUINO READ ERROR]"
                )

                print(
                    f"{type(e).__name__}: {e}"
                )

                time.sleep(1)

    except Exception as e:

        print()
        print(
            "========================================"
        )

        print(
            "[ARDUINO CONNECTION ERROR]"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        print(
            "Check the COM port and make sure"
        )

        print(
            "Arduino Serial Monitor is closed."
        )

        print(
            "========================================"
        )
# ============================================================
# MAIN
# ============================================================

def main():

    global fall_handler_global
    global latest_frame


    print()
    print(
        "============================================"
    )

    print(
        "       SAHAY SMART AI SAFETY ASSISTANT"
    )

    print(
        "============================================"
    )

    print(
        "Starting integrated software demonstration..."
    )

    print()


    # ========================================================
    # DATABASE
    # ========================================================

    init_db()

    print(
        "[SYSTEM] Database initialized."
    )


    # ========================================================
    # TWO CAMERAS
    # ========================================================

    visitor_cap = cv2.VideoCapture(VISITOR_CAMERA_INDEX)
    fall_cap = cv2.VideoCapture(FALL_CAMERA_INDEX)

    if not visitor_cap.isOpened():
        print(
            f"[CAMERA ERROR] Could not open visitor camera "
            f"(index {VISITOR_CAMERA_INDEX})."
        )
        return

    if not fall_cap.isOpened():
        print(
            f"[CAMERA ERROR] Could not open fall camera "
            f"(index {FALL_CAMERA_INDEX})."
        )
        visitor_cap.release()
        return

    print(
        f"[CAMERA] Visitor camera opened successfully (index {VISITOR_CAMERA_INDEX})."
    )
    print(
        f"[CAMERA] Fall camera opened successfully (index {FALL_CAMERA_INDEX})."
    )


    # ========================================================
    # MODULE INITIALIZATION
    # ========================================================

    try:

        visitor_handler = (
            VisitorEventHandler()
        )

        fall_handler = (
            FallEventHandler()
        )

        fall_handler_global = (
            fall_handler
        )

    except Exception as e:

        print()
        print(
            "[SYSTEM ERROR] "
            "Could not initialize modules."
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        visitor_cap.release()
        fall_cap.release()

        return


    # ========================================================
    # START KEYBOARD LISTENER
    # ========================================================

    keyboard_listener = (
        start_keyboard_listener()
    )

    arduino_stop_event = threading.Event()
    arduino_thread = threading.Thread(
        target=arduino_panic_listener,
        args=(arduino_stop_event,),
        daemon=True
    )
    arduino_thread.start()


    # ========================================================
    # WELLBEING
    # ========================================================

    wellbeing_thread = threading.Thread(
        target=wellbeing_checkin_loop,
        daemon=True
    )

    wellbeing_thread.start()


    # ========================================================
    # INITIAL MODE
    # ========================================================

    set_mode(
        DUAL_MODE
    )


    print(
        "============================================"
    )

    print(
        "             SAHAY IS RUNNING"
    )

    print(
        "============================================"
    )

    print(
        "CURRENT MODE:"
    )

    print(
        "  DUAL CAMERA MODE"
    )

    print(
        f"  Visitor Camera: {VISITOR_CAMERA_INDEX}"
    )

    print(
        f"  Fall Camera: {FALL_CAMERA_INDEX}"
    )

    print()

    print(
        "Controls:"
    )

    print(
        "  F -> Not required (fall detection always active)"
    )

    print(
        "  P -> Panic"
    )

    print(
        "  Q -> Quit"
    )

    print(
        "============================================"
    )

    print()


    frame_count = 0


    # ========================================================
    # DUAL CAMERA LOOP
    # ========================================================

    try:

        while True:

            visitor_ret, visitor_frame = visitor_cap.read()
            fall_ret, fall_frame = fall_cap.read()

            if not visitor_ret:
                print("[CAMERA ERROR] Could not read visitor camera frame.")
                break

            if not fall_ret:
                print("[CAMERA ERROR] Could not read fall camera frame.")
                break

            frame_count += 1

            visitor_bgr = visitor_frame.copy()
            fall_bgr = fall_frame.copy()

            # =================================================
            # VISITOR RECOGNITION CAMERA
            # =================================================

            if frame_count % FACE_PROCESS_INTERVAL == 0:
                visitor_handler.process(visitor_bgr)

            # =================================================
            # FALL DETECTION CAMERA
            # =================================================

            if frame_count % FALL_PROCESS_INTERVAL == 0:
                fall_rgb = cv2.cvtColor(
                    fall_bgr,
                    cv2.COLOR_BGR2RGB
                )
                fall_handler.process(
                    fall_rgb,
                    fall_bgr
                )

            # =================================================
            # DISPLAY
            # =================================================

            cv2.putText(
                visitor_bgr,
                "SAHAY - VISITOR CAMERA",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )
            cv2.putText(
                visitor_bgr,
                "Visitor Recognition: ACTIVE",
                (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 255),
                2
            )

            cv2.putText(
                fall_bgr,
                "SAHAY - FALL CAMERA",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )
            cv2.putText(
                fall_bgr,
                "Fall Detection: ACTIVE",
                (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 255),
                2
            )
            cv2.putText(
                fall_bgr,
                f"Fall State: {fall_handler.detector.state}",
                (20, 105),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2
            )

            cv2.putText(
                visitor_bgr,
                "P = SOFTWARE PANIC | Q = QUIT",
                (20, 105),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                2
            )

            cv2.putText(
                fall_bgr,
                "Physical Panic Button = PANIC",
                (20, 140),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                2
            )

            cv2.imshow(
                "SAHAY - Visitor Camera",
                visitor_bgr
            )

            cv2.imshow(
                "SAHAY - Fall Camera",
                fall_bgr
            )

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                print("[SYSTEM] Quit requested.")
                break

    except KeyboardInterrupt:

        print(
            "[SYSTEM] "
            "Keyboard interrupt received."
        )


    except Exception as e:

        print()
        print(
            "[MAIN ERROR]"
        )

        print(
            f"{type(e).__name__}: {e}"
        )


    finally:

        print()
        print(
            "[SYSTEM] Shutting down..."
        )


        arduino_stop_event.set()

        visitor_cap.release()
        fall_cap.release()

        cv2.destroyAllWindows()


        try:

            keyboard_listener.stop()

        except Exception:

            pass


        try:

            fall_handler.close()

        except Exception:

            pass


        print(
            "[SYSTEM] "
            "SAHAY stopped."
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()

