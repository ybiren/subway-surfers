"""WebSocket server: handles phone auth, pairing, frame relay, and game commands."""
import asyncio
import json
import random
import socket
import string
import base64
import queue as tqueue

import cv2
import numpy as np
import websockets

from database import init_db, login, signup
from game.pose_detector import PoseDetector


def _get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()


class SubwayServer:
    PORT = 8765

    def __init__(self, cmd_q: tqueue.Queue, state_q: tqueue.Queue):
        self.cmd_q = cmd_q      # → game engine
        self.state_q = state_q  # ← game engine

        self.phone_ws = None          # authenticated + paired phone
        self.pair_code: str | None = None
        self.detector = PoseDetector()
        self._paused_by_server = False

        self.ip = _get_local_ip()
        self._generate_pair_code()

    # ── Pair code ──────────────────────────────────────────────────────────────

    def _generate_pair_code(self):
        self.pair_code = ''.join(random.choices(string.digits, k=6))
        qr_data = f'subway://{self.ip}:{self.PORT}?code={self.pair_code}'
        self.cmd_q.put({
            'type': 'pair_info',
            'code': self.pair_code,
            'ip': self.ip,
            'qr_data': qr_data,
        })

    # ── Entry point ────────────────────────────────────────────────────────────

    async def start(self):
        init_db()
        async with websockets.serve(self._handle, '0.0.0.0', self.PORT,
                                    max_size=5 * 1024 * 1024):
            print(f'[server] Listening on {self.ip}:{self.PORT}  code={self.pair_code}')
            await asyncio.gather(
                self._state_broadcaster(),
                asyncio.Future()   # run forever
            )

    # ── Per-connection handler ─────────────────────────────────────────────────

    async def _handle(self, ws):
        client = {'authenticated': False, 'username': None, 'paired': False}
        try:
            async for raw in ws:
                if isinstance(raw, bytes):
                    await self._handle_frame(ws, client, raw)
                else:
                    await self._handle_text(ws, client, json.loads(raw))
        except (websockets.exceptions.ConnectionClosed, json.JSONDecodeError):
            pass
        finally:
            if ws is self.phone_ws:
                self.phone_ws = None
                self.cmd_q.put({'type': 'phone_disconnected'})

    async def _handle_text(self, ws, client, msg):
        t = msg.get('type')
        if t == 'auth':
            await self._auth(ws, client, msg)
        elif t == 'pair':
            await self._pair(ws, client, msg)
        elif t == 'game_cmd':
            self._forward_game_cmd(client, msg.get('cmd'))
        elif t == 'player_status':
            self._handle_player_status(client, msg)

    async def _handle_frame(self, ws, client, data: bytes):
        """Receive JPEG frame, run pose detection, send feedback."""
        if not client.get('paired'):
            return
        arr = np.frombuffer(data, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return

        gesture, pose_visible, _ = self.detector.process(frame)

        # Auto-pause when player leaves frame
        if not pose_visible and not self._paused_by_server:
            self._paused_by_server = True
            self.cmd_q.put({'type': 'game_cmd', 'cmd': 'pause'})
        elif pose_visible and self._paused_by_server:
            self._paused_by_server = False

        if gesture:
            self.cmd_q.put({'type': 'game_cmd', 'cmd': gesture})

        feedback = {
            'type': 'pose_feedback',
            'pose_visible': pose_visible,
            'gesture': gesture,
        }
        try:
            await ws.send(json.dumps(feedback))
        except Exception:
            pass

    # ── Auth ───────────────────────────────────────────────────────────────────

    async def _auth(self, ws, client, msg):
        action = msg.get('action')
        username = msg.get('username', '').strip()
        password = msg.get('password', '')
        if action == 'login':
            ok, text = login(username, password)
        elif action == 'signup':
            ok, text = signup(username, password)
        else:
            ok, text = False, 'Unknown action'

        if ok:
            client['authenticated'] = True
            client['username'] = username

        await ws.send(json.dumps({'type': 'auth_result', 'success': ok,
                                  'message': text, 'username': username if ok else None}))

    # ── Pairing ────────────────────────────────────────────────────────────────

    async def _pair(self, ws, client, msg):
        if not client.get('authenticated'):
            await ws.send(json.dumps({'type': 'pair_result', 'success': False,
                                      'error': 'Not authenticated'}))
            return
        code = msg.get('code', '')
        if code == self.pair_code:
            client['paired'] = True
            self.phone_ws = ws
            self.detector.reset_calibration()
            await ws.send(json.dumps({'type': 'pair_result', 'success': True}))
            self.cmd_q.put({'type': 'phone_connected', 'username': client['username']})
        else:
            await ws.send(json.dumps({'type': 'pair_result', 'success': False,
                                      'error': 'Invalid code'}))

    # ── Game commands ──────────────────────────────────────────────────────────

    def _forward_game_cmd(self, client, cmd):
        if client.get('paired') and cmd:
            self.cmd_q.put({'type': 'game_cmd', 'cmd': cmd})

    def _handle_player_status(self, client, msg):
        if not client.get('paired'):
            return
        in_frame = msg.get('in_frame', True)
        if not in_frame and not self._paused_by_server:
            self._paused_by_server = True
            self.cmd_q.put({'type': 'game_cmd', 'cmd': 'pause'})

    # ── State broadcaster ──────────────────────────────────────────────────────

    async def _state_broadcaster(self):
        """Forward game-state updates from game engine to phone."""
        loop = asyncio.get_running_loop()
        while True:
            await asyncio.sleep(0.05)
            while not self.state_q.empty():
                try:
                    state = self.state_q.get_nowait()
                except tqueue.Empty:
                    break
                if self.phone_ws:
                    try:
                        await self.phone_ws.send(json.dumps(state))
                    except Exception:
                        pass
