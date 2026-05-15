"""Subway Surfers-style pseudo-3D game engine using Pygame."""
import pygame
import random
import math
import time
import queue
import io
import base64

# ── Screen ───────────────────────────────────────────────────────────────────
SW, SH = 1200, 700
FPS = 60

# ── Perspective / Track ───────────────────────────────────────────────────────
VANISH_X = SW // 2
VANISH_Y = 220
GROUND_Y = 580
HORIZON_Y = VANISH_Y

# Lane X at player (near bottom)
LANE_X = [SW // 2 - 250, SW // 2, SW // 2 + 250]
LANE_LEFT_EDGE = [SW // 2 - 380, SW // 2 - 130, SW // 2 + 120]
LANE_RIGHT_EDGE = [SW // 2 - 120, SW // 2 + 130, SW // 2 + 380]

PLAYER_H = 110
PLAYER_W = 60
JUMP_HEIGHT = 200   # pixels at ground level
JUMP_DURATION = 0.55  # seconds

# ── Colors ────────────────────────────────────────────────────────────────────
SKY_TOP    = (10,  10,  30)
SKY_BOT    = (40,  40,  80)
TRACK_DARK = (30,  25,  20)
TRACK_MID  = (50,  45,  35)
RAIL_COLOR = (160, 150, 120)
COIN_COLOR = (255, 215,  0)
COIN_SHINE = (255, 255, 150)
PLAYER_CLR = (30, 144, 255)
PLAYER_ACC = (0,  80, 200)
OBS_TRAIN  = (180,  30,  30)
OBS_BARRIER= (200, 120,   0)
OBS_BAR    = (150,  60, 180)
UI_BG      = (0, 0, 0, 160)
WHITE      = (255, 255, 255)
GREEN      = (50,  200,  50)
RED        = (200,  50,  50)
GRAY       = (120, 120, 120)
DARK_GRAY  = (50,   50,  50)
YELLOW     = (255, 220,   0)
BLACK      = (0, 0, 0)


def project(lane: int, depth: float, y_offset: float = 0.0):
    """
    depth  0.0 = at player (near, big)
           1.0 = at horizon (far, tiny)
    Returns (screen_x, screen_y, scale)
    """
    t = depth
    x = LANE_X[lane] * (1 - t) + VANISH_X * t
    y = GROUND_Y * (1 - t) + HORIZON_Y * t
    y -= y_offset * (1 - t)
    scale = max(0.05, 1.0 - t * 0.92)
    return x, y, scale


# ── Entities ──────────────────────────────────────────────────────────────────

class Coin:
    def __init__(self, lane, depth):
        self.lane = lane
        self.depth = depth
        self.collected = False

    def update(self, speed, dt):
        self.depth -= speed * dt

    def draw(self, surf):
        if self.depth < 0 or self.depth > 1:
            return
        x, y, s = project(self.lane, self.depth)
        r = max(4, int(18 * s))
        pygame.draw.circle(surf, COIN_COLOR, (int(x), int(y)), r)
        pygame.draw.circle(surf, COIN_SHINE, (int(x) - r // 3, int(y) - r // 3), max(2, r // 3))

    @property
    def dead(self):
        return self.depth < -0.05


OBSTACLE_TRAIN   = 'train'    # full lane, dodge left/right
OBSTACLE_BARRIER = 'barrier'  # low, must jump
OBSTACLE_BAR     = 'bar'      # high, must duck


class Obstacle:
    def __init__(self, lane, depth, kind):
        self.lane = lane
        self.depth = depth
        self.kind = kind

    def update(self, speed, dt):
        self.depth -= speed * dt

    def draw(self, surf):
        if self.depth < 0 or self.depth > 1:
            return
        x, y, s = project(self.lane, self.depth)
        if self.kind == OBSTACLE_TRAIN:
            w = int(220 * s)
            h = int(340 * s)
            rect = pygame.Rect(int(x) - w // 2, int(y) - h, w, h)
            pygame.draw.rect(surf, OBS_TRAIN, rect, border_radius=4)
            # windows
            ww, wh = max(4, w // 5), max(4, h // 6)
            for row in range(2):
                for col in range(3):
                    wx = rect.left + w // 8 + col * (w // 3)
                    wy = rect.top + h // 6 + row * (h // 3)
                    pygame.draw.rect(surf, YELLOW, (wx, wy, ww, wh))
        elif self.kind == OBSTACLE_BARRIER:
            w = int(200 * s)
            h = int(80 * s)
            rect = pygame.Rect(int(x) - w // 2, int(y) - h, w, h)
            pygame.draw.rect(surf, OBS_BARRIER, rect, border_radius=3)
            # stripes
            stripe_w = max(2, w // 6)
            for i in range(0, w, stripe_w * 2):
                pygame.draw.rect(surf, WHITE, (rect.left + i, rect.top, stripe_w, h))
        elif self.kind == OBSTACLE_BAR:
            # horizontal bar floating at mid height
            bar_y = int(y) - int(160 * s)
            w = int(200 * s)
            h = max(6, int(30 * s))
            rect = pygame.Rect(int(x) - w // 2, bar_y, w, h)
            pygame.draw.rect(surf, OBS_BAR, rect, border_radius=2)
            # poles
            pole_w = max(4, int(12 * s))
            left_pole = pygame.Rect(rect.left, bar_y, pole_w, int(y) - bar_y)
            right_pole = pygame.Rect(rect.right - pole_w, bar_y, pole_w, int(y) - bar_y)
            pygame.draw.rect(surf, OBS_BAR, left_pole)
            pygame.draw.rect(surf, OBS_BAR, right_pole)

    def get_hitbox(self):
        """Return (lane, depth_range, height_range_norm) for collision."""
        if self.kind == OBSTACLE_TRAIN:
            return self.lane, 0.06, (0.0, 1.0)   # full height
        elif self.kind == OBSTACLE_BARRIER:
            return self.lane, 0.06, (0.0, 0.45)  # lower half
        elif self.kind == OBSTACLE_BAR:
            return self.lane, 0.06, (0.45, 1.0)  # upper half

    @property
    def dead(self):
        return self.depth < -0.05


class Player:
    LANE_SPEED = 6.0  # pixels per second lane-switch speed (normalized)

    def __init__(self):
        self.lane = 1
        self.target_lane = 1
        self.lane_t = 1.0          # 0 = old lane, 1 = target lane
        self.old_lane_x = LANE_X[1]
        self.jump_timer = 0.0
        self.ducking = False
        self.dead = False
        self.invincible = 0.0      # seconds of invincibility after hit

    def move_left(self):
        if self.target_lane > 0:
            self.old_lane_x = self._current_x()
            self.target_lane -= 1
            self.lane_t = 0.0

    def move_right(self):
        if self.target_lane < 2:
            self.old_lane_x = self._current_x()
            self.target_lane += 1
            self.lane_t = 0.0

    def jump(self):
        if self.jump_timer <= 0:
            self.jump_timer = JUMP_DURATION

    def duck(self, state: bool):
        self.ducking = state

    def _current_x(self):
        t = min(1.0, self.lane_t)
        return self.old_lane_x * (1 - t) + LANE_X[self.target_lane] * t

    def update(self, dt):
        # Lane slide
        if self.lane_t < 1.0:
            self.lane_t = min(1.0, self.lane_t + dt * self.LANE_SPEED)
            if self.lane_t >= 1.0:
                self.lane = self.target_lane
        # Jump arc
        if self.jump_timer > 0:
            self.jump_timer = max(0.0, self.jump_timer - dt)
        if self.invincible > 0:
            self.invincible -= dt

    def get_y_offset(self):
        if self.jump_timer <= 0:
            return 0.0
        t = 1.0 - self.jump_timer / JUMP_DURATION   # 0→1 over jump
        return JUMP_HEIGHT * math.sin(math.pi * t)

    def get_height_scale(self):
        return 0.5 if self.ducking else 1.0

    def draw(self, surf):
        x = self._current_x()
        y_off = self.get_y_offset()
        hs = self.get_height_scale()
        h = int(PLAYER_H * hs)
        w = PLAYER_W
        px = int(x)
        py = int(GROUND_Y - y_off)

        # Blink when invincible
        if self.invincible > 0 and int(self.invincible * 10) % 2 == 0:
            return

        # Body
        body_rect = pygame.Rect(px - w // 2, py - h, w, h)
        pygame.draw.rect(surf, PLAYER_CLR, body_rect, border_radius=8)
        pygame.draw.rect(surf, PLAYER_ACC, body_rect, 3, border_radius=8)

        # Head (when not ducking, draw above body)
        if not self.ducking:
            head_r = 22
            head_y = body_rect.top - head_r
            pygame.draw.circle(surf, (255, 220, 180), (px, head_y), head_r)
            pygame.draw.circle(surf, PLAYER_ACC, (px, head_y), head_r, 2)

        # Legs (animated with running stride)
        leg_h = max(8, h // 4)
        lx = px - w // 4
        rx = px + w // 4
        leg_y = py
        pygame.draw.rect(surf, PLAYER_ACC, (lx - 8, leg_y, 12, leg_h), border_radius=3)
        pygame.draw.rect(surf, PLAYER_ACC, (rx - 4, leg_y, 12, leg_h), border_radius=3)

    def get_lane_for_collision(self):
        return self.target_lane

    def is_jumping(self):
        return self.jump_timer > 0

    def hit(self):
        if self.invincible <= 0:
            self.invincible = 1.5
            return True
        return False


# ── Background helpers ─────────────────────────────────────────────────────────

def draw_background(surf, scroll):
    # Sky gradient
    for y in range(HORIZON_Y + 80):
        t = y / (HORIZON_Y + 80)
        r = int(SKY_TOP[0] * (1 - t) + SKY_BOT[0] * t)
        g = int(SKY_TOP[1] * (1 - t) + SKY_BOT[1] * t)
        b = int(SKY_TOP[2] * (1 - t) + SKY_BOT[2] * t)
        pygame.draw.line(surf, (r, g, b), (0, y), (SW, y))

    # City silhouette (parallax layer 1, slow)
    building_data = [
        (50, 120), (150, 80), (250, 150), (350, 100), (450, 130),
        (550, 90), (650, 160), (750, 110), (850, 140), (950, 95),
        (1050, 170), (1150, 105),
    ]
    bx_offset = int(scroll * 0.2) % SW
    for bx, bh in building_data:
        rx = (bx - bx_offset) % SW
        rect = pygame.Rect(rx, HORIZON_Y + 60 - bh, 80, bh + 10)
        pygame.draw.rect(surf, (15, 15, 40), rect)
        # windows
        for wy in range(rect.top + 10, rect.bottom - 10, 20):
            for wxi in range(rect.left + 5, rect.right - 10, 18):
                if (wxi // 18 + wy // 20 + int(scroll * 0.001)) % 3 != 0:
                    pygame.draw.rect(surf, (200, 180, 60), (wxi, wy, 10, 8))


def draw_track(surf):
    # Ground below horizon
    ground_rect = pygame.Rect(0, HORIZON_Y + 60, SW, SH - HORIZON_Y - 60)
    pygame.draw.rect(surf, TRACK_MID, ground_rect)

    # Rail lines (perspective)
    # Left boundary of left lane → vanish
    # Right boundary of right lane → vanish
    vp = (VANISH_X, VANISH_Y)

    lines = [
        (LANE_LEFT_EDGE[0], GROUND_Y),
        (LANE_RIGHT_EDGE[0], GROUND_Y),
        (LANE_LEFT_EDGE[1], GROUND_Y),
        (LANE_RIGHT_EDGE[1], GROUND_Y),
        (LANE_LEFT_EDGE[2], GROUND_Y),
        (LANE_RIGHT_EDGE[2], GROUND_Y),
    ]
    for lx, ly in lines:
        pygame.draw.line(surf, RAIL_COLOR, (lx, ly), vp, 2)

    # Cross-ties (perspective, scrolling)
    pass  # optional: add ties for polish


def draw_track_fill(surf):
    # Dark track surface between lanes
    vp = (VANISH_X, VANISH_Y)
    # Fill the trapezoid
    pts = [
        (LANE_LEFT_EDGE[0], GROUND_Y),
        (LANE_RIGHT_EDGE[2], GROUND_Y),
        (VANISH_X + 20, VANISH_Y + 5),
        (VANISH_X - 20, VANISH_Y + 5),
    ]
    pygame.draw.polygon(surf, TRACK_DARK, pts)


# ── Game states ────────────────────────────────────────────────────────────────

STATE_WAITING   = 'waiting'
STATE_CONNECTED = 'connected'
STATE_READY     = 'ready'
STATE_PLAYING   = 'playing'
STATE_PAUSED    = 'paused'
STATE_GAME_OVER = 'gameover'


class GameEngine:
    def __init__(self, cmd_q: queue.Queue, state_q: queue.Queue):
        self.cmd_q = cmd_q
        self.state_q = state_q

        self.state = STATE_WAITING
        self.pair_code = None
        self.pair_ip = None
        self.pair_qr_data = None
        self.username = None

        self.player = Player()
        self.obstacles: list[Obstacle] = []
        self.coins: list[Coin] = []
        self.scroll = 0.0
        self.speed = 0.35      # depth units per second
        self.speed_max = 1.0
        self.score = 0
        self.coin_count = 0
        self.elapsed = 0.0
        self.lives = 3
        self._last_obs = 0.0
        self._next_obs_interval = 2.0
        self._last_coin_row = 0.0

        self._font_large = None
        self._font_med = None
        self._font_small = None
        self._qr_surf = None

    # ── Setup ──────────────────────────────────────────────────────────────────

    def _init_fonts(self):
        pygame.font.init()
        self._font_large = pygame.font.SysFont('arial', 54, bold=True)
        self._font_med   = pygame.font.SysFont('arial', 36, bold=True)
        self._font_small = pygame.font.SysFont('arial', 24)

    def _build_qr_surface(self):
        if not self.pair_qr_data:
            return
        try:
            import qrcode
            qr = qrcode.QRCode(box_size=5, border=2)
            qr.add_data(self.pair_qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color='black', back_color='white')
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            self._qr_surf = pygame.image.load(buf)
        except Exception:
            self._qr_surf = None

    # ── Main loop ──────────────────────────────────────────────────────────────

    def run(self):
        pygame.init()
        screen = pygame.display.set_mode((SW, SH))
        pygame.display.set_caption('Subway Surfers')
        clock = pygame.time.Clock()
        self._init_fonts()

        running = True
        prev_time = time.time()

        while running:
            now = time.time()
            dt = min(now - prev_time, 0.05)
            prev_time = now

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                # Keyboard for testing without phone
                if event.type == pygame.KEYDOWN:
                    self._handle_key(event.key)

            self._process_queue()
            self._update(dt)
            self._draw(screen)
            pygame.display.flip()
            clock.tick(FPS)

        pygame.quit()

    def _handle_key(self, key):
        """Keyboard testing shortcuts."""
        km = {
            pygame.K_LEFT:  'move_left',
            pygame.K_RIGHT: 'move_right',
            pygame.K_UP:    'jump',
            pygame.K_DOWN:  'duck',
            pygame.K_SPACE: 'start',
            pygame.K_p:     'pause',
            pygame.K_r:     'resume',
        }
        if key in km:
            self._apply_cmd(km[key])

    # ── Queue processing ───────────────────────────────────────────────────────

    def _process_queue(self):
        while not self.cmd_q.empty():
            try:
                msg = self.cmd_q.get_nowait()
            except queue.Empty:
                break
            mtype = msg.get('type')
            if mtype == 'pair_info':
                self.pair_code = msg.get('code')
                self.pair_ip = msg.get('ip')
                self.pair_qr_data = msg.get('qr_data')
                self._build_qr_surface()
            elif mtype == 'phone_connected':
                self.username = msg.get('username')
                self.state = STATE_CONNECTED
            elif mtype == 'phone_disconnected':
                if self.state == STATE_PLAYING:
                    self.state = STATE_PAUSED
                self.username = None
            elif mtype == 'game_cmd':
                self._apply_cmd(msg.get('cmd'))

    def _apply_cmd(self, cmd):
        if cmd == 'start':
            if self.state in (STATE_CONNECTED, STATE_READY, STATE_GAME_OVER):
                self._start_game()
        elif cmd == 'pause':
            if self.state == STATE_PLAYING:
                self.state = STATE_PAUSED
        elif cmd == 'resume':
            if self.state == STATE_PAUSED:
                self.state = STATE_PLAYING
        elif cmd == 'ready':
            if self.state == STATE_CONNECTED:
                self.state = STATE_READY
        elif self.state == STATE_PLAYING:
            if cmd == 'jump':
                self.player.jump()
            elif cmd == 'duck':
                self.player.duck(True)
            elif cmd == 'unduck':
                self.player.duck(False)
            elif cmd == 'move_left':
                self.player.move_left()
            elif cmd == 'move_right':
                self.player.move_right()

    def _start_game(self):
        self.player = Player()
        self.obstacles = []
        self.coins = []
        self.score = 0
        self.coin_count = 0
        self.elapsed = 0.0
        self.speed = 0.35
        self.lives = 3
        self._last_obs = -999
        self._last_coin_row = -999
        self.state = STATE_PLAYING

    # ── Update ─────────────────────────────────────────────────────────────────

    def _update(self, dt):
        if self.state != STATE_PLAYING:
            return

        self.elapsed += dt
        self.scroll += dt * 300
        self.speed = min(self.speed_max, 0.35 + self.elapsed * 0.008)
        self.score = int(self.elapsed * 10 + self.coin_count * 50)

        self.player.update(dt)

        # Spawn obstacles
        if self.elapsed - self._last_obs > self._next_obs_interval:
            self._spawn_obstacle()
            self._last_obs = self.elapsed
            self._next_obs_interval = random.uniform(1.5, 3.5)

        # Spawn coin rows
        if self.elapsed - self._last_coin_row > 0.8:
            self._spawn_coins()
            self._last_coin_row = self.elapsed

        # Update & cull
        for o in self.obstacles:
            o.update(self.speed, dt)
        for c in self.coins:
            c.update(self.speed, dt)
        self.obstacles = [o for o in self.obstacles if not o.dead]
        self.coins = [c for c in self.coins if not c.dead]

        self._check_collisions()
        self._push_state()

    def _spawn_obstacle(self):
        kind = random.choice([OBSTACLE_TRAIN, OBSTACLE_BARRIER, OBSTACLE_BAR,
                               OBSTACLE_BARRIER, OBSTACLE_TRAIN])
        if kind == OBSTACLE_TRAIN:
            lane = random.randint(0, 2)
        else:
            lane = random.randint(0, 2)
        self.obstacles.append(Obstacle(lane, 0.95, kind))

    def _spawn_coins(self):
        lane = random.randint(0, 2)
        count = random.randint(3, 6)
        base_depth = random.uniform(0.6, 0.9)
        for i in range(count):
            d = base_depth - i * 0.04
            if d > 0.05:
                self.coins.append(Coin(lane, max(0.1, d)))

    def _check_collisions(self):
        player_lane = self.player.get_lane_for_collision()
        py_off = self.player.get_y_offset()
        player_height_norm = py_off / PLAYER_H  # 0 = on ground, 1 = full jump
        is_ducking = self.player.ducking

        for obs in self.obstacles:
            if obs.depth > 0.08 or obs.depth < -0.02:
                continue
            o_lane, depth_range, (h_min, h_max) = obs.get_hitbox()
            if o_lane != player_lane:
                continue
            # Check height collision
            if obs.kind == OBSTACLE_BARRIER:
                # Must jump over — collision if not high enough
                if player_height_norm < 0.45:
                    if self.player.hit():
                        self._on_hit()
            elif obs.kind == OBSTACLE_BAR:
                # Must duck — collision if not ducking
                if not is_ducking:
                    if self.player.hit():
                        self._on_hit()
            elif obs.kind == OBSTACLE_TRAIN:
                # Any height, must be in different lane
                if self.player.hit():
                    self._on_hit()

        # Coin collection
        for c in self.coins:
            if c.collected:
                continue
            if c.depth < 0.08 and c.depth > -0.02 and c.lane == player_lane:
                c.collected = True
                self.coin_count += 1

    def _on_hit(self):
        self.lives -= 1
        if self.lives <= 0:
            self.state = STATE_GAME_OVER
            self._push_game_over()

    def _push_state(self):
        msg = {
            'type': 'game_state',
            'state': self.state,
            'score': self.score,
            'time': round(self.elapsed, 1),
            'lives': self.lives,
        }
        try:
            self.state_q.put_nowait(msg)
        except queue.Full:
            pass

    def _push_game_over(self):
        msg = {
            'type': 'game_over',
            'score': self.score,
            'time': round(self.elapsed, 1),
            'coins': self.coin_count,
        }
        try:
            self.state_q.put_nowait(msg)
        except queue.Full:
            pass

    # ── Drawing ────────────────────────────────────────────────────────────────

    def _draw(self, surf):
        surf.fill(SKY_TOP)
        if self.state == STATE_WAITING:
            self._draw_waiting(surf)
        elif self.state == STATE_CONNECTED:
            self._draw_connected(surf)
        elif self.state == STATE_READY:
            self._draw_ready(surf)
        elif self.state == STATE_PLAYING:
            self._draw_game(surf)
        elif self.state == STATE_PAUSED:
            self._draw_game(surf)
            self._draw_pause_overlay(surf)
        elif self.state == STATE_GAME_OVER:
            self._draw_game(surf)
            self._draw_game_over_overlay(surf)

    def _draw_waiting(self, surf):
        draw_background(surf, self.scroll)
        draw_track_fill(surf)
        draw_track(surf)

        cx, cy = SW // 2, SH // 2
        self._draw_panel(surf, cx, cy - 80, 700, 460)

        title = self._font_large.render('SUBWAY SURFERS', True, YELLOW)
        surf.blit(title, title.get_rect(center=(cx, cy - 200)))

        if self.pair_code:
            t1 = self._font_med.render('Scan QR or enter code on phone:', True, WHITE)
            surf.blit(t1, t1.get_rect(center=(cx, cy - 110)))

            code_surf = self._font_large.render(self.pair_code, True, YELLOW)
            surf.blit(code_surf, code_surf.get_rect(center=(cx + (180 if self._qr_surf else 0), cy - 40)))

            if self.pair_ip:
                ip_t = self._font_small.render(f'Server IP: {self.pair_ip}:8765', True, GRAY)
                surf.blit(ip_t, ip_t.get_rect(center=(cx, cy + 40)))

            if self._qr_surf:
                qr_rect = self._qr_surf.get_rect(center=(cx - 160, cy - 10))
                surf.blit(self._qr_surf, qr_rect)
        else:
            wait_t = self._font_med.render('Starting server…', True, WHITE)
            surf.blit(wait_t, wait_t.get_rect(center=(cx, cy)))

    def _draw_connected(self, surf):
        draw_background(surf, self.scroll)
        draw_track_fill(surf)
        draw_track(surf)
        cx, cy = SW // 2, SH // 2
        self._draw_panel(surf, cx, cy, 500, 220)
        user_t = self._font_med.render(f'Player: {self.username}', True, GREEN)
        surf.blit(user_t, user_t.get_rect(center=(cx, cy - 60)))
        wait_t = self._font_med.render('Waiting for player to get ready…', True, WHITE)
        surf.blit(wait_t, wait_t.get_rect(center=(cx, cy)))
        hint_t = self._font_small.render('Press START on the phone when in position', True, GRAY)
        surf.blit(hint_t, hint_t.get_rect(center=(cx, cy + 55)))

    def _draw_ready(self, surf):
        draw_background(surf, self.scroll)
        draw_track_fill(surf)
        draw_track(surf)
        cx, cy = SW // 2, SH // 2
        self._draw_panel(surf, cx, cy, 500, 200)
        r_t = self._font_large.render('READY!', True, GREEN)
        surf.blit(r_t, r_t.get_rect(center=(cx, cy - 50)))
        hint_t = self._font_med.render('Press START to begin', True, WHITE)
        surf.blit(hint_t, hint_t.get_rect(center=(cx, cy + 30)))

    def _draw_game(self, surf):
        draw_background(surf, self.scroll)
        draw_track_fill(surf)
        draw_track(surf)

        # Sort by depth (far first)
        all_objs = (
            sorted(self.obstacles, key=lambda o: o.depth, reverse=True) +
            sorted(self.coins, key=lambda c: c.depth, reverse=True)
        )
        for obj in all_objs:
            obj.draw(surf)

        self.player.draw(surf)
        self._draw_hud(surf)

    def _draw_hud(self, surf):
        hud_surf = pygame.Surface((SW, 60), pygame.SRCALPHA)
        hud_surf.fill((0, 0, 0, 140))
        surf.blit(hud_surf, (0, 0))

        score_t = self._font_med.render(f'Score: {self.score}', True, YELLOW)
        surf.blit(score_t, (20, 10))

        mins = int(self.elapsed // 60)
        secs = int(self.elapsed % 60)
        time_t = self._font_med.render(f'Time: {mins:02d}:{secs:02d}', True, WHITE)
        surf.blit(time_t, time_t.get_rect(midtop=(SW // 2, 10)))

        # Lives
        for i in range(3):
            color = RED if i < self.lives else DARK_GRAY
            pygame.draw.circle(surf, color, (SW - 30 - i * 35, 30), 12)

        coins_t = self._font_small.render(f'× {self.coin_count}', True, COIN_COLOR)
        pygame.draw.circle(surf, COIN_COLOR, (SW - 150, 30), 10)
        surf.blit(coins_t, (SW - 135, 20))

    def _draw_pause_overlay(self, surf):
        overlay = pygame.Surface((SW, SH), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        surf.blit(overlay, (0, 0))
        cx, cy = SW // 2, SH // 2
        p_t = self._font_large.render('PAUSED', True, WHITE)
        surf.blit(p_t, p_t.get_rect(center=(cx, cy - 40)))
        r_t = self._font_med.render('Resume on phone or press R', True, GRAY)
        surf.blit(r_t, r_t.get_rect(center=(cx, cy + 30)))

    def _draw_game_over_overlay(self, surf):
        overlay = pygame.Surface((SW, SH), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surf.blit(overlay, (0, 0))
        cx, cy = SW // 2, SH // 2
        self._draw_panel(surf, cx, cy, 480, 320)

        go_t = self._font_large.render('GAME OVER', True, RED)
        surf.blit(go_t, go_t.get_rect(center=(cx, cy - 120)))

        sc_t = self._font_med.render(f'Score: {self.score}', True, YELLOW)
        surf.blit(sc_t, sc_t.get_rect(center=(cx, cy - 50)))

        mins = int(self.elapsed // 60)
        secs = int(self.elapsed % 60)
        ti_t = self._font_med.render(f'Time: {mins:02d}:{secs:02d}', True, WHITE)
        surf.blit(ti_t, ti_t.get_rect(center=(cx, cy + 10)))

        co_t = self._font_med.render(f'Coins: {self.coin_count}', True, COIN_COLOR)
        surf.blit(co_t, co_t.get_rect(center=(cx, cy + 70)))

        re_t = self._font_small.render('Press START on phone to play again', True, GRAY)
        surf.blit(re_t, re_t.get_rect(center=(cx, cy + 130)))

    def _draw_panel(self, surf, cx, cy, w, h):
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((20, 20, 40, 200))
        pygame.draw.rect(panel, (80, 80, 120, 200), (0, 0, w, h), 2, border_radius=12)
        surf.blit(panel, (cx - w // 2, cy - h // 2))
