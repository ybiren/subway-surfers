"""WebSocket client that runs in a background thread."""
import asyncio
import json
import threading
import websockets
import time


class WSClient:
    def __init__(self, on_message=None, on_connected=None, on_disconnected=None):
        self.on_message = on_message
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected
        self._ws = None
        self._loop = None
        self._thread = None
        self._running = False
        self._send_queue = asyncio.Queue() if False else None  # created in thread

    def connect(self, uri):
        """Connect to WebSocket URI in a background thread."""
        self._uri = uri
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def disconnect(self):
        self._running = False
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._close(), self._loop)

    def send(self, data: dict):
        if self._loop and self._ws and self._running:
            asyncio.run_coroutine_threadsafe(
                self._send_raw(json.dumps(data)), self._loop
            )

    def send_bytes(self, data: bytes):
        if self._loop and self._ws and self._running:
            asyncio.run_coroutine_threadsafe(
                self._send_raw(data), self._loop
            )

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect_loop())

    async def _connect_loop(self):
        retry_delay = 1
        while self._running:
            try:
                async with websockets.connect(self._uri, ping_interval=20) as ws:
                    self._ws = ws
                    retry_delay = 1
                    if self.on_connected:
                        self.on_connected()
                    await self._listen(ws)
            except Exception as e:
                self._ws = None
                if self.on_disconnected:
                    self.on_disconnected(str(e))
                if self._running:
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 10)

    async def _listen(self, ws):
        async for message in ws:
            if self.on_message:
                try:
                    data = json.loads(message)
                    self.on_message(data)
                except Exception:
                    pass

    async def _send_raw(self, data):
        if self._ws:
            try:
                await self._ws.send(data)
            except Exception:
                pass

    async def _close(self):
        if self._ws:
            await self._ws.close()
