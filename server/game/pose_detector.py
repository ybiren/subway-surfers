"""MediaPipe-based pose detector running on the PC (Tasks API, mediapipe>=0.10.30)."""
import os
import time
import urllib.request

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# Landmark indices (same values as old PoseLandmark enum)
_NOSE          = 0
_L_SHOULDER    = 11
_R_SHOULDER    = 12
_L_WRIST       = 15
_R_WRIST       = 16
_L_HIP         = 23
_R_HIP         = 24

import sys
if getattr(sys, 'frozen', False):
    _MODEL_PATH = os.path.join(sys._MEIPASS, 'game', 'pose_landmarker.task')
else:
    _MODEL_PATH = os.path.join(os.path.dirname(__file__), 'pose_landmarker.task')
_MODEL_URL  = (
    'https://storage.googleapis.com/mediapipe-models/'
    'pose_landmarker/pose_landmarker_full/float16/latest/'
    'pose_landmarker_full.task'
)

# Connections to draw (pairs of landmark indices)
_CONNECTIONS = [
    (11,12),(11,13),(13,15),(12,14),(14,16),
    (11,23),(12,24),(23,24),(23,25),(24,26),
    (25,27),(26,28),
]


def _ensure_model():
    if not os.path.exists(_MODEL_PATH):
        print('[pose] Downloading pose landmarker model (~30 MB)…')
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        print('[pose] Model ready.')


class PoseDetector:
    JUMP_THRESHOLD    = 0.15
    DUCK_THRESHOLD    = 0.08
    LATERAL_THRESHOLD = 0.06
    PAUSE_THRESHOLD   = 0.12
    GESTURE_COOLDOWN  = 0.4

    def __init__(self):
        _ensure_model()
        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=_MODEL_PATH),
            running_mode=vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=0.3,
            min_pose_presence_confidence=0.3,
            min_tracking_confidence=0.3,
        )
        self.landmarker = vision.PoseLandmarker.create_from_options(options)

        self.neutral_hip_y      = None
        self.neutral_nose_x     = 0.5
        self.neutral_shoulder_y = None
        self.is_jumping         = False
        self.is_ducking         = False
        self._cooldowns         = {}
        self._calib_frames      = []
        self._calib_target      = 10   # average over 10 frames

    def reset_calibration(self):
        self.neutral_hip_y      = None
        self.neutral_shoulder_y = None
        self.is_jumping         = False
        self.is_ducking         = False
        self._calib_frames      = []

    def process(self, frame_bgr) -> tuple:
        """Returns (gesture, pose_visible, annotated_frame, landmarks_list).
        landmarks_list is a list of {x, y} normalised coords, or None."""
        rgb      = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result   = self.landmarker.detect(mp_image)

        annotated = frame_bgr.copy()
        if not result.pose_landmarks:
            return None, False, annotated, None

        lm = result.pose_landmarks[0]
        self._draw(annotated, lm)

        # Mirror x axis — front camera image is flipped horizontally
        class _MirroredLM:
            def __init__(self, p): self.x = 1.0 - p.x; self.y = p.y
        lm = [_MirroredLM(p) for p in lm]

        # Key landmarks for client overlay (indices that matter for the game)
        _KEY = [0, 11, 12, 13, 14, 15, 16, 23, 24]
        lm_data = [{'x': lm[i].x, 'y': lm[i].y, 'i': i}
                   for i in _KEY if i < len(lm)]

        if self.neutral_hip_y is None:
            self._calib_frames.append(lm)
            if len(self._calib_frames) < self._calib_target:
                return None, True, annotated, lm_data
            self._calibrate_avg()

        return self._detect(lm), True, annotated, lm_data

    # ── Internals ─────────────────────────────────────────────────────────────

    def _calibrate_avg(self):
        frames = self._calib_frames
        self.neutral_hip_y      = sum((f[_L_HIP].y + f[_R_HIP].y) / 2 for f in frames) / len(frames)
        self.neutral_shoulder_y = sum((f[_L_SHOULDER].y + f[_R_SHOULDER].y) / 2 for f in frames) / len(frames)
        self.neutral_nose_x     = sum(f[_NOSE].x for f in frames) / len(frames)
        print(f'[pose] Calibrated: nose_x={self.neutral_nose_x:.3f} hip_y={self.neutral_hip_y:.3f}')
        self._calib_frames = []

    def _can_trigger(self, name) -> bool:
        return time.time() - self._cooldowns.get(name, 0) > self.GESTURE_COOLDOWN

    def _fire(self, name) -> str:
        self._cooldowns[name] = time.time()
        return name

    def _detect(self, lm):
        hip_y      = (lm[_L_HIP].y + lm[_R_HIP].y) / 2
        shoulder_y = (lm[_L_SHOULDER].y + lm[_R_SHOULDER].y) / 2
        nose_x     = lm[_NOSE].x
        lw_y       = lm[_L_WRIST].y
        rw_y       = lm[_R_WRIST].y

        hip_delta    = self.neutral_hip_y - hip_y
        hands_raised = (shoulder_y - lw_y > self.PAUSE_THRESHOLD and
                        shoulder_y - rw_y > self.PAUSE_THRESHOLD)

        # Pause — hands raised overrides everything
        if hands_raised:
            if self._can_trigger('pause'):
                return self._fire('pause')

        # Jump — only if hands are NOT raised
        if hip_delta > self.JUMP_THRESHOLD and not hands_raised:
            if not self.is_jumping and self._can_trigger('jump'):
                self.is_jumping = True
                return self._fire('jump')
        else:
            self.is_jumping = False

        # Duck — shoulder moves down
        if shoulder_y - self.neutral_shoulder_y > self.DUCK_THRESHOLD:
            if not self.is_ducking and self._can_trigger('duck'):
                self.is_ducking = True
                return self._fire('duck')
        else:
            if self.is_ducking:
                self.is_ducking = False
                return 'unduck'

        # Lateral — blocked only for 0.5s after a jump fires
        dx = nose_x - self.neutral_nose_x
        jump_just_fired = time.time() - self._cooldowns.get('jump', 0) < 0.5
        if not jump_just_fired:
            if dx < -self.LATERAL_THRESHOLD:
                if self._can_trigger('move_left'):
                    return self._fire('move_left')
            elif dx > self.LATERAL_THRESHOLD:
                if self._can_trigger('move_right'):
                    return self._fire('move_right')

        return None

    def _draw(self, frame, lm):
        h, w = frame.shape[:2]
        pts = [(int(p.x * w), int(p.y * h)) for p in lm]
        for a, b in _CONNECTIONS:
            if a < len(pts) and b < len(pts):
                cv2.line(frame, pts[a], pts[b], (0, 255, 0), 2)
        for p in pts:
            cv2.circle(frame, p, 4, (0, 0, 255), -1)
