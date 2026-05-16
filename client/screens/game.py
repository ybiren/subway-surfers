"""Game screen — camera preview + score HUD + in-frame alerts."""
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock


class GameScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(name='game', **kw)
        self.app = app
        self.score = 0
        self.elapsed = 0.0
        self.paused = False
        self._frame_event = None
        self._alert_event = None
        self.camera = None
        self._build_ui()

    def _build_ui(self):
        root = FloatLayout()

        # Camera is created lazily in on_enter after permissions are granted
        self._camera_container = Widget(size_hint=(1, 1))
        root.add_widget(self._camera_container)
        self._root_layout = root

        # Red edge overlay (shown when out of frame)
        self.alert_overlay = Widget(size_hint=(1, 1))
        self._update_overlay(False)
        root.add_widget(self.alert_overlay)

        # Top HUD bar
        hud = BoxLayout(
            size_hint=(1, None), height=55,
            pos_hint={'top': 1},
            padding=10, spacing=10,
        )
        with hud.canvas.before:
            Color(0, 0, 0, 0.55)
            self._hud_rect = Rectangle(pos=hud.pos, size=hud.size)
        hud.bind(pos=self._update_hud_rect, size=self._update_hud_rect)

        self.score_lbl = Label(
            text='Score: 0',
            font_size='20sp', bold=True,
            color=(1, 0.85, 0, 1),
        )
        self.time_lbl = Label(
            text='00:00',
            font_size='20sp', bold=True,
            color=(1, 1, 1, 1),
        )
        hud.add_widget(self.score_lbl)
        hud.add_widget(self.time_lbl)
        root.add_widget(hud)

        # Alert label (center)
        self.alert_lbl = Label(
            text='',
            font_size='18sp', bold=True,
            color=(1, 0.3, 0.3, 1),
            size_hint=(0.9, None), height=44,
            pos_hint={'center_x': 0.5, 'top': 0.88},
        )
        root.add_widget(self.alert_lbl)

        # Resume button (shown when paused)
        self.resume_btn = Button(
            text='Resume',
            font_size='20sp',
            size_hint=(None, None), width=180, height=60,
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            background_color=(0.1, 0.6, 0.2, 1),
            background_normal='',
            opacity=0,
            disabled=True,
        )
        self.resume_btn.bind(on_press=self._on_resume)
        root.add_widget(self.resume_btn)

        # End screen overlay (hidden initially)
        self.end_panel = BoxLayout(
            orientation='vertical',
            size_hint=(0.8, None), height=280,
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            padding=20, spacing=10,
            opacity=0,
        )
        with self.end_panel.canvas.before:
            Color(0.07, 0.07, 0.15, 0.92)
            self._end_rect = Rectangle(pos=self.end_panel.pos, size=self.end_panel.size)
        self.end_panel.bind(pos=self._upd_end_rect, size=self._upd_end_rect)

        self.end_title = Label(text='GAME OVER', font_size='26sp', bold=True, color=(1, 0.3, 0.3, 1))
        self.end_score = Label(text='', font_size='20sp', color=(1, 0.85, 0, 1))
        self.end_time  = Label(text='', font_size='18sp', color=(1, 1, 1, 1))
        self.end_coins = Label(text='', font_size='18sp', color=(1, 0.85, 0, 1))

        new_game_btn = Button(
            text='New Game',
            font_size='16sp',
            size_hint_y=None, height=50,
            background_color=(0.1, 0.5, 0.9, 1),
            background_normal='',
        )
        new_game_btn.bind(on_press=self._on_new_game)

        exit_btn = Button(
            text='Exit',
            font_size='16sp',
            size_hint_y=None, height=50,
            background_color=(0.6, 0.1, 0.1, 1),
            background_normal='',
        )
        exit_btn.bind(on_press=self._on_exit)

        for w in (self.end_title, self.end_score, self.end_time, self.end_coins, new_game_btn, exit_btn):
            self.end_panel.add_widget(w)
        root.add_widget(self.end_panel)

        self.add_widget(root)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _update_hud_rect(self, inst, val):
        self._hud_rect.pos = inst.pos
        self._hud_rect.size = inst.size

    def _upd_end_rect(self, inst, val):
        self._end_rect.pos = inst.pos
        self._end_rect.size = inst.size

    def _update_overlay(self, show: bool):
        self.alert_overlay.canvas.clear()
        if show:
            from kivy.graphics import Color, Line
            with self.alert_overlay.canvas:
                Color(1, 0, 0, 0.45)
                Line(rectangle=(4, 4,
                                 self.alert_overlay.width - 8,
                                 self.alert_overlay.height - 8),
                     width=14)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_enter(self):
        if self.camera is None:
            from kivy.uix.camera import Camera
            self.camera = Camera(
                play=False,
                resolution=(640, 480),
                size_hint=(1, 1),
                pos_hint={'center_x': 0.5, 'center_y': 0.5},
            )
            self._root_layout.remove_widget(self._camera_container)
            self._root_layout.add_widget(self.camera, index=len(self._root_layout.children))
        self.camera.play = True
        self._frame_event = Clock.schedule_interval(self._send_frame, 1 / 15)
        self.end_panel.opacity = 0
        self.resume_btn.opacity = 0
        self.resume_btn.disabled = True

    def on_leave(self):
        if self._frame_event:
            self._frame_event.cancel()
            self._frame_event = None

    # ── Frame sending ─────────────────────────────────────────────────────────

    def _send_frame(self, dt):
        tex = self.camera.texture
        if tex is None:
            return
        frame = self._texture_to_jpeg(tex)
        if frame:
            self.app.ws.send_bytes(frame)

    def _texture_to_jpeg(self, tex, quality=60) -> bytes | None:
        try:
            from PIL import Image
            import io
            buf = tex.pixels
            img = Image.frombytes('RGBA', (tex.width, tex.height), buf)
            img = img.transpose(Image.FLIP_TOP_BOTTOM).convert('RGB')
            out = io.BytesIO()
            img.save(out, format='JPEG', quality=quality)
            return out.getvalue()
        except Exception:
            return None

    # ── Pose feedback ─────────────────────────────────────────────────────────

    def on_pose_feedback(self, pose_visible, gesture):
        if not pose_visible:
            self._show_alert('Step back into frame!')
            self._update_overlay(True)
            self.app.ws.send({'type': 'player_status', 'in_frame': False})
        else:
            self._clear_alert()
            self._update_overlay(False)

    def _show_alert(self, text):
        self.alert_lbl.text = text
        if self._alert_event:
            self._alert_event.cancel()
        self._alert_event = Clock.schedule_once(lambda dt: self._clear_alert(), 3)

    def _clear_alert(self):
        self.alert_lbl.text = ''

    # ── Game state ────────────────────────────────────────────────────────────

    def on_game_state(self, state, score, elapsed, lives):
        self.score = score
        self.elapsed = elapsed
        self.score_lbl.text = f'Score: {score}'
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        self.time_lbl.text = f'{mins:02d}:{secs:02d}'
        paused = state == 'paused'
        if paused != self.paused:
            self.paused = paused
            self.resume_btn.opacity = 1 if paused else 0
            self.resume_btn.disabled = not paused

    def on_game_over(self, score, elapsed, coins):
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        self.end_score.text = f'Score: {score}'
        self.end_time.text  = f'Time: {mins:02d}:{secs:02d}'
        self.end_coins.text = f'Coins: {coins}'
        self.end_panel.opacity = 1

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_resume(self, *_):
        self.app.ws.send({'type': 'game_cmd', 'cmd': 'resume'})

    def _on_new_game(self, *_):
        self.end_panel.opacity = 0
        self.app.sm.current = 'prepare'

    def _on_exit(self, *_):
        self.app.stop()
