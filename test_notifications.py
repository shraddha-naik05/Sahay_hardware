from notifications import send_telegram_message

message = (
    "SAHAY EMERGENCY ALERT\n\n"
    "A possible fall was detected.\n"
    "The resident did not respond to the safety check."
)

print("================================")
print("   SAHAY TELEGRAM TEST")
print("================================")

result = send_telegram_message(message)

print()

if result:
    print("Telegram notification test successful.")
else:
    print("Telegram notification test failed.")