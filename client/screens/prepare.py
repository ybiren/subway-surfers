"""Prepare screen — camera preview + mode selection + start button."""
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.camera import Camera
from kivy.clock import Clock


class PrepareScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(name='prepare', **kw)
        self.app = app
        self.pose_visible = False
        self.recording = False
        self._frame_event = None
        self._build_ui()

    def _build_ui(self):
        root = FloatLayout()

        # Camera preview (full background)
        self.camera = Camera(
            play=False,
            resolution=(640, 480),
            size_hint=(1, 1),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
        )
        root.add_widget(self.camera)

        # Top HUD
        top_bar = BoxLayout(
            size_hint=(1, None), height=60,
            pos_hint={'top': 1},
            padding=10, spacing=10,
        )
        self.status_lbl = Label(
            text='[b]Position yourself so your full body is visible[/b]',
            markup=True, font_size='14sp',
            color=(1, 1, 1, 1),
        )
        top_bar.add_widget(self.status_lbl)
        root.add_widget(top_bar)

        # Side buttons (left)
        side_left = BoxLayout(
            orientation='vertical',
            size_hint=(None, None), width=120, height=140,
            pos_hint={'x': 0.02, 'center_y': 0.5},
            spacing=10,
        )
        self.body_btn = Button(
            text='Full\nBody',
            font_size='14sp',
            background_color=(0.1, 0.4, 0.85, 1),
            background_normal='',
        )
        self.body_btn.bind(on_press=lambda *_: self._select_mode('body'))
        side_left.add_widget(self.body_btn)
        root.add_widget(side_left)

        # Record button (right side)
        self.record_btn = Button(
            text='⏺ REC',
            font_size='14sp',
            size_hint=(None, None), width=100, height=50,
            pos_hint={'right': 0.98, 'center_y': 0.5},
            background_color=(0.8, 0.1, 0.1, 1),
            background_normal='',
        )
        self.record_btn.bind(on_press=self._toggle_record)
        root.add_widget(self.record_btn)

        # Bottom: start button
        self.start_btn = Button(
            text='START',
            font_size='22sp',
            bold=True,
            size_hint=(None, None), width=200, height=70,
            pos_hint={'center_x': 0.5, 'y': 0.04},
            background_color=(0.1, 0.7, 0.2, 0.5),
            background_normal='',
            disabled=True,
        )
        self.start_btn.bind(on_press=self._on_start)
        root.add_widget(self.start_btn)

        self.add_widget(root)

    # ── Screen lifecycle ──────────────────────────────────────────────────────

    def on_enter(self):
        self.camera.play = True
        self._frame_event = Clock.schedule_interval(self._send_frame, 1 / 15)

    def on_leave(self):
        if self._frame_event:
            self._frame_event.cancel()
            self._frame_event = None
        # keep camera playing for game screen

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
        self.pose_visible = pose_visible
        self.start_btn.disabled = not pose_visible
        if pose_visible:
            self.start_btn.background_color = (0.1, 0.7, 0.2, 1)
            self.status_lbl.text = '[b]Ready! Press START when you are set[/b]'
            self.status_lbl.color = (0.3, 1, 0.3, 1)
        else:
            self.start_btn.background_color = (0.1, 0.7, 0.2, 0.4)
            self.status_lbl.text = '[b]Cannot detect pose — make sure full body is visible[/b]'
            self.status_lbl.color = (1, 0.4, 0.4, 1)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _select_mode(self, mode):
        pass  # body mode only in this version

    def _toggle_record(self, *_):
        self.recording = not self.recording
        if self.recording:
            self.record_btn.background_color = (0.9, 0.2, 0.2, 1)
            self.record_btn.text = '⏹ STOP'
            self.app.start_recording()
        else:
            self.record_btn.background_color = (0.5, 0.1, 0.1, 1)
            self.record_btn.text = '⏺ REC'
            self.app.stop_recording()

    def _on_start(self, *_):
        self.app.ws.send({'type': 'game_cmd', 'cmd': 'start'})
        self.app.sm.current = 'game'
