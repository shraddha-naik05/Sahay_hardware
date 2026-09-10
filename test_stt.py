from stt import SpeechRecognizer


print("================================")
print("       SAHAY STT TEST")
print("================================")
print("Speak after the microphone starts.")
print("Say: I am fine")
print()

recognizer = SpeechRecognizer()

text = recognizer.listen(
    timeout=10,
    phrase_time_limit=5
)

print()
print("Final result:")

if text:
    print(f"Recognized: {text}")
else:
    print("No valid speech recognized.")