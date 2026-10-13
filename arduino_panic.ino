// ==========================================
// SAHAY - ESP32 Panic Button
// ==========================================

const int PANIC_BUTTON_PIN = 4;

bool lastButtonState = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50;

void setup() {
  // Button uses ESP32's internal pull-up resistor
  pinMode(PANIC_BUTTON_PIN, INPUT_PULLUP);

  Serial.begin(115200);

  Serial.println("SAHAY PANIC SYSTEM READY");
}

void loop() {

  bool reading = digitalRead(PANIC_BUTTON_PIN);

  // Detect button state change
  if (reading != lastButtonState) {
    lastDebounceTime = millis();
  }

  // Wait for debounce period
  if ((millis() - lastDebounceTime) > debounceDelay) {

    // LOW means button is pressed
    if (lastButtonState == HIGH && reading == LOW) {

      Serial.println("PANIC");
    }
  }
  lastButtonState = reading;
}