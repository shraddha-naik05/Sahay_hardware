import speech_recognition as sr


class SpeechRecognizer:
    def __init__(self):
        self.recognizer = sr.Recognizer()

    def listen(self, timeout=5, phrase_time_limit=5):
        try:
            with sr.Microphone() as source:

                print("[STT] Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(
                    source,
                    duration=0.5
                )

                print("[STT] Listening...")
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit
                )

            print("[STT] Processing speech...")

            text = self.recognizer.recognize_google(audio)

            print(f"[STT] Heard: {text}")

            return text.lower().strip()

        except sr.WaitTimeoutError:
            print("[STT] No speech detected.")
            return ""

        except sr.UnknownValueError:
            print("[STT] Could not understand speech.")
            return ""

        except sr.RequestError as e:
            print(f"[STT] Speech service error: {e}")
            return ""

        except Exception as e:
            print(f"[STT ERROR] {e}")
            return ""