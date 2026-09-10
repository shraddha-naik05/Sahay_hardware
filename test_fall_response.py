import pyttsx3

from fall_response import wait_for_response


def speak(message):

    engine = pyttsx3.init()

    engine.setProperty("rate", 150)
    engine.setProperty("volume", 1.0)

    print(f"[TTS] {message}")

    engine.say(message)
    engine.runAndWait()


print("================================")
print("   SAHAY FALL RESPONSE TEST")
print("================================")
print()

speak(
    "A fall has been detected. "
    "Are you okay? "
    "Please say I am fine if you are safe."
)

safe = wait_for_response(
    timeout_seconds=15
)

print()

if safe:

    print("================================")
    print("        RESULT: SAFE")
    print("================================")

else:

    print("================================")
    print("     RESULT: EMERGENCY")
    print("================================")