import cv2

from fall_detector import FallDetector


detector = FallDetector()

camera = cv2.VideoCapture(0)

camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

if not camera.isOpened():

    print("Could not open webcam.")

    exit()


print("Fall detection test started.")
print("Press Q to quit.")


while True:

    ret, frame = camera.read()

    if not ret:

        break

    rgb = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )

    fall = detector.process(rgb)

    if fall:

        cv2.putText(
            frame,
            "FALL DETECTED!",
            (30, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (0, 0, 255),
            3
        )

    cv2.imshow(
        "SAHAY Fall Detection Test",
        frame
    )

    if cv2.waitKey(1) & 0xFF == ord("q"):

        break


camera.release()

cv2.destroyAllWindows()