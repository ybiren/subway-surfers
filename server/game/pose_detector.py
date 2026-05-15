"""MediaPipe-based pose detector running on the PC."""
import cv2
import mediapipe as mp
import numpy as np
import time


class PoseDetector:
    JUMP_THRESHOLD = 0.07       # hip moves up by this fraction
    DUCK_THRESHOLD = 0.08       # shoulder moves down
    LATERAL_THRESHOLD = 0.12    # nose moves left/right from neutral
    PAUSE_THRESHOLD = 0.12      # both wrists above shoulders by this much
    GESTURE_COOLDOWN = 0.4      # seconds between same gesture

    def __init__(self):
        mp_pose = mp.solutions.pose
        self.pose = mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.L = mp_pose.PoseLandmark

        self.neutral_hip_y = None
        self.neutral_nose_x = 0.5
        self.neutral_shoulder_y = None

        self.is_jumping = False
        self.is_ducking = False
        self._cooldowns = {}

    def reset_calibration(self):
        self.neutral_hip_y = None
        self.neutral_shoulder_y = None
        self.is_jumping = False
        self.is_ducking = False

    def process(self, frame_bgr) -> tuple:
        """
        Returns (gesture, pose_visible, annotated_frame).
        gesture is one of: jump, duck, unduck, move_left, move_right, pause, None.
        """
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb)

        annotated = frame_bgr.copy()
        if not results.pose_landmarks:
            return None, False, annotated

        mp.solutions.drawing_utils.draw_landmarks(
            annotated,
            results.pose_landmarks,
            mp.solutions.pose.POSE_CONNECTIONS,
        )

        lm = results.pose_landmarks.landmark
        if self.neutral_hip_y is None:
            self._calibrate(lm)
            return None, True, annotated

        gesture = self._detect(lm)
        return gesture, True, annotated

    def _calibrate(self, lm):
        L = self.L
        self.neutral_hip_y = (lm[L.LEFT_HIP].y + lm[L.RIGHT_HIP].y) / 2
        self.neutral_shoulder_y = (lm[L.LEFT_SHOULDER].y + lm[L.RIGHT_SHOULDER].y) / 2
        self.neutral_nose_x = lm[L.NOSE].x

    def _can_trigger(self, name) -> bool:
        return time.time() - self._cooldowns.get(name, 0) > self.GESTURE_COOLDOWN

    def _fire(self, name) -> str:
        self._cooldowns[name] = time.time()
        return name

    def _detect(self, lm) -> str | None:
        L = self.L

        hip_y = (lm[L.LEFT_HIP].y + lm[L.RIGHT_HIP].y) / 2
        shoulder_y = (lm[L.LEFT_SHOULDER].y + lm[L.RIGHT_SHOULDER].y) / 2
        nose_x = lm[L.NOSE].x
        lw_y = lm[L.LEFT_WRIST].y
        rw_y = lm[L.RIGHT_WRIST].y

        # Pause: both wrists above shoulders
        if (shoulder_y - lw_y > self.PAUSE_THRESHOLD and
                shoulder_y - rw_y > self.PAUSE_THRESHOLD):
            if self._can_trigger('pause'):
                return self._fire('pause')

        # Jump: hip moves up (y decreases)
        hip_delta = self.neutral_hip_y - hip_y
        if hip_delta > self.JUMP_THRESHOLD:
            if not self.is_jumping and self._can_trigger('jump'):
                self.is_jumping = True
                return self._fire('jump')
        else:
            self.is_jumping = False

        # Duck: shoulder moves down (y increases)
        shoulder_delta = shoulder_y - self.neutral_shoulder_y
        if shoulder_delta > self.DUCK_THRESHOLD:
            if not self.is_ducking and self._can_trigger('duck'):
                self.is_ducking = True
                return self._fire('duck')
        else:
            if self.is_ducking:
                self.is_ducking = False
                return 'unduck'

        # Lateral movement
        dx = nose_x - self.neutral_nose_x
        if dx < -self.LATERAL_THRESHOLD:
            if self._can_trigger('move_left'):
                return self._fire('move_left')
        elif dx > self.LATERAL_THRESHOLD:
            if self._can_trigger('move_right'):
                return self._fire('move_right')

        return None
