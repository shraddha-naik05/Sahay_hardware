import cv2
from notifications import send_telegram_photo


IMAGE_PATH = "test_photo.jpg"


print("================================")
print("   SAHAY TELEGRAM PHOTO TEST")
print("================================")
print()


# Open webcam
camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("[CAMERA ERROR] Could not open camera.")
    exit()


print("Camera opened.")
print("Capturing image...")

ret, frame = camera.read()

camera.release()


if not ret:
    print("[CAMERA ERROR] Could not capture frame.")
    exit()


# Save image
cv2.imwrite(IMAGE_PATH, frame)

print(f"Image saved: {IMAGE_PATH}")
print()


caption = (
    "SAHAY TEST ALERT\n\n"
    "This is a test camera snapshot."
)


result = send_telegram_photo(
    IMAGE_PATH,
    caption
)


print()

if result:
    print("================================")
    print("   PHOTO TEST SUCCESSFUL")
    print("================================")
else:
    print("================================")
    print("      PHOTO TEST FAILED")
    print("================================")