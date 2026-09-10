import cv2

from face_service import VisitorRecognizer


def main():

    recognizer = VisitorRecognizer()

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():

        print("Could not open webcam.")

        return

    print("Visitor recognition started.")
    print("Press Q to quit.")

    while True:

        ret, frame = camera.read()

        if not ret:

            print("Could not read camera.")

            break

        results = recognizer.recognize(
            frame
        )

        for result in results:

            x1, y1, x2, y2 = result["bbox"]

            if result["known"]:

                label = (
                    f'{result["name"]} '
                    f'({result["score"]:.2f})'
                )

                color = (0, 255, 0)

            else:

                label = (
                    f'UNKNOWN '
                    f'({result["score"]:.2f})'
                )

                color = (0, 0, 255)

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                color,
                2
            )

            cv2.putText(
                frame,
                label,
                (x1, max(y1 - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                color,
                2
            )

        cv2.imshow(
            "SAHAY Visitor Recognition",
            frame
        )

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):

            break

    camera.release()

    cv2.destroyAllWindows()


if __name__ == "__main__":

    main()