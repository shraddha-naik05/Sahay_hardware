import os
import pickle
import sqlite3

import cv2
import numpy as np

from importlib import import_module


# Import dynamically so static analyzers do not report a missing optional
# dependency while preserving the same runtime API.
FaceAnalysis = import_module("insightface.app").FaceAnalysis

from database import DB_PATH, get_connection


class ArcFaceEngine:

    def __init__(self):

        model_name = os.getenv(
            "ARCFACE_MODEL",
            "buffalo_l"
        )

        det_size = int(
            os.getenv(
                "FACE_DET_SIZE",
                "640"
            )
        )

        print("Loading ArcFace model...")

        self.app = FaceAnalysis(
            name=model_name,
            providers=["CPUExecutionProvider"]
        )

        self.app.prepare(
            ctx_id=0,
            det_size=(det_size, det_size)
        )

        print("ArcFace model loaded successfully.")

    def detect_faces(self, frame):

        return self.app.get(frame)

    def get_embedding(self, face):

        embedding = face.embedding.astype(
            np.float32
        )

        norm = np.linalg.norm(embedding)

        if norm == 0:
            return None

        return embedding / norm


class FaceDatabase:

    def save_face(
        self,
        name,
        relation,
        embedding
    ):

        conn = get_connection()

        data = pickle.dumps(embedding)

        conn.execute("""
            INSERT INTO known_faces
            (name, relation, embedding, model, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (
            name,
            relation,
            data,
            "buffalo_l"
        ))

        conn.commit()
        conn.close()

    def get_faces(self):

        conn = get_connection()

        rows = conn.execute("""
            SELECT *
            FROM known_faces
            WHERE model = 'buffalo_l'
        """).fetchall()

        conn.close()

        result = []

        for row in rows:

            embedding = pickle.loads(
                row["embedding"]
            )

            result.append({
                "id": row["id"],
                "name": row["name"],
                "relation": row["relation"],
                "embedding": embedding
            })

        return result


class VisitorRecognizer:

    def __init__(self):

        self.engine = ArcFaceEngine()
        self.database = FaceDatabase()

        self.threshold = float(
            os.getenv(
                "FACE_MATCH_THRESHOLD",
                "0.45"
            )
        )

    def recognize(self, frame):

        faces = self.engine.detect_faces(
            frame
        )

        known_faces = self.database.get_faces()

        results = []

        for face in faces:

            embedding = self.engine.get_embedding(
                face
            )

            if embedding is None:
                continue

            best_name = None
            best_relation = None
            best_score = -1

            for known in known_faces:

                score = float(
                    np.dot(
                        embedding,
                        known["embedding"]
                    )
                )

                if score > best_score:

                    best_score = score

                    best_name = known["name"]

                    best_relation = known["relation"]

            is_known = (
                best_score >= self.threshold
            )

            results.append({
                "bbox": face.bbox.astype(int),
                "known": is_known,
                "name": best_name if is_known else None,
                "relation": (
                    best_relation
                    if is_known
                    else None
                ),
                "score": best_score
            })

        return results