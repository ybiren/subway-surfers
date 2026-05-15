"""Connect screen — enter the 6-digit pair code shown on the PC screen."""
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.clock import Clock


class ConnectScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(name='connect', **kw)
        self.app = app
        self._build_ui()

    def _build_ui(self):
        root = BoxLayout(orientation='vertical', padding=40, spacing=20)
        root.add_widget(Widget(size_hint_y=0.18))

        root.add_widget(Label(
            text='[b]Pair with PC[/b]', markup=True,
            font_size='30sp', color=(1, 0.85, 0, 1),
            size_hint_y=None, height=56,
        ))
        root.add_widget(Label(
            text='Enter the 6-digit code\nshown on the game screen',
            font_size='16sp', color=(0.75, 0.75, 0.75, 1),
            size_hint_y=None, height=56,
            halign='center',
        ))

        self.code_input = TextInput(
            hint_text='  _ _ _ _ _ _',
            multiline=False,
            size_hint=(0.7, None), height=70,
            pos_hint={'center_x': 0.5},
            font_size='32sp',
            background_color=(0.10, 0.10, 0.18, 1),
            foreground_color=(1, 0.9, 0, 1),
            hint_text_color=(0.35, 0.35, 0.35, 1),
            cursor_color=(1, 1, 1, 1),
            padding=[20, 14],
            input_filter='int',
            max_chars=6,
            halign='center',
        )
        root.add_widget(self.code_input)

        self.pair_btn = Button(
            text='Pair',
            font_size='20sp',
            size_hint=(0.7, None), height=62,
            pos_hint={'center_x': 0.5},
            background_color=(0.12, 0.42, 0.88, 1),
            background_normal='',
        )
        self.pair_btn.bind(on_press=self._on_pair)
        root.add_widget(self.pair_btn)

        self.status_label = Label(
            text='', font_size='15sp',
            color=(1, 0.4, 0.4, 1),
            size_hint_y=None, height=36,
        )
        root.add_widget(self.status_label)
        root.add_widget(Widget())
        self.add_widget(root)

    def on_enter(self):
        self.code_input.text = ''
        self.set_status('')
        self.pair_btn.disabled = False

    def _on_pair(self, *_):
        code = self.code_input.text.strip()
        if len(code) != 6:
            self.set_status('Enter the full 6-digit code', error=True)
            return
        self.set_status('Pairing…')
        self.pair_btn.disabled = True
        self.app.ws.send({'type': 'pair', 'code': code})

    def on_pair_result(self, success, error=''):
        if success:
            self.set_status('Paired!', error=False)
            Clock.schedule_once(lambda dt: setattr(self.app.sm, 'current', 'prepare'), 0.4)
        else:
            self.set_status(error or 'Invalid code — try again', error=True)
            self.pair_btn.disabled = False

    def set_status(self, text, error=False):
        self.status_label.color = (1, 0.35, 0.35, 1) if error else (0.3, 0.9, 0.3, 1)
        self.status_label.text = text
