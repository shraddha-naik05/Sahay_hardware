import pyttsx3

engine = pyttsx3.init()

engine.setProperty("rate", 150)
engine.setProperty("volume", 1.0)

print("Testing SAHAY voice...")

engine.say("Fall detected. Are you okay? Please say I am fine if you are safe.")

engine.runAndWait()

print("TTS test completed.")