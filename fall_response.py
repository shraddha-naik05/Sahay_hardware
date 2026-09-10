import time

from stt import SpeechRecognizer

SAFE_RESPONSES = [
    "fine",
    "i'm fine",
    "im fine",
    "i am fine",
    "okay",
    "ok",
    "i'm okay",
    "im okay",
    "i am okay",
    "alright",
    "all right",
    "i'm alright",
    "im alright",
    "i am alright"
]

def is_safe_response(text):
    """
    Check whether the resident's response indicates
    that they are okay.
    """

    if not text:
        return False

    text = text.lower().strip()

    for response in SAFE_RESPONSES:
        if response in text:
            return True

    return False

def wait_for_response(timeout_seconds=15):

    recognizer = SpeechRecognizer()

    start_time = time.time()

    print()
    print("================================")
    print("      FALL RESPONSE CHECK")
    print("================================")
    print("Waiting for resident response...")

    while time.time() - start_time < timeout_seconds:

        remaining = timeout_seconds - (
            time.time() - start_time
        )

        listen_timeout = min(
            5,
            max(1, int(remaining))
        )

        text = recognizer.listen(
            timeout=listen_timeout,
            phrase_time_limit=5
        )

        if not text:
            continue

        print(f"[FALL RESPONSE] Resident said: {text}")

        if is_safe_response(text):

            print(
                "[FALL RESPONSE] "
                "Resident confirmed they are okay."
            )

            return True

        print(
            "[FALL RESPONSE] "
            "Response not recognized as a safe response."
        )

    print(
        "[FALL RESPONSE] "
        "No safe response received."
    )

    return False