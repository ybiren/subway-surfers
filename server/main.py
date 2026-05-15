"""PC entry point — starts WebSocket server in thread and runs Pygame game."""
import asyncio
import queue
import threading
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ws_server import SubwayServer
from game.engine import GameEngine
from database import init_db


def _run_server(cmd_q, state_q):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    server = SubwayServer(cmd_q, state_q)
    loop.run_until_complete(server.start())


def main():
    init_db()
    cmd_q = queue.Queue(maxsize=100)
    state_q = queue.Queue(maxsize=100)

    t = threading.Thread(target=_run_server, args=(cmd_q, state_q), daemon=True)
    t.start()

    engine = GameEngine(cmd_q, state_q)
    engine.run()


if __name__ == '__main__':
    main()
