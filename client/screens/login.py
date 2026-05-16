"""Login / Signup screen — also collects server IP and initiates WS connection."""
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.clock import Clock


class LoginScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(name='login', **kw)
        self.app = app
        self._pending_action = None   # 'login' or 'signup'
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = BoxLayout(orientation='vertical', padding=40, spacing=16)
        root.add_widget(Widget(size_hint_y=0.1))

        root.add_widget(Label(
            text='[b]SUBWAY SURFERS[/b]', markup=True,
            font_size='34sp', color=(1, 0.85, 0, 1),
            size_hint_y=None, height=56,
        ))
        root.add_widget(Label(
            text='Motion Controller 2222',
            font_size='17sp', color=(0.75, 0.75, 0.75, 1),
            size_hint_y=None, height=32,
        ))

        root.add_widget(Widget(size_hint_y=0.04))

        # ── Server IP field ────────────────────────────────────────────────
        root.add_widget(Label(
            text='Server IP',
            font_size='13sp', color=(0.6, 0.6, 0.8, 1),
            size_hint=(0.85, None), height=22,
            pos_hint={'center_x': 0.5},
            halign='left', text_size=(9999, None),
        ))
        self.ip_input = TextInput(
            hint_text='e.g. 192.168.1.10',
            multiline=False,
            size_hint=(0.85, None), height=50,
            pos_hint={'center_x': 0.5},
            font_size='17sp',
            background_color=(0.10, 0.10, 0.18, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.45, 0.45, 0.45, 1),
            cursor_color=(1, 1, 1, 1),
            padding=[14, 12],
            keyboard_suggestions=False,
        )
        root.add_widget(self.ip_input)

        # ── Username ───────────────────────────────────────────────────────
        self.username_input = TextInput(
            hint_text='Username',
            multiline=False,
            size_hint=(0.85, None), height=50,
            pos_hint={'center_x': 0.5},
            font_size='17sp',
            background_color=(0.10, 0.10, 0.18, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.45, 0.45, 0.45, 1),
            cursor_color=(1, 1, 1, 1),
            padding=[14, 12],
        )
        root.add_widget(self.username_input)

        # ── Password ───────────────────────────────────────────────────────
        self.password_input = TextInput(
            hint_text='Password',
            password=True,
            multiline=False,
            size_hint=(0.85, None), height=50,
            pos_hint={'center_x': 0.5},
            font_size='17sp',
            background_color=(0.10, 0.10, 0.18, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.45, 0.45, 0.45, 1),
            cursor_color=(1, 1, 1, 1),
            padding=[14, 12],
        )
        root.add_widget(self.password_input)

        # ── Buttons ────────────────────────────────────────────────────────
        btn_row = BoxLayout(
            size_hint=(0.85, None), height=58,
            pos_hint={'center_x': 0.5}, spacing=16,
        )
        self.login_btn = Button(
            text='Login',
            font_size='18sp',
            background_color=(0.12, 0.42, 0.88, 1),
            background_normal='',
        )
        self.login_btn.bind(on_press=self._on_login)

        self.signup_btn = Button(
            text='Sign Up',
            font_size='18sp',
            background_color=(0.10, 0.62, 0.28, 1),
            background_normal='',
        )
        self.signup_btn.bind(on_press=self._on_signup)

        btn_row.add_widget(self.login_btn)
        btn_row.add_widget(self.signup_btn)
        root.add_widget(btn_row)

        # ── Status ─────────────────────────────────────────────────────────
        self.status_label = Label(
            text='', font_size='14sp',
            color=(1, 0.4, 0.4, 1),
            size_hint_y=None, height=34,
        )
        root.add_widget(self.status_label)
        root.add_widget(Widget())
        self.add_widget(root)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_login(self, *_):
        self._start('login')

    def _on_signup(self, *_):
        self._start('signup')

    def _start(self, action):
        ip = self.ip_input.text.strip()
        username = self.username_input.text.strip()
        password = self.password_input.text

        if not ip:
            self.set_status('Enter the server IP address', error=True)
            return
        if not username or not password:
            self.set_status('Enter username and password', error=True)
            return

        self._pending_action = action
        # Store credentials so ws_connected callback can send auth
        self.app.server_ip = ip
        self.app.username = username
        self.app.password = password

        self.set_status('Connecting to server…')
        self._set_buttons_enabled(False)
        self.app.ws.connect(f'ws://{ip}:8765')

    def _set_buttons_enabled(self, enabled):
        self.login_btn.disabled = not enabled
        self.signup_btn.disabled = not enabled

    # ── WS connected — now send auth ──────────────────────────────────────────

    def on_ws_connected(self):
        self.set_status('Connected — authenticating…')
        self.app.ws.send({
            'type': 'auth',
            'action': self._pending_action,
            'username': self.app.username,
            'password': self.app.password,
        })

    def on_ws_disconnected(self, reason):
        self.set_status(f'Cannot connect: {reason}', error=True)
        self._set_buttons_enabled(True)

    # ── Auth result ───────────────────────────────────────────────────────────

    def on_auth_result(self, success, message, username):
        if success:
            self.set_status(f'Welcome, {username}!', error=False)
            Clock.schedule_once(lambda dt: setattr(self.app.sm, 'current', 'connect'), 0.4)
        else:
            self.set_status(message, error=True)
            self._set_buttons_enabled(True)

    def set_status(self, text, error=False):
        self.status_label.color = (1, 0.35, 0.35, 1) if error else (0.3, 0.9, 0.3, 1)
        self.status_label.text = text
