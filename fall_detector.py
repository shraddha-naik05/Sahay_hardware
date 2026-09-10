import os
import time
import math
from collections import deque

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from dotenv import load_dotenv

load_dotenv()


# ============================================================
# FALL DETECTION SETTINGS
# ============================================================

# Lower values = easier detection
MOVEMENT_THRESHOLD = float(
    os.getenv("FALL_MOVEMENT_THRESHOLD", "0.09")
)

# Body angle at which the person is considered sufficiently
# horizontal for fall confirmation.
HORIZONTAL_ANGLE = float(
    os.getenv("FALL_HORIZONTAL_ANGLE", "50")
)

# Number of consecutive frames required to confirm the fall.
CONFIRMATION_FRAMES = int(
    os.getenv("FALL_CONFIRMATION_FRAMES", "3")
)

# Prevent repeated fall alerts immediately after one detection.
COOLDOWN_SECONDS = int(
    os.getenv("FALL_COOLDOWN_SECONDS", "30")
)

# How much recent movement history to examine.
HISTORY_SECONDS = float(
    os.getenv("FALL_HISTORY_SECONDS", "1.0")
)

# MediaPipe landmark visibility threshold.
MIN_VISIBILITY = float(
    os.getenv("FALL_MIN_VISIBILITY", "0.35")
)


class FallDetector:

    def __init__(
        self,
        confirmation_frames=CONFIRMATION_FRAMES,
        cooldown_seconds=COOLDOWN_SECONDS
    ):

        self.confirmation_frames = confirmation_frames
        self.cooldown_seconds = cooldown_seconds

        # ----------------------------------------------------
        # Load MediaPipe Pose Landmarker
        # ----------------------------------------------------

        model_path = os.path.join(
            os.path.dirname(__file__),
            "models",
            "pose_landmarker_full.task"
        )

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Pose model not found: {model_path}"
            )

        base_options = python.BaseOptions(
            model_asset_path=model_path
        )

        options = vision.PoseLandmarkerOptions(
            base_options=base_options
        )

        self.pose = vision.PoseLandmarker.create_from_options(
            options
        )

        # ----------------------------------------------------
        # Detection State
        # ----------------------------------------------------

        self.state = "NORMAL"

        self.fall_candidate_frames = 0

        self.last_fall_time = 0

        self.previous_hip_y = None

        self.hip_history = deque()

        # ----------------------------------------------------
        # Values exposed for debugging / dashboard / UI
        # ----------------------------------------------------

        self.last_body_angle = 0.0
        self.last_hip_displacement = 0.0
        self.last_frame_movement = 0.0

        self.last_horizontal = False
        self.last_significant_movement = False

        self.person_detected = False

    # ========================================================
    # BODY ANGLE
    # ========================================================

    def _calculate_body_angle(
        self,
        left_shoulder,
        right_shoulder,
        left_hip,
        right_hip
    ):

        shoulder_x = (
            left_shoulder.x +
            right_shoulder.x
        ) / 2

        shoulder_y = (
            left_shoulder.y +
            right_shoulder.y
        ) / 2

        hip_x = (
            left_hip.x +
            right_hip.x
        ) / 2

        hip_y = (
            left_hip.y +
            right_hip.y
        ) / 2

        dx = hip_x - shoulder_x
        dy = hip_y - shoulder_y

        # 0° = upright
        # ~90° = horizontal
        angle = math.degrees(
            math.atan2(abs(dx), abs(dy))
        )

        return angle

    # ========================================================
    # LANDMARK VISIBILITY
    # ========================================================

    def _landmarks_reliable(
        self,
        left_shoulder,
        right_shoulder,
        left_hip,
        right_hip
    ):

        values = [
            getattr(left_shoulder, "visibility", 1.0),
            getattr(right_shoulder, "visibility", 1.0),
            getattr(left_hip, "visibility", 1.0),
            getattr(right_hip, "visibility", 1.0)
        ]

        return all(
            value >= MIN_VISIBILITY
            for value in values
        )

    # ========================================================
    # PROCESS FRAME
    # ========================================================

    def process(self, frame):

        current_time = time.time()

        # ----------------------------------------------------
        # Cooldown
        # ----------------------------------------------------

        if (
            current_time - self.last_fall_time
            < self.cooldown_seconds
        ):
            return False

        # ----------------------------------------------------
        # Convert frame to MediaPipe image
        #
        # IMPORTANT:
        # frame must be RGB.
        # main.py should convert:
        #
        # rgb_frame = cv2.cvtColor(
        #     bgr_frame,
        #     cv2.COLOR_BGR2RGB
        # )
        # ----------------------------------------------------

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=frame
        )

        results = self.pose.detect(mp_image)

        # ----------------------------------------------------
        # No person detected
        # ----------------------------------------------------

        if not results.pose_landmarks:

            self.person_detected = False

            self.state = "NORMAL"

            self.fall_candidate_frames = 0

            self.previous_hip_y = None

            self.hip_history.clear()

            self.last_body_angle = 0.0
            self.last_hip_displacement = 0.0
            self.last_frame_movement = 0.0

            self.last_horizontal = False
            self.last_significant_movement = False

            return False

        self.person_detected = True

        # ----------------------------------------------------
        # Get first person's landmarks
        # ----------------------------------------------------

        landmarks = results.pose_landmarks[0]

        left_shoulder = landmarks[
            vision.PoseLandmark.LEFT_SHOULDER
        ]

        right_shoulder = landmarks[
            vision.PoseLandmark.RIGHT_SHOULDER
        ]

        left_hip = landmarks[
            vision.PoseLandmark.LEFT_HIP
        ]

        right_hip = landmarks[
            vision.PoseLandmark.RIGHT_HIP
        ]

        # ----------------------------------------------------
        # Check landmark reliability
        # ----------------------------------------------------

        if not self._landmarks_reliable(
            left_shoulder,
            right_shoulder,
            left_hip,
            right_hip
        ):

            return False

        # ====================================================
        # CALCULATE BODY POSITION
        # ====================================================

        hip_y = (
            left_hip.y +
            right_hip.y
        ) / 2

        body_angle = self._calculate_body_angle(
            left_shoulder,
            right_shoulder,
            left_hip,
            right_hip
        )

        # ----------------------------------------------------
        # Store hip history
        # ----------------------------------------------------

        self.hip_history.append(
            (current_time, hip_y)
        )

        while (
            self.hip_history and
            current_time - self.hip_history[0][0]
            > HISTORY_SECONDS
        ):

            self.hip_history.popleft()

        # ----------------------------------------------------
        # Calculate displacement over history
        # ----------------------------------------------------

        hip_displacement = 0.0

        if len(self.hip_history) >= 2:

            oldest_hip_y = self.hip_history[0][1]

            hip_displacement = abs(
                hip_y - oldest_hip_y
            )

        # ----------------------------------------------------
        # Calculate frame-to-frame movement
        # ----------------------------------------------------

        frame_movement = 0.0

        if self.previous_hip_y is not None:

            frame_movement = abs(
                hip_y -
                self.previous_hip_y
            )

        self.previous_hip_y = hip_y

        # ====================================================
        # UPDATE DEBUG VALUES
        # ====================================================

        self.last_body_angle = body_angle

        self.last_hip_displacement = hip_displacement

        self.last_frame_movement = frame_movement

        # ====================================================
        # DETECTION CONDITIONS
        # ====================================================

        horizontal_body = (
            body_angle >= HORIZONTAL_ANGLE
        )

        significant_movement = (
            hip_displacement >= MOVEMENT_THRESHOLD
        )

        self.last_horizontal = horizontal_body

        self.last_significant_movement = (
            significant_movement
        )

        # ====================================================
        # STATE MACHINE
        # ====================================================

        # ----------------------------------------------------
        # NORMAL
        # ----------------------------------------------------

        if self.state == "NORMAL":

            if significant_movement:

                self.state = "SUSPECTED"

                print(
                    "[FALL STATE] "
                    "Possible fall movement detected."
                )

        # ----------------------------------------------------
        # SUSPECTED
        # ----------------------------------------------------

        elif self.state == "SUSPECTED":

            # If the person becomes horizontal,
            # start confirmation.

            if horizontal_body:

                self.state = "CONFIRMING"

                self.fall_candidate_frames = 1

                print(
                    "[FALL STATE] "
                    "Abnormal posture detected. "
                    "Confirming..."
                )

            # If movement settles without horizontal
            # posture, return to normal.

            elif hip_displacement < (
                MOVEMENT_THRESHOLD * 0.5
            ):

                self.state = "NORMAL"

                self.fall_candidate_frames = 0

        # ----------------------------------------------------
        # CONFIRMING
        # ----------------------------------------------------

        elif self.state == "CONFIRMING":

            if horizontal_body:

                self.fall_candidate_frames += 1

            else:

                # Don't immediately cancel the detection.
                # Allow one temporary bad frame.

                self.fall_candidate_frames -= 1

                if self.fall_candidate_frames <= 0:

                    self.fall_candidate_frames = 0

                    self.state = "NORMAL"

        # ====================================================
        # DEBUG OUTPUT
        # ====================================================

        print(
            f"[FALL DEBUG] "
            f"angle={body_angle:.1f} | "
            f"hip_disp={hip_displacement:.3f} | "
            f"frame_move={frame_movement:.3f} | "
            f"horizontal={horizontal_body} | "
            f"state={self.state} | "
            f"confirm="
            f"{self.fall_candidate_frames}/"
            f"{self.confirmation_frames}"
        )

        # ====================================================
        # FINAL FALL CONFIRMATION
        # ====================================================

        if (
            self.state == "CONFIRMING"
            and
            self.fall_candidate_frames
            >= self.confirmation_frames
        ):

            print(
                "\n"
                "================================\n"
                "       FALL DETECTED!\n"
                "================================\n"
            )

            self.last_fall_time = current_time

            self.state = "NORMAL"

            self.fall_candidate_frames = 0

            return True

        return False

    # ========================================================
    # RESET
    # ========================================================

    def reset(self):

        self.state = "NORMAL"

        self.fall_candidate_frames = 0

        self.previous_hip_y = None

        self.hip_history.clear()

        self.last_body_angle = 0.0

        self.last_hip_displacement = 0.0

        self.last_frame_movement = 0.0

        self.last_horizontal = False

        self.last_significant_movement = False

        self.person_detected = False

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        self.pose.close()