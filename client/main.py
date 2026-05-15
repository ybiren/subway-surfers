"""Kivy Android client entry point."""
import os
# Must be set before kivy imports
os.environ.setdefault('KIVY_ORIENTATION', 'Portrait')

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, FadeTransition
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.utils import platform

from screens.login import LoginScreen
from screens.connect import ConnectScreen
from screens.prepare import PrepareScreen
from screens.game import GameScreen
from utils.ws_client import WSClient

# Dark background
Window.clearcolor = (0.06, 0.06, 0.12, 1)


class SubwayApp(App):
    title = 'Subway Surfers Controller'

    def __init__(self, **kw):
        super().__init__(**kw)
        self.server_ip: str | None = None
        self.username: str | None = None
        self.password: str | None = None
        self._recording_frames: list = []
        self._recording = False
        self.ws = WSClient(
            on_message=self._on_ws_message,
            on_connected=self._on_ws_connected,
            on_disconnected=self._on_ws_disconnected,
        )

    def build(self):
        self.sm = ScreenManager(transition=FadeTransition())

        self.login_screen   = LoginScreen(self)
        self.connect_screen = ConnectScreen(self)
        self.prepare_screen = PrepareScreen(self)
        self.game_screen    = GameScreen(self)

        for s in (self.login_screen, self.connect_screen,
                  self.prepare_screen, self.game_screen):
            self.sm.add_widget(s)

        self.sm.current = 'login'
        return self.sm

    # ── WebSocket callbacks ───────────────────────────────────────────────────

    def _on_ws_connected(self):
        # Route to whichever screen initiated the connection
        def _upd(dt):
            if self.sm.current == 'login':
                self.login_screen.on_ws_connected()
        Clock.schedule_once(_upd)

    def _on_ws_disconnected(self, reason):
        def _upd(dt):
            if self.sm.current == 'login':
                self.login_screen.on_ws_disconnected(reason)
        Clock.schedule_once(_upd)

    def _on_ws_message(self, msg: dict):
        t = msg.get('type')
        if t == 'auth_result':
            self._handle_auth_result(msg)
        elif t == 'pair_result':
            self._handle_pair_result(msg)
        elif t == 'pose_feedback':
            self._handle_pose_feedback(msg)
        elif t == 'game_state':
            self._handle_game_state(msg)
        elif t == 'game_over':
            self._handle_game_over(msg)

    # ── Message handlers ──────────────────────────────────────────────────────

    def _handle_auth_result(self, msg):
        ok = msg.get('success')
        username = msg.get('username')
        message = msg.get('message', '')
        if ok:
            self.username = username

        def _upd(dt):
            if self.sm.current == 'login':
                self.login_screen.on_auth_result(ok, message, username)

        Clock.schedule_once(_upd)

    def _handle_pair_result(self, msg):
        ok = msg.get('success')
        error = msg.get('error', 'Pair failed')

        def _upd(dt):
            self.connect_screen.on_pair_result(ok, error)
        Clock.schedule_once(_upd)

    def _handle_pose_feedback(self, msg):
        pose_visible = msg.get('pose_visible', False)
        gesture = msg.get('gesture')

        def _upd(dt):
            cur = self.sm.current
            if cur == 'prepare':
                self.prepare_screen.on_pose_feedback(pose_visible, gesture)
            elif cur == 'game':
                self.game_screen.on_pose_feedback(pose_visible, gesture)
        Clock.schedule_once(_upd)

    def _handle_game_state(self, msg):
        state = msg.get('state', 'playing')
        score = msg.get('score', 0)
        elapsed = msg.get('time', 0.0)
        lives = msg.get('lives', 3)

        def _upd(dt):
            if self.sm.current == 'game':
                self.game_screen.on_game_state(state, score, elapsed, lives)
        Clock.schedule_once(_upd)

    def _handle_game_over(self, msg):
        score = msg.get('score', 0)
        elapsed = msg.get('time', 0.0)
        coins = msg.get('coins', 0)

        def _upd(dt):
            if self.sm.current == 'game':
                self.game_screen.on_game_over(score, elapsed, coins)
        Clock.schedule_once(_upd)

    # ── Recording ─────────────────────────────────────────────────────────────

    def start_recording(self):
        self._recording = True
        self._recording_frames = []

    def stop_recording(self):
        self._recording = False
        if self._recording_frames:
            self._save_recording()

    def _save_recording(self):
        try:
            import cv2, numpy as np, time
            from kivy.utils import platform
            if platform == 'android':
                from android.storage import primary_external_storage_path
                path = os.path.join(primary_external_storage_path(),
                                    'DCIM', f'subway_{int(time.time())}.mp4')
            else:
                path = f'subway_{int(time.time())}.mp4'
            h, w = self._recording_frames[0].shape[:2]
            out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'mp4v'), 15, (w, h))
            for f in self._recording_frames:
                out.write(f)
            out.release()
        except Exception as e:
            print(f'[recording] save error: {e}')


if __name__ == '__main__':
    SubwayApp().run()
