import cv2
import numpy as np

from face_service import ArcFaceEngine, FaceDatabase


SAMPLES_REQUIRED = 8


def enroll_person():

    name = input(
        "Enter person's name: "
    ).strip()

    relation = input(
        "Enter relation: "
    ).strip()

    if not name:
        print("Name cannot be empty.")
        return

    engine = ArcFaceEngine()
    database = FaceDatabase()

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():

        print("ERROR: Could not open webcam.")

        return

    embeddings = []

    print()
    print("Camera opened.")
    print("Look at the camera.")
    print()
    print(
        "Press C to capture a sample."
    )
    print(
        "Press Q to cancel."
    )

    while len(embeddings) < SAMPLES_REQUIRED:

        ret, frame = camera.read()

        if not ret:

            print("Could not read webcam frame.")

            break

        faces = engine.detect_faces(
            frame
        )

        display = frame.copy()

        for face in faces:

            bbox = face.bbox.astype(int)

            x1, y1, x2, y2 = bbox

            cv2.rectangle(
                display,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                2
            )

        cv2.putText(
            display,
            f"Samples: {len(embeddings)}/{SAMPLES_REQUIRED}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )

        cv2.imshow(
            "SAHAY - Face Enrollment",
            display
        )

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):

            break

        if key == ord("c"):

            if len(faces) != 1:

                print(
                    "Please ensure exactly ONE face is visible."
                )

                continue

            embedding = engine.get_embedding(
                faces[0]
            )

            if embedding is None:

                print(
                    "Could not generate embedding."
                )

                continue

            embeddings.append(
                embedding
            )

            print(
                f"Captured sample "
                f"{len(embeddings)}/{SAMPLES_REQUIRED}"
            )

    camera.release()

    cv2.destroyAllWindows()

    if len(embeddings) < SAMPLES_REQUIRED:

        print("Enrollment cancelled.")

        return

    # Average all captured embeddings
    average_embedding = np.mean(
        np.array(embeddings),
        axis=0
    )

    # Normalize
    average_embedding = (
        average_embedding /
        np.linalg.norm(average_embedding)
    )

    database.save_face(
        name,
        relation,
        average_embedding
    )

    print()
    print(
        f"Successfully enrolled {name}."
    )


if __name__ == "__main__":

    enroll_person()