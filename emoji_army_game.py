#!/usr/bin/env python3
"""
Emoji Army Conquest Game v2
===========================
Improved with unit types, smarter combat, recruitment animations,
death effects, XP/leveling, formations, and enhanced enemy AI.

Controls:
  WASD / Arrow Keys  - Move player
  Q                  - Toggle Attack mode (army attacks nearest enemies)
  E                  - Toggle Group mode (army follows player & regenerates)
  F                  - Force-recruit nearby (bypass willingness timer)
  SPACE              - Dash / sprint
  TAB                - Toggle minimap
  R                  - Restart game
  ESC                - Quit

Requirements:
  pip install pygame
"""

import pygame
import random
import math
import sys

# ─── CONSTANTS ───────────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = 1200, 800
WORLD_W, WORLD_H = 5000, 5000
TILE = 40
GRID_COLS = WORLD_W // TILE
GRID_ROWS = WORLD_H // TILE
FPS = 60
PLAYER_SPEED = 3.5
DASH_SPEED = 7.0
RECRUIT_RADIUS = 100
ATTACK_RADIUS = 280
GROUP_RADIUS = 65
BASE_UNIT_SPEED = 2.2
BASE_ENEMY_SPEED = 1.5
BASE_COMBAT_RANGE = 25
PLAYER_DAMAGE = 3
HP_PLAYER = 200
FRIENDLY_CAMP_COUNT = 7
ENEMY_BASE_COUNT = 5
INITIAL_FRIENDLIES = 50
ENEMY_SPAWN_INTERVAL = 200
MAX_ENEMIES_PER_BASE = 10
CAMERA_LERP = 0.08
MAX_ARMY_SIZE = 60
UNIT_HP_REGEN = 0.08  # per frame in group mode
XP_PER_KILL = 15
XP_TO_LEVEL = 60

# ─── UNIT TYPE DEFINITIONS ───────────────────────────────────────────────────
UNIT_TYPES = {
    'warrior': {
        'emoji': '⚔', 'emoji_size': 24,
        'hp': 70, 'damage': 12, 'speed': 2.4, 'range': 28,
        'attack_cd': 22, 'color': (220, 180, 50), 'name': 'Warrior',
        'desc': 'Balanced fighter',
    },
    'archer': {
        'emoji': '🏹', 'emoji_size': 24,
        'hp': 45, 'damage': 9, 'speed': 2.0, 'range': 80,
        'attack_cd': 30, 'color': (50, 200, 100), 'name': 'Archer',
        'desc': 'Ranged attacker',
    },
    'tank': {
        'emoji': '🛡', 'emoji_size': 24,
        'hp': 120, 'damage': 7, 'speed': 1.5, 'range': 24,
        'attack_cd': 30, 'color': (100, 150, 255), 'name': 'Tank',
        'desc': 'High HP, slow',
    },
    'scout': {
        'emoji': '🗡', 'emoji_size': 24,
        'hp': 40, 'damage': 8, 'speed': 3.2, 'range': 22,
        'attack_cd': 14, 'color': (255, 150, 50), 'name': 'Scout',
        'desc': 'Fast attacker',
    },
}

NEUTRAL_TYPE_WEIGHTS = {'warrior': 35, 'archer': 25, 'tank': 20, 'scout': 20}

ENEMY_TYPES = {
    'grunt': {
        'emoji': '💀', 'emoji_size': 22,
        'hp': 45, 'damage': 6, 'speed': 1.6, 'range': 24,
        'attack_cd': 35, 'color': (200, 60, 60), 'name': 'Grunt',
        'xp_value': 10,
    },
    'elite': {
        'emoji': '👿', 'emoji_size': 26,
        'hp': 100, 'damage': 14, 'speed': 1.3, 'range': 30,
        'attack_cd': 28, 'color': (200, 40, 200), 'name': 'Elite',
        'xp_value': 30,
    },
    'boss': {
        'emoji': '👹', 'emoji_size': 32,
        'hp': 250, 'damage': 22, 'speed': 1.1, 'range': 32,
        'attack_cd': 40, 'color': (255, 100, 0), 'name': 'Boss',
        'xp_value': 80,
    },
}
ENEMY_TYPE_WEIGHTS = {'grunt': 60, 'elite': 30, 'boss': 10}

# ─── COLORS ───────────────────────────────────────────────────────────────────
C_GRASS      = (76, 153, 0)
C_GRASS2     = (82, 148, 20)
C_GRASS3     = (68, 138, 10)
C_WATER      = (30, 100, 200)
C_HP_GREEN   = (0, 220, 60)
C_HP_RED     = (220, 30, 30)
C_HP_YELLOW  = (220, 200, 30)
C_ATTACK_CLR = (255, 80, 80)
C_GROUP_CLR  = (80, 200, 255)
C_CRIT_COLOR = (255, 255, 0)
C_KNOCKBACK  = (255, 140, 60)

# ─── EMOJI CACHE ──────────────────────────────────────────────────────────────
EMOJI_FONT_PATH = "/usr/share/fonts/truetype/emoji/NotoColorEmoji.ttf"
emoji_cache: dict[str, pygame.Surface] = {}

def load_emoji(char: str, size: int = 28) -> pygame.Surface:
    key = f"{char}_{size}"
    if key not in emoji_cache:
        font = pygame.font.Font(EMOJI_FONT_PATH, size)
        emoji_cache[key] = font.render(char, True, (255, 255, 255))
    return emoji_cache[key]

def weighted_random(weights: dict) -> str:
    total = sum(weights.values())
    r = random.uniform(0, total)
    cumulative = 0
    for key, weight in weights.items():
        cumulative += weight
        if r <= cumulative:
            return key
    return list(weights.keys())[0]

# ─── PROCEDURAL WORLD ─────────────────────────────────────────────────────────
class World:
    def __init__(self):
        self.tiles: list[list[int]] = []
        self._generate()

    def _simple_noise(self, x, y, scale=8):
        nx, ny = x / scale, y / scale
        ix, iy = int(nx), int(ny)
        fx, fy = nx - ix, ny - iy
        fx = fx * fx * (3 - 2 * fx)
        fy = fy * fy * (3 - 2 * fy)
        def h(a, b):
            return (((a * 374761393 + b * 668265263) & 0xFFFFFFFF) % 10000) / 10000.0
        v00, v10 = h(ix, iy), h(ix+1, iy)
        v01, v11 = h(ix, iy+1), h(ix+1, iy+1)
        return v00*(1-fx)*(1-fy) + v10*fx*(1-fy) + v01*(1-fx)*fy + v11*fx*fy

    def _generate(self):
        self.tiles = [[0]*GRID_COLS for _ in range(GRID_ROWS)]
        water_seeds = [(random.randint(5, GRID_COLS-10), random.randint(5, GRID_ROWS-10))
                       for _ in range(12)]
        for wy, wx in water_seeds:
            cx, cy = wx, wy
            radius = random.randint(2, 5)
            for dy in range(-radius-1, radius+2):
                for dx in range(-radius-1, radius+2):
                    ny, nx = cy+dy, cx+dx
                    if 0 <= ny < GRID_ROWS and 0 <= nx < GRID_COLS:
                        dist = math.sqrt(dx*dx + dy*dy)
                        if dist < radius + random.random()*1.5:
                            self.tiles[ny][nx] = 2
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                if self.tiles[row][col] == 2:
                    continue
                n = self._simple_noise(col, row, 6)
                if n > 0.72 and random.random() < 0.6:
                    self.tiles[row][col] = 1
        cx, cy = GRID_COLS // 2, GRID_ROWS // 2
        for dy in range(-6, 7):
            for dx in range(-6, 7):
                ny, nx = cy+dy, cx+dx
                if 0 <= ny < GRID_ROWS and 0 <= nx < GRID_COLS:
                    self.tiles[ny][nx] = 0

    def is_blocked(self, x, y, radius=12):
        col = int(x // TILE)
        row = int(y // TILE)
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                r, c = row + dy, col + dx
                if 0 <= r < GRID_ROWS and 0 <= c < GRID_COLS:
                    if self.tiles[r][c] == 2:
                        tile_left = c * TILE
                        tile_top = r * TILE
                        closest_x = max(tile_left, min(x, tile_left + TILE))
                        closest_y = max(tile_top, min(y, tile_top + TILE))
                        dist = math.sqrt((x - closest_x)**2 + (y - closest_y)**2)
                        if dist < radius:
                            return True
                    if self.tiles[r][c] == 1:
                        px = c * TILE + TILE // 2
                        py = r * TILE + TILE // 2
                        dist = math.sqrt((x - px)**2 + (y - py)**2)
                        if dist < radius + 8:
                            return True
        return False

    def find_open_pos(self, region=None):
        for _ in range(500):
            if region:
                rx, ry, rw, rh = region
                x = random.randint(rx, rx + rw)
                y = random.randint(ry, ry + rh)
            else:
                x = random.randint(50, WORLD_W - 50)
                y = random.randint(50, WORLD_H - 50)
            col = int(x // TILE)
            row = int(y // TILE)
            if 0 <= row < GRID_ROWS and 0 <= col < GRID_COLS:
                if self.tiles[row][col] == 0:
                    return x, y
        return WORLD_W // 2, WORLD_H // 2


class Camera:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0

    def update(self, target_x, target_y):
        desired_x = target_x - SCREEN_W / 2
        desired_y = target_y - SCREEN_H / 2
        self.x += (desired_x - self.x) * CAMERA_LERP
        self.y += (desired_y - self.y) * CAMERA_LERP
        self.x = max(0, min(WORLD_W - SCREEN_W, self.x))
        self.y = max(0, min(WORLD_H - SCREEN_H, self.y))

    def apply(self, x, y):
        return x - self.x, y - self.y

    def visible(self, x, y, margin=80):
        sx, sy = self.apply(x, y)
        return -margin < sx < SCREEN_W + margin and -margin < sy < SCREEN_H + margin


class Particle:
    __slots__ = ('x','y','vx','vy','life','max_life','color','text','size')
    def __init__(self, x, y, color, text=None, life=40, size=0):
        self.x, self.y = x, y
        self.vx = random.uniform(-1.5, 1.5)
        self.vy = random.uniform(-2.5, -0.3)
        self.life = life
        self.max_life = life
        self.color = color
        self.text = text
        self.size = size


class Corpse:
    __slots__ = ('x','y','emoji_key','color','timer','max_timer','fade')
    def __init__(self, x, y, emoji_key, color, duration=120):
        self.x, self.y = x, y
        self.emoji_key = emoji_key
        self.color = color
        self.timer = duration
        self.max_timer = duration
        self.fade = 255

    def update(self):
        self.timer -= 1
        self.fade = max(0, int(255 * (self.timer / self.max_timer)))
        return self.timer > 0


class Pickup:
    __slots__ = ('x','y','pickup_type','timer','max_timer')
    def __init__(self, x, y, pickup_type='heart'):
        self.x, self.y = x + random.randint(-15,15), y + random.randint(-15,15)
        self.pickup_type = pickup_type  # 'heart', 'star', 'medal'
        self.timer = 480  # 8 seconds to grab
        self.max_timer = 480


class Unit:
    __slots__ = ('x','y','vx','vy','hp','max_hp','speed','team','recruited',
                 'unit_type','enemy_type','attack_target','attack_cd',
                 'recruit_anim','dead','recruit_timer','willingness',
                 'level','xp','knockback_vx','knockback_vy','stun_timer',
                 'retreating','facing_angle','alive_timer','is_leading')
    def __init__(self, x, y, team='friendly', recruited=False,
                 unit_type=None, enemy_type=None):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = 0.0, 0.0
        self.team = team
        self.recruited = recruited
        self.dead = False
        self.recruit_timer = 0
        self.recruit_anim = 0
        self.willingness = random.uniform(20, 80)  # frames until willing
        self.level = 1
        self.xp = 0
        self.knockback_vx = 0.0
        self.knockback_vy = 0.0
        self.stun_timer = 0
        self.retreating = False
        self.facing_angle = random.uniform(0, 2*math.pi)
        self.alive_timer = 0
        self.is_leading = False

        if team == 'friendly':
            self.unit_type = unit_type or weighted_random(NEUTRAL_TYPE_WEIGHTS)
            self.enemy_type = None
            stats = UNIT_TYPES[self.unit_type]
            self.hp = stats['hp']
            self.max_hp = stats['hp']
            self.speed = stats['speed']
            self.attack_cd = 0
        else:
            self.unit_type = None
            self.enemy_type = enemy_type or weighted_random(ENEMY_TYPE_WEIGHTS)
            stats = ENEMY_TYPES[self.enemy_type]
            self.hp = stats['hp']
            self.max_hp = stats['hp']
            self.speed = stats['speed']
            self.attack_cd = 0

    @property
    def damage(self):
        if self.team == 'friendly' and self.unit_type:
            base = UNIT_TYPES[self.unit_type]['damage']
        elif self.enemy_type:
            base = ENEMY_TYPES[self.enemy_type]['damage']
        else:
            base = 5
        level_bonus = 1 + (self.level - 1) * 0.15
        return base * level_bonus

    @property
    def combat_range(self):
        if self.team == 'friendly' and self.unit_type:
            return UNIT_TYPES[self.unit_type]['range']
        elif self.enemy_type:
            return ENEMY_TYPES[self.enemy_type]['range']
        return BASE_COMBAT_RANGE

    @property
    def base_attack_cd(self):
        if self.team == 'friendly' and self.unit_type:
            return UNIT_TYPES[self.unit_type]['attack_cd']
        elif self.enemy_type:
            return ENEMY_TYPES[self.enemy_type]['attack_cd']
        return 25

    def gain_xp(self, amount):
        self.xp += amount
        while self.xp >= XP_TO_LEVEL * self.level:
            self.xp -= XP_TO_LEVEL * self.level
            self.level += 1
            self.max_hp = int(self.max_hp * 1.12)
            self.hp = min(self.hp + int(self.max_hp * 0.3), self.max_hp)
            return True  # leveled up
        return False

    def hp_pct(self):
        return self.hp / self.max_hp if self.max_hp > 0 else 0


class Player:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.hp = HP_PLAYER
        self.max_hp = HP_PLAYER
        self.speed = PLAYER_SPEED
        self.dashing = False
        self.dash_timer = 0
        self.dash_cooldown = 0
        self.mode = 'group'
        self.recruit_flash = 0
        self.score = 0
        self.invincible = 0
        self.force_recruit_cooldown = 0
        self.combo = 0
        self.combo_timer = 0


class Camp:
    def __init__(self, x, y, team):
        self.x, self.y = x, y
        self.team = team
        self.spawn_timer = 0
        self.max_units = MAX_ENEMIES_PER_BASE


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("⚔️ Emoji Army Conquest v2 ⚔️")
        self.clock = pygame.time.Clock()
        self.font_sm = pygame.font.Font(None, 22)
        self.font_md = pygame.font.Font(None, 28)
        self.font_lg = pygame.font.Font(None, 42)
        self.font_xl = pygame.font.Font(None, 56)
        self.font_tiny = pygame.font.Font(None, 18)

        self.emoji = {
            'player':       load_emoji('🤺', 30),
            'tree':          load_emoji('🌳', 36),
            'water':         load_emoji('🌊', 30),
            'camp_friendly': load_emoji('🏕', 36),
            'camp_enemy':    load_emoji('🏰', 40),
            'neutral':       load_emoji('👤', 22),
            'recruit':       load_emoji('✨', 20),
            'heart':         load_emoji('❤', 18),
            'crown':         load_emoji('👑', 24),
            'skull':         load_emoji('☠', 28),
            'star':          load_emoji('⭐', 16),
            'fire':          load_emoji('🔥', 18),
            'medal':         load_emoji('🎖', 22),
            'shield':        load_emoji('🛡', 20),
            'sword':         load_emoji('⚔', 20),
            'levelup':       load_emoji('🆙', 22),
            'sparkle':       load_emoji('💎', 18),
        }
        # Pre-load unit type emojis
        for ut in UNIT_TYPES.values():
            self.emoji[f"unit_{ut['emoji']}_{ut['emoji_size']}"] = load_emoji(ut['emoji'], ut['emoji_size'])
        for et in ENEMY_TYPES.values():
            self.emoji[f"enemy_{et['emoji']}_{et['emoji_size']}"] = load_emoji(et['emoji'], et['emoji_size'])

        self._init_game()

    def _init_game(self):
        self.world = World()
        self.camera = Camera()
        self.player = Player(WORLD_W // 2, WORLD_H // 2)
        self.units: list[Unit] = []
        self.particles: list[Particle] = []
        self.corpses: list[Corpse] = []
        self.pickups: list[Pickup] = []
        self.camps: list[Camp] = []
        self.frame = 0
        self.show_minimap = True
        self.game_over = False
        self.game_won = False
        self.total_enemies_defeated = 0
        self.total_recruited = 0
        self.combo_high = 0

        for _ in range(FRIENDLY_CAMP_COUNT):
            cx, cy = self.world.find_open_pos()
            self.camps.append(Camp(cx, cy, 'friendly'))
            for _ in range(random.randint(4, 8)):
                ux, uy = self._random_pos_near(cx, cy, 60, 200)
                self.units.append(Unit(ux, uy, 'friendly', recruited=False))

        for _ in range(INITIAL_FRIENDLIES - FRIENDLY_CAMP_COUNT * 6):
            x, y = self.world.find_open_pos()
            self.units.append(Unit(x, y, 'friendly', recruited=False))

        for _ in range(ENEMY_BASE_COUNT):
            cx, cy = self.world.find_open_pos()
            self.camps.append(Camp(cx, cy, 'enemy'))
            for _ in range(random.randint(4, 6)):
                ex, ey = self._random_pos_near(cx, cy, 40, 120)
                self.units.append(Unit(ex, ey, 'enemy'))

    def _random_pos_near(self, cx, cy, min_d, max_d):
        for _ in range(50):
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(min_d, max_d)
            x = cx + math.cos(angle) * dist
            y = cy + math.sin(angle) * dist
            x = max(20, min(WORLD_W - 20, x))
            y = max(20, min(WORLD_H - 20, y))
            if not self.world.is_blocked(x, y, 10):
                return x, y
        return cx + random.randint(min_d, max_d), cy + random.randint(min_d, max_d)

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_q:
                        self.player.mode = 'attack'
                        self._add_particles(self.player.x, self.player.y - 30,
                                            (255, 80, 80), '⚔', 20)
                    elif event.key == pygame.K_e:
                        self.player.mode = 'group'
                        self._add_particles(self.player.x, self.player.y - 30,
                                            (80, 200, 255), '🛡', 20)
                    elif event.key == pygame.K_TAB:
                        self.show_minimap = not self.show_minimap
                    elif event.key == pygame.K_r:
                        self._init_game()
                    elif event.key == pygame.K_SPACE and self.player.dash_cooldown <= 0:
                        self.player.dashing = True
                        self.player.dash_timer = 18
                        self.player.dash_cooldown = 50
                    elif event.key == pygame.K_f:
                        self.player.force_recruit_cooldown = 90
                elif event.type == pygame.KEYUP:
                    if event.key == pygame.K_SPACE:
                        self.player.dashing = False

            if not self.game_over and not self.game_won:
                self._update()

            self._draw()
            pygame.display.flip()
            self.frame += 1
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit()

    def _update(self):
        p = self.player

        # ── Player movement ────────────────────────────────────────────────
        keys = pygame.key.get_pressed()
        dx, dy = 0, 0
        if keys[pygame.K_w] or keys[pygame.K_UP]:    dy = -1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:   dy = 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:   dx = -1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:  dx = 1
        if dx != 0 and dy != 0:
            dx *= 0.707
            dy *= 0.707

        speed = DASH_SPEED if p.dashing and p.dash_timer > 0 else p.speed
        if p.dash_timer > 0:
            p.dash_timer -= 1
            if p.dash_timer <= 0:
                p.dashing = False
        if p.dash_cooldown > 0:
            p.dash_cooldown -= 1

        nx = p.x + dx * speed
        ny = p.y + dy * speed
        if not self.world.is_blocked(nx, p.y, 10): p.x = nx
        if not self.world.is_blocked(p.x, ny, 10): p.y = ny
        p.x = max(15, min(WORLD_W - 15, p.x))
        p.y = max(15, min(WORLD_H - 15, p.y))
        if p.invincible > 0: p.invincible -= 1
        if p.force_recruit_cooldown > 0: p.force_recruit_cooldown -= 1
        if p.combo_timer > 0:
            p.combo_timer -= 1
            if p.combo_timer <= 0:
                p.combo = 0
        if p.recruit_flash > 0: p.recruit_flash -= 1

        army_size = self._army_size()
        recruited = [u for u in self.units if not u.dead and u.recruited]
        enemies = [u for u in self.units if not u.dead and u.team == 'enemy']

        # ── Recruitment with staggered willingness ─────────────────────────
        for u in self.units:
            if u.dead or u.team != 'friendly' or u.recruited:
                continue
            dist = math.sqrt((p.x - u.x)**2 + (p.y - u.y)**2)
            in_range = dist < RECRUIT_RADIUS
            force = p.force_recruit_cooldown > 60  # first 30 frames of F

            if in_range:
                if force or u.recruit_timer > 0:
                    # Already in process of joining
                    u.recruit_timer += 1
                    # Walk toward player
                    self._move_toward(u, p.x, p.y, u.speed * 1.3)
                    # Join when close enough
                    if dist < 30 or (force and u.recruit_timer > 10) or u.recruit_timer > 40:
                        if army_size < MAX_ARMY_SIZE:
                            u.recruited = True
                            u.recruit_anim = 30
                            u.willingness = 0
                            p.recruit_flash = 15
                            self.total_recruited += 1
                            self._add_particles(u.x, u.y, (100, 200, 255), '✨', 25)
                            army_size += 1
                        else:
                            # Army full, bounce back
                            u.recruit_timer = 0
                            self._add_particles(u.x, u.y, (255, 100, 100), 'FULL', 20)
                else:
                    # Willingness check — some units join eagerly, some need time
                    u.willingness -= 1
                    # Draw connection line effect
                    if u.willingness <= 0:
                        u.recruit_timer = 1
                        self._add_particles(u.x, u.y, (100, 200, 255, 180), '', 8, size=3)
            else:
                u.recruit_timer = 0
                if u.willingness < 80:
                    u.willingness = min(80, u.willingness + 0.3)

        # ── Spawn enemies ─────────────────────────────────────────────────
        for camp in self.camps:
            if camp.team == 'enemy':
                nearby_enemies = sum(1 for u in enemies
                                     if math.sqrt((u.x-camp.x)**2+(u.y-camp.y)**2) < 300)
                if nearby_enemies < camp.max_units:
                    camp.spawn_timer += 1
                    if camp.spawn_timer >= ENEMY_SPAWN_INTERVAL:
                        camp.spawn_timer = 0
                        ex, ey = self._random_pos_near(camp.x, camp.y, 40, 120)
                        self.units.append(Unit(ex, ey, 'enemy'))

        # ── Update recruited units ────────────────────────────────────────
        self._update_army(recruited, enemies, p)

        # ── Update enemy AI ────────────────────────────────────────────────
        self._update_enemies(enemies, recruited, p)

        # ── Player auto-attack nearest enemy ──────────────────────────────
        for e in enemies:
            if e.dead: continue
            d = math.sqrt((p.x - e.x)**2 + (p.y - e.y)**2)
            if d < BASE_COMBAT_RANGE + 10:
                is_crit = random.random() < 0.15
                dmg = PLAYER_DAMAGE * (2.5 if is_crit else 1)
                e.hp -= dmg
                color = C_CRIT_COLOR if is_crit else (255, 255, 100)
                text = f"{int(dmg)}!" if is_crit else str(int(dmg))
                self._add_particles(e.x, e.y - 10, color, text, 18)
                self._apply_knockback(e, p.x, p.y, 3 if is_crit else 1.5)
                if e.hp <= 0:
                    self._kill_unit(e, p)
                break

        # ── Pickups ────────────────────────────────────────────────────────
        for pickup in self.pickups[:]:
            pickup.timer -= 1
            d = math.sqrt((p.x - pickup.x)**2 + (p.y - pickup.y)**2)
            if d < 35:
                if pickup.pickup_type == 'heart':
                    heal = 25
                    p.hp = min(p.max_hp, p.hp + heal)
                    self._add_particles(p.x, p.y - 20, (255, 80, 80), f"+{heal}HP", 20)
                elif pickup.pickup_type == 'star':
                    p.score += 50
                    self._add_particles(p.x, p.y - 20, (255, 255, 100), "+50", 20)
                elif pickup.pickup_type == 'medal':
                    p.score += 25
                    # Heal army a bit
                    for u in recruited:
                        u.hp = min(u.max_hp, u.hp + 10)
                    self._add_particles(p.x, p.y - 20, (100, 200, 255), "+25 Army Heal", 20)
                self.pickups.remove(pickup)
            elif pickup.timer <= 0:
                self.pickups.remove(pickup)

        # ── Base capture ─────────────────────────────────────────────────
        for camp in self.camps[:]:
            if camp.team == 'enemy':
                d = math.sqrt((p.x - camp.x)**2 + (p.y - camp.y)**2)
                nearby_e = [u for u in enemies
                            if not u.dead and math.sqrt((u.x-camp.x)**2+(u.y-camp.y)**2) < 200]
                if d < 50 and len(nearby_e) == 0:
                    camp.team = 'friendly'
                    p.score += 100
                    self._add_particles(camp.x, camp.y, (255, 215, 0), '👑', 40)
                    self._add_particles(camp.x, camp.y, (255, 255, 100), '⭐', 30)
                    # Spawn some friendly recruits at captured base
                    for _ in range(random.randint(2, 4)):
                        ux, uy = self._random_pos_near(camp.x, camp.y, 40, 100)
                        self.units.append(Unit(ux, uy, 'friendly', recruited=False))

        # ── Cooldowns, corpses, particles ─────────────────────────────────
        for u in self.units:
            if u.dead: continue
            if u.attack_cd > 0: u.attack_cd -= 1
            if u.recruit_anim > 0: u.recruit_anim -= 1
            if u.stun_timer > 0: u.stun_timer -= 1
            u.alive_timer += 1
            # Apply knockback
            if abs(u.knockback_vx) > 0.1 or abs(u.knockback_vy) > 0.1:
                kx = u.x + u.knockback_vx
                ky = u.y + u.knockback_vy
                if not self.world.is_blocked(kx, u.y, 8): u.x = kx
                if not self.world.is_blocked(u.x, ky, 8): u.y = ky
                u.knockback_vx *= 0.8
                u.knockback_vy *= 0.8
            else:
                u.knockback_vx = 0
                u.knockback_vy = 0

        # Update corpses
        self.corpses = [c for c in self.corpses if c.update()]

        # Clean dead units periodically
        if self.frame % 90 == 0:
            self.units = [u for u in self.units if not u.dead]

        # Update particles
        self.particles = [pt for pt in self.particles if pt.life > 0]
        for pt in self.particles:
            pt.x += pt.vx
            pt.y += pt.vy
            pt.vy += 0.02  # slight gravity
            pt.life -= 1

        self.camera.update(p.x, p.y)

        # Win check
        if not self.game_won:
            alive_bases = [c for c in self.camps if c.team == 'enemy']
            alive_enemies = [u for u in self.units if not u.dead and u.team == 'enemy']
            if not alive_bases and len(alive_enemies) == 0:
                self.game_won = True

    def _update_army(self, recruited, enemies, p):
        """Update army units with smart targeting, formations, retreat, and regen."""
        army_size = len(recruited)

        for u in recruited:
            if u.dead: continue
            if u.stun_timer > 0: continue

            # ── Retreat behavior for low HP ────────────────────────────
            if u.hp_pct() < 0.2 and not u.retreating:
                u.retreating = True
                self._add_particles(u.x, u.y - 10, C_HP_RED, 'RETREAT', 15)

            if u.retreating:
                # Run away from nearest enemy toward player
                nearest_enemy = None
                ne_dist = 150
                for e in enemies:
                    if e.dead: continue
                    d = math.sqrt((u.x - e.x)**2 + (u.y - e.y)**2)
                    if d < ne_dist:
                        nearest_enemy = e
                        ne_dist = d
                if nearest_enemy is None or ne_dist > 120:
                    u.retreating = False  # safe now
                else:
                    # Run opposite direction
                    dx = u.x - nearest_enemy.x
                    dy = u.y - nearest_enemy.y
                    dist = math.sqrt(dx*dx + dy*dy) + 0.01
                    flee_x = u.x + (dx/dist) * u.speed * 1.5
                    flee_y = u.y + (dy/dist) * u.speed * 1.5
                    self._move_toward(u, flee_x, flee_y, u.speed * 1.5)
                    continue

            # ── HP regeneration in group mode ──────────────────────────
            if p.mode == 'group':
                d_to_p = math.sqrt((u.x - p.x)**2 + (u.y - p.y)**2)
                if d_to_p < GROUP_RADIUS + 30:
                    u.hp = min(u.max_hp, u.hp + UNIT_HP_REGEN)

            # ── Combat logic ──────────────────────────────────────────
            if p.mode == 'attack':
                u.attack_target = None
                # Smart targeting: find the enemy with fewest allies already targeting it
                target_scores: dict[int, tuple] = {}  # unit_id -> (enemy, dist)
                enemy_target_count: dict = {}
                for other_u in recruited:
                    if other_u.attack_target and not other_u.attack_target.dead:
                        eid = id(other_u.attack_target)
                        enemy_target_count[eid] = enemy_target_count.get(eid, 0) + 1

                nearest = None
                nearest_dist = ATTACK_RADIUS
                best_score = -999

                for e in enemies:
                    if e.dead: continue
                    d = math.sqrt((u.x - e.x)**2 + (u.y - e.y)**2)
                    if d < nearest_dist:
                        # Score: prefer closer enemies, fewer allies targeting
                        eid = id(e)
                        allies_on = enemy_target_count.get(eid, 0)
                        score = -d + allies_on * (-40)  # discourage dogpiling
                        # Prioritize low-HP enemies for finish-off
                        if e.hp_pct() < 0.3:
                            score += 30
                        if score > best_score:
                            best_score = score
                            nearest = e
                            nearest_dist = d

                if nearest:
                    u.attack_target = nearest
                    effective_range = u.combat_range
                    if nearest_dist > effective_range:
                        self._move_toward(u, nearest.x, nearest.y, u.speed)
                    # Ranged units (archers) stop and shoot
                    if nearest_dist <= effective_range and u.attack_cd <= 0:
                        self._unit_attack(u, nearest, p)
                else:
                    # No enemy, follow player loosely
                    d_to_p = math.sqrt((u.x - p.x)**2 + (u.y - p.y)**2)
                    if d_to_p > GROUP_RADIUS + 40:
                        self._move_toward(u, p.x, p.y, u.speed * 0.7)

            elif p.mode == 'group':
                # Defend self if enemy is close
                closest_enemy = None
                ce_dist = 55
                for e in enemies:
                    if e.dead: continue
                    d = math.sqrt((u.x - e.x)**2 + (u.y - e.y)**2)
                    if d < ce_dist:
                        closest_enemy = e
                        ce_dist = d

                if closest_enemy and u.attack_cd <= 0:
                    u.attack_target = closest_enemy
                    self._unit_attack(u, closest_enemy, p)
                else:
                    u.attack_target = None
                    self._group_around(u, p, army_size)

    def _unit_attack(self, attacker, target, player):
        """Handle a unit attacking a target with crits, knockback, and XP."""
        is_crit = random.random() < 0.12
        dmg = attacker.damage * (2.0 if is_crit else 1.0)
        target.hp -= dmg
        attacker.attack_cd = attacker.base_attack_cd

        # Update facing angle
        attacker.facing_angle = math.atan2(target.y - attacker.y, target.x - attacker.x)

        # Visual effects
        color = C_CRIT_COLOR if is_crit else (255, 100, 50)
        text = f"{int(dmg)}!" if is_crit else str(int(dmg))
        self._add_particles(target.x, target.y - 10, color, text, 18)

        if is_crit:
            self._add_particles(target.x, target.y, (255, 255, 100), '', 8, size=4)
            self._apply_knockback(target, attacker.x, attacker.y, 4)
        else:
            self._apply_knockback(target, attacker.x, attacker.y, 1.5)

        # Archer projectile visual
        if attacker.unit_type == 'archer' and attacker.recruited:
            self._spawn_projectile_particles(attacker.x, attacker.y, target.x, target.y)

        if target.hp <= 0:
            self._kill_unit(target, player)
            if attacker.recruited:
                xp = target.xp_value if hasattr(target, 'xp_value') else XP_PER_KILL
                if target.enemy_type:
                    xp = ENEMY_TYPES[target.enemy_type]['xp_value']
                leveled = attacker.gain_xp(xp)
                if leveled:
                    self._add_particles(attacker.x, attacker.y - 20,
                                        (255, 255, 0), f"Lv{attacker.level}!", 30)
                    self._add_particles(attacker.x, attacker.y, (255, 215, 0), '', 12, size=5)

    def _kill_unit(self, unit, player):
        """Handle unit death: create corpse, particles, drops, combo."""
        unit.dead = True

        # Determine emoji for corpse
        if unit.team == 'enemy' and unit.enemy_type:
            et = ENEMY_TYPES[unit.enemy_type]
            corpse_key = f"enemy_{et['emoji']}_{et['emoji_size']}"
            corpse_color = et['color']
        elif unit.recruited and unit.unit_type:
            ut = UNIT_TYPES[unit.unit_type]
            corpse_key = f"unit_{ut['emoji']}_{ut['emoji_size']}"
            corpse_color = ut['color']
        else:
            corpse_key = 'neutral'
            corpse_color = (150, 150, 150)

        self.corpses.append(Corpse(unit.x, unit.y, corpse_key, corpse_color))
        self._add_particles(unit.x, unit.y, (255, 200, 50), '☠', 30)
        self._add_particles(unit.x, unit.y, (200, 50, 50), '', 6, size=5)

        if unit.team == 'enemy':
            player.score += 10
            self.total_enemies_defeated += 1
            # Combo
            player.combo += 1
            player.combo_timer = 120  # 2 second window
            if player.combo > 1:
                bonus = player.combo * 5
                player.score += bonus
                self._add_particles(unit.x, unit.y - 25,
                                    (255, 200, 0), f"x{player.combo} +{bonus}", 25)
            if player.combo > self.combo_high:
                self.combo_high = player.combo

            # Death drops
            roll = random.random()
            if roll < 0.20:
                self.pickups.append(Pickup(unit.x, unit.y, 'heart'))
            elif roll < 0.30:
                self.pickups.append(Pickup(unit.x, unit.y, 'star'))
            elif roll < 0.38:
                self.pickups.append(Pickup(unit.x, unit.y, 'medal'))

        elif unit.recruited:
            self._add_particles(unit.x, unit.y, (100, 150, 255), '💔', 25)

    def _apply_knockback(self, target, from_x, from_y, force):
        dx = target.x - from_x
        dy = target.y - from_y
        dist = math.sqrt(dx*dx + dy*dy) + 0.01
        target.knockback_vx += (dx / dist) * force
        target.knockback_vy += (dy / dist) * force
        target.stun_timer = max(target.stun_timer, int(force * 3))

    def _spawn_projectile_particles(self, sx, sy, tx, ty):
        """Create a line of particles simulating an arrow."""
        steps = 5
        for i in range(steps):
            t = i / steps
            px = sx + (tx - sx) * t + random.uniform(-5, 5)
            py = sy + (ty - sy) * t + random.uniform(-5, 5)
            self.particles.append(Particle(px, py, (200, 200, 150), life=10, size=3))

    def _update_enemies(self, enemies, recruited, p):
        """Enhanced enemy AI with pack behavior and retreat."""
        for e in enemies:
            if e.dead: continue
            if e.stun_timer > 0: continue

            # Find nearest threat
            d_to_p = math.sqrt((e.x - p.x)**2 + (e.y - p.y)**2)
            target = None
            target_dist = 220

            if d_to_p < target_dist:
                target = p
                target_dist = d_to_p
            for u in recruited:
                if u.dead: continue
                d = math.sqrt((e.x - u.x)**2 + (e.y - u.y)**2)
                if d < target_dist:
                    target = u
                    target_dist = d

            # Retreat when low HP (except bosses)
            if e.hp_pct() < 0.15 and e.enemy_type != 'boss' and d_to_p < 100:
                dx = e.x - p.x
                dy = e.y - p.y
                dist = math.sqrt(dx*dx + dy*dy) + 0.01
                flee_x = e.x + (dx/dist) * e.speed * 1.2
                flee_y = e.y + (dy/dist) * e.speed * 1.2
                self._move_toward(e, flee_x, flee_y, e.speed * 1.2)
                continue

            if target:
                self._move_toward(e, target.x, target.y, e.speed)
                if target is p and d_to_p < COMBAT_RANGE + 5 and e.attack_cd <= 0:
                    if p.invincible <= 0:
                        dmg = e.damage
                        p.hp -= dmg
                        p.invincible = 10
                        e.attack_cd = e.base_attack_cd
                        self._add_particles(p.x, p.y - 20, (255, 50, 50), f"-{int(dmg)}", 20)
                        self._apply_knockback(p, e.x, e.y, 2)
                        if p.hp <= 0:
                            self.game_over = True
                            self._add_particles(p.x, p.y, (255, 0, 0), '💀', 40)
                elif target is not p and target_dist < e.combat_range and e.attack_cd <= 0:
                    target.hp -= e.damage
                    e.attack_cd = e.base_attack_cd
                    self._add_particles(target.x, target.y - 10,
                                        (255, 80, 80), f"-{int(e.damage)}", 18)
                    self._apply_knockback(target, e.x, e.y, 1.5)
                    e.facing_angle = math.atan2(target.y - e.y, target.x - e.x)
                    if target.hp <= 0:
                        target.dead = True
                        self.corpses.append(Corpse(target.x, target.y,
                            f"unit_{UNIT_TYPES[target.unit_type]['emoji']}_{UNIT_TYPES[target.unit_type]['emoji_size']}"
                            if target.unit_type else 'neutral',
                            UNIT_TYPES[target.unit_type]['color'] if target.unit_type else (150,150,150)))
                        self._add_particles(target.x, target.y, (200, 50, 50), '💔', 25)
            else:
                # Pack behavior: wander near base, group up
                base = None
                for c in self.camps:
                    if c.team == 'enemy':
                        d = math.sqrt((e.x - c.x)**2 + (e.y - c.y)**2)
                        if d < 250:
                            base = c
                            break
                if base:
                    d_base = math.sqrt((e.x-base.x)**2 + (e.y-base.y)**2)
                    if d_base > 70:
                        self._move_toward(e, base.x + random.randint(-30,30),
                                          base.y + random.randint(-30,30),
                                          e.speed * 0.5)
                else:
                    # Wander randomly
                    if self.frame % 60 == 0:
                        e.target_x = e.x + random.randint(-100, 100)
                        e.target_y = e.y + random.randint(-100, 100)
                    if hasattr(e, 'target_x'):
                        self._move_toward(e, e.target_x, e.target_y, e.speed * 0.3)

    def _move_toward(self, unit, tx, ty, speed):
        dx = tx - unit.x
        dy = ty - unit.y
        dist = math.sqrt(dx*dx + dy*dy)
        if dist < 2: return
        nx = unit.x + (dx / dist) * speed
        ny = unit.y + (dy / dist) * speed
        if not self.world.is_blocked(nx, unit.y, 8): unit.x = nx
        if not self.world.is_blocked(unit.x, ny, 8): unit.y = ny

    def _group_around(self, unit, player, army_size):
        """Formation-based grouping: inner core, outer ring, flankers."""
        idx = id(unit)
        base_angle = (idx % 360) / 360.0 * 2 * math.pi
        wobble = math.sin(self.frame * 0.02 + idx * 0.1) * 0.12
        angle = base_angle + wobble

        # Multi-ring formation
        if army_size <= 6:
            r = GROUP_RADIUS * 0.5
        elif army_size <= 15:
            ring = 0 if (hash(idx) % 3) != 0 else 1
            r = GROUP_RADIUS * (0.45 + ring * 0.35)
        elif army_size <= 35:
            ring = hash(idx) % 3
            r = GROUP_RADIUS * (0.4 + ring * 0.25)
        else:
            ring = hash(idx) % 4
            r = GROUP_RADIUS * (0.4 + ring * 0.22)

        # Scouts on the outer ring
        if unit.unit_type == 'scout' and army_size > 8:
            r += 15

        tx = player.x + math.cos(angle) * r
        ty = player.y + math.sin(angle) * r

        dtx = tx - unit.x
        dty = ty - unit.y
        dist = math.sqrt(dtx*dtx + dty*dty)
        if dist > 3:
            spd = min(UNIT_SPEED * 1.3, dist)
            nx = unit.x + (dtx / dist) * spd
            ny = unit.y + (dty / dist) * spd
            if not self.world.is_blocked(nx, unit.y, 8): unit.x = nx
            if not self.world.is_blocked(unit.x, ny, 8): unit.y = ny

    def _add_particles(self, x, y, color, text=None, life=25, size=0):
        count = 4 if text else (2 if size > 0 else 1)
        for _ in range(count):
            self.particles.append(Particle(
                x + random.randint(-10, 10),
                y + random.randint(-10, 10),
                color, text, life, size))

    def _army_size(self):
        return sum(1 for u in self.units if not u.dead and u.recruited)

    def _enemy_count(self):
        return sum(1 for u in self.units if not u.dead and u.team == 'enemy')

    def _enemy_base_count(self):
        return sum(1 for c in self.camps if c.team == 'enemy')

    # ─── DRAWING ───────────────────────────────────────────────────────────────
    def _draw(self):
        self.screen.fill(C_GRASS)
        cam = self.camera

        start_col = max(0, int(cam.x // TILE) - 1)
        end_col = min(GRID_COLS, int((cam.x + SCREEN_W) // TILE) + 2)
        start_row = max(0, int(cam.y // TILE) - 1)
        end_row = min(GRID_ROWS, int((cam.y + SCREEN_H) // TILE) + 2)

        # Terrain
        for row in range(start_row, end_row):
            for col in range(start_col, end_col):
                sx, sy = cam.apply(col * TILE, row * TILE)
                tile = self.world.tiles[row][col]
                if tile == 0:
                    c = [C_GRASS, C_GRASS2, C_GRASS3][(col * 7 + row * 13) % 3]
                    pygame.draw.rect(self.screen, c, (sx, sy, TILE, TILE))
                elif tile == 2:
                    pygame.draw.rect(self.screen, C_WATER, (sx, sy, TILE, TILE))
                    if cam.visible(col * TILE + TILE//2, row * TILE + TILE//2):
                        es = self.emoji['water']
                        ew, eh = es.get_size()
                        self.screen.blit(es, (sx + TILE//2 - ew//2, sy + TILE//2 - eh//2))

        # Trees
        for row in range(start_row, end_row):
            for col in range(start_col, end_col):
                if self.world.tiles[row][col] == 1:
                    px, py = col * TILE + TILE // 2, row * TILE + TILE // 2
                    if cam.visible(px, py):
                        sx, sy = cam.apply(px, py)
                        es = self.emoji['tree']
                        self.screen.blit(es, (sx - es.get_width()//2, sy - es.get_height()//2))

        # Corpses (below units)
        for corpse in self.corpses:
            if not cam.visible(corpse.x, corpse.y, 30): continue
            sx, sy = cam.apply(corpse.x, corpse.y)
            if corpse.emoji_key in self.emoji:
                es = self.emoji[corpse.emoji_key]
                # Dim the corpse
                dim = pygame.Surface(es.get_size(), pygame.SRCALPHA)
                dim.blit(es, (0, 0))
                dim.set_alpha(corpse.fade // 2)
                self.screen.blit(dim, (sx - es.get_width()//2, sy - es.get_height()//2))

        # Pickups
        for pickup in self.pickups:
            if not cam.visible(pickup.x, pickup.y, 30): continue
            sx, sy = cam.apply(pickup.x, pickup.y)
            bob = math.sin(self.frame * 0.1 + id(pickup)) * 4
            if pickup.pickup_type == 'heart':
                es = self.emoji['heart']
            elif pickup.pickup_type == 'star':
                es = self.emoji['star']
            else:
                es = self.emoji['medal']
            self.screen.blit(es, (sx - es.get_width()//2, sy - es.get_height()//2 + bob))
            # Pulsing ring
            pulse = abs(math.sin(self.frame * 0.1)) * 0.5 + 0.5
            s = pygame.Surface((40, 40), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 255, 200, int(60 * pulse)), (20, 20), 15, 2)
            self.screen.blit(s, (sx - 20, sy - 20))

        # Camps
        for camp in self.camps:
            if not cam.visible(camp.x, camp.y, 100): continue
            sx, sy = cam.apply(camp.x, camp.y)
            if camp.team == 'friendly':
                s = pygame.Surface((RECRUIT_RADIUS*2, RECRUIT_RADIUS*2), pygame.SRCALPHA)
                pygame.draw.circle(s, (100, 200, 255, 25),
                                  (RECRUIT_RADIUS, RECRUIT_RADIUS), RECRUIT_RADIUS)
                pygame.draw.circle(s, (100, 200, 255, 50),
                                  (RECRUIT_RADIUS, RECRUIT_RADIUS), RECRUIT_RADIUS, 2)
                self.screen.blit(s, (sx - RECRUIT_RADIUS, sy - RECRUIT_RADIUS))
                e = self.emoji['camp_friendly']
                self.screen.blit(e, (sx - e.get_width()//2, sy - e.get_height()//2))
            else:
                s = pygame.Surface((320, 320), pygame.SRCALPHA)
                pygame.draw.circle(s, (255, 50, 50, 20), (160, 160), 160)
                pygame.draw.circle(s, (255, 50, 50, 45), (160, 160), 160, 2)
                self.screen.blit(s, (sx - 160, sy - 160))
                e = self.emoji['camp_enemy']
                self.screen.blit(e, (sx - e.get_width()//2, sy - e.get_height()//2))
                if camp.spawn_timer > 0:
                    pct = camp.spawn_timer / ENEMY_SPAWN_INTERVAL
                    bw = 40
                    pygame.draw.rect(self.screen, (60,60,60), (sx - bw//2, sy + 25, bw, 5))
                    pygame.draw.rect(self.screen, (255,80,80), (sx - bw//2, sy + 25, int(bw*pct), 5))

        # Units — sorted by y for depth
        visible_units = [u for u in self.units if not u.dead and cam.visible(u.x, u.y, 30)]
        visible_units.sort(key=lambda u: u.y)

        for u in visible_units:
            sx, sy = cam.apply(u.x, u.y)

            if u.team == 'friendly' and not u.recruited:
                es = self.emoji['neutral']
                self.screen.blit(es, (sx - es.get_width()//2, sy - es.get_height()//2))

                # Willingness indicator
                if u.recruit_timer > 0:
                    # Joining animation: draw connecting line
                    p_sx, p_sy = cam.apply(self.player.x, self.player.y)
                    progress = min(1.0, u.recruit_timer / 30.0)
                    line_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                    # Dashed line effect
                    steps = int(10 * progress)
                    for i in range(steps):
                        t1 = i / 10.0
                        t2 = min(1.0, (i + 0.6) / 10.0)
                        lx1 = sx + (p_sx - sx) * t1
                        ly1 = sy + (p_sy - sy) * t1
                        lx2 = sx + (p_sx - sx) * t2
                        ly2 = sy + (p_sy - sy) * t2
                        pygame.draw.line(line_surf, (100, 200, 255, int(150 * progress)),
                                        (int(lx1), int(ly1)), (int(lx2), int(ly2)), 2)
                    self.screen.blit(line_surf, (0, 0))

                    # Progress ring
                    arc_pct = u.recruit_timer / 30.0
                    ring_s = pygame.Surface((60, 60), pygame.SRCALPHA)
                    pygame.draw.circle(ring_s, (100, 200, 255, 100), (30, 30), 22, 3)
                    # Fill arc
                    end_angle = arc_pct * 2 * math.pi
                    for a in range(int(end_angle / 0.15)):
                        ang = a * 0.15
                        px_r = 30 + math.cos(ang) * 22
                        py_r = 30 + math.sin(ang) * 22
                        pygame.draw.circle(ring_s, (150, 230, 255, 200), (int(px_r), int(py_r)), 2)
                    self.screen.blit(ring_s, (sx - 30, sy - 30))
                else:
                    # Pulsing recruit ring with willingness hint
                    pulse = abs(math.sin(self.frame * 0.08)) * 0.4 + 0.6
                    s = pygame.Surface((50, 50), pygame.SRCALPHA)
                    pygame.draw.circle(s, (100, 200, 255, int(80 * pulse)), (25, 25), 20, 2)
                    self.screen.blit(s, (sx - 25, sy - 25))
                    # Show unit type emoji hint
                    if u.unit_type:
                        ut = UNIT_TYPES[u.unit_type]
                        type_es = load_emoji(ut['emoji'], 14)
                        self.screen.blit(type_es, (sx + 12, sy - 18))

                # HP bar
                self._draw_hp_bar(sx, sy + 14, u.hp, u.max_hp, 20, C_HP_GREEN)

            elif u.recruited:
                # Draw army unit with type emoji
                if u.unit_type:
                    ut = UNIT_TYPES[u.unit_type]
                    es = self.emoji[f"unit_{ut['emoji']}_{ut['emoji_size']}"]
                else:
                    es = self.emoji['sword']
                self.screen.blit(es, (sx - es.get_width()//2, sy - es.get_height()//2))

                # Level badge
                if u.level > 1:
                    lvl_text = self.font_tiny.render(f"Lv{u.level}", True, (255, 255, 0))
                    self.screen.blit(lvl_text, (sx + 12, sy - 18))

                # Recruit animation
                if u.recruit_anim > 0:
                    star = self.emoji['recruit']
                    self.screen.blit(star, (sx - star.get_width()//2,
                                            sy - es.get_height()//2 - star.get_height()))

                # Attack target line (faint)
                if u.attack_target and not u.attack_target.dead and self.player.mode == 'attack':
                    tsx, tsy = cam.apply(u.attack_target.x, u.attack_target.y)
                    line_s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                    pygame.draw.line(line_s, (255, 100, 100, 40), (sx, sy), (tsx, tsy), 1)
                    self.screen.blit(line_s, (0, 0))

                # HP bar (color by HP %)
                hp_pct = u.hp_pct()
                hp_color = C_HP_GREEN if hp_pct > 0.5 else (C_HP_YELLOW if hp_pct > 0.25 else C_HP_RED)
                self._draw_hp_bar(sx, sy + 14, u.hp, u.max_hp, 22, hp_color)

                # Retreat indicator
                if u.retreating:
                    ret_text = self.font_tiny.render("!!", True, C_HP_RED)
                    self.screen.blit(ret_text, (sx - 5, sy - 28))

            elif u.team == 'enemy':
                if u.enemy_type:
                    et = ENEMY_TYPES[u.enemy_type]
                    es = self.emoji[f"enemy_{et['emoji']}_{et['emoji_size']}"]
                else:
                    es = self.emoji['skull']
                self.screen.blit(es, (sx - es.get_width()//2, sy - es.get_height()//2))

                # Boss crown
                if u.enemy_type == 'boss':
                    crown = self.emoji['crown']
                    self.screen.blit(crown, (sx - crown.get_width()//2, sy - 30))

                hp_pct = u.hp_pct()
                hp_color = C_HP_GREEN if hp_pct > 0.5 else (C_HP_YELLOW if hp_pct > 0.25 else C_HP_RED)
                bar_w = 26 if u.enemy_type == 'boss' else 22
                self._draw_hp_bar(sx, sy + 16, u.hp, u.max_hp, bar_w, hp_color)

                # Stun indicator
                if u.stun_timer > 0:
                    stun_text = self.font_tiny.render("*", True, (255, 255, 200))
                    self.screen.blit(stun_text, (sx + 10, sy - 20))

        # Player
        p = self.player
        px_s, py_s = cam.apply(p.x, p.y)

        # Mode radius
        if p.mode == 'attack':
            s = pygame.Surface((ATTACK_RADIUS*2, ATTACK_RADIUS*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 60, 60, 15),
                              (ATTACK_RADIUS, ATTACK_RADIUS), ATTACK_RADIUS)
            pygame.draw.circle(s, (255, 60, 60, 40),
                              (ATTACK_RADIUS, ATTACK_RADIUS), ATTACK_RADIUS, 2)
            self.screen.blit(s, (px_s - ATTACK_RADIUS, py_s - ATTACK_RADIUS))
        else:
            r = GROUP_RADIUS + 25
            s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (80, 180, 255, 20), (r, r), r)
            pygame.draw.circle(s, (80, 180, 255, 50), (r, r), r, 2)
            self.screen.blit(s, (px_s - r, py_s - r))

        if p.recruit_flash > 0:
            s = pygame.Surface((120, 120), pygame.SRCALPHA)
            alpha = int(p.recruit_flash * 12)
            pygame.draw.circle(s, (100, 200, 255, alpha), (60, 60), 60)
            self.screen.blit(s, (px_s - 60, py_s - 60))

        # Dash cooldown ring
        if p.dash_cooldown > 0:
            cd_pct = p.dash_cooldown / 50.0
            s = pygame.Surface((60, 60), pygame.SRCALPHA)
            end_a = (1 - cd_pct) * 2 * math.pi
            for a_step in range(int(end_a / 0.15)):
                ang = a_step * 0.15 - math.pi/2
                rx = 30 + math.cos(ang) * 22
                ry = 30 + math.sin(ang) * 22
                pygame.draw.circle(s, (200, 200, 255, 120), (int(rx), int(ry)), 2)
            self.screen.blit(s, (px_s - 30, py_s - 30))

        # Player emoji
        e = self.emoji['player']
        self.screen.blit(e, (px_s - e.get_width()//2, py_s - e.get_height()//2))
        crown = self.emoji['crown']
        bob = math.sin(self.frame * 0.05) * 3
        self.screen.blit(crown, (px_s - crown.get_width()//2,
                                 py_s - e.get_height()//2 - crown.get_height() + bob))
        self._draw_hp_bar(px_s, py_s + 20, p.hp, p.max_hp, 36, C_HP_GREEN)

        # Particles
        for part in self.particles:
            sx, sy = cam.apply(part.x, part.y)
            alpha = int(255 * (part.life / part.max_life))
            if part.text:
                color = (*part.color[:3],)
                txt = self.font_sm.render(str(part.text), True, color)
                self.screen.blit(txt, (sx - txt.get_width()//2, sy))
            elif part.size > 0:
                s = max(1, int(part.size * (part.life / part.max_life)))
                surf = pygame.Surface((s*2, s*2), pygame.SRCALPHA)
                pygame.draw.circle(surf, (*part.color[:3], alpha), (s, s), s)
                self.screen.blit(surf, (sx - s, sy - s))
            else:
                s = max(1, int(4 * (part.life / part.max_life)))
                surf = pygame.Surface((s*2, s*2), pygame.SRCALPHA)
                pygame.draw.circle(surf, (*part.color[:3], alpha), (s, s), s)
                self.screen.blit(surf, (sx - s, sy - s))

        # HUD
        self._draw_hud()
        if self.show_minimap:
            self._draw_minimap()

        if self.game_over:
            self._draw_overlay("GAME OVER", (255, 60, 60),
                f"Score: {p.score}  |  Defeated: {self.total_enemies_defeated}  |  Best Combo: x{self.combo_high}  |  Press R")
        elif self.game_won:
            self._draw_overlay("VICTORY!", (255, 215, 0),
                f"Score: {p.score}  |  All Bases Captured!  |  Best Combo: x{self.combo_high}  |  Press R")

    def _draw_hp_bar(self, x, y, hp, max_hp, width, color):
        bar_h = 4
        pygame.draw.rect(self.screen, (40, 40, 40), (x - width//2, y, width, bar_h), border_radius=2)
        pct = max(0, hp / max_hp)
        fill_w = int(width * pct)
        if fill_w > 0:
            pygame.draw.rect(self.screen, color, (x - width//2, y, fill_w, bar_h), border_radius=2)

    def _draw_hud(self):
        p = self.player
        army = self._army_size()
        enemies = self._enemy_count()
        bases = self._enemy_base_count()

        # Top bar
        s = pygame.Surface((SCREEN_W, 58), pygame.SRCALPHA)
        s.fill((10, 10, 30, 190))
        self.screen.blit(s, (0, 0))

        # HP
        hp_pct = p.hp / p.max_hp
        hp_color = C_HP_GREEN if hp_pct > 0.3 else C_HP_RED
        hp_text = f"HP: {max(0,int(p.hp))}/{p.max_hp}"
        hp_surf = self.font_md.render(hp_text, True, hp_color)
        self.screen.blit(hp_surf, (15, 4))
        bar_w = 120
        pygame.draw.rect(self.screen, (60,60,60), (15, 28, bar_w, 8), border_radius=3)
        pygame.draw.rect(self.screen, hp_color, (15, 28, int(bar_w * hp_pct), 8), border_radius=3)

        # Score & combo
        score_surf = self.font_md.render(f"Score: {p.score}", True, (255, 215, 0))
        self.screen.blit(score_surf, (155, 4))
        if p.combo > 1:
            combo_surf = self.font_md.render(f"COMBO x{p.combo}!", True, (255, 150, 0))
            self.screen.blit(combo_surf, (155, 28))
        else:
            army_surf = self.font_md.render(f"Army: {army}/{MAX_ARMY_SIZE}", True, (100, 200, 255))
            self.screen.blit(army_surf, (155, 28))

        # Mode
        if p.mode == 'attack':
            mode_color = C_ATTACK_CLR
            mode_text = "ATTACK MODE"
        else:
            mode_color = C_GROUP_CLR
            mode_text = "GROUP MODE"
        mode_surf = self.font_md.render(mode_text, True, mode_color)
        self.screen.blit(mode_surf, (SCREEN_W//2 - mode_surf.get_width()//2, 4))
        desc = "[Q] Attack  [E] Group  [F] Recruit  [SPACE] Dash  [TAB] Map"
        desc_surf = self.font_tiny.render(desc, True, (160, 160, 180))
        self.screen.blit(desc_surf, (SCREEN_W//2 - desc_surf.get_width()//2, 28))

        # Army composition
        recruited = [u for u in self.units if not u.dead and u.recruited]
        type_counts = {}
        for u in recruited:
            if u.unit_type:
                type_counts[u.unit_type] = type_counts.get(u.unit_type, 0) + 1
        comp_parts = []
        for ut_name, count in sorted(type_counts.items()):
            if ut_name in UNIT_TYPES:
                emoji_char = UNIT_TYPES[ut_name]['emoji']
                comp_parts.append(f"{emoji_char}{count}")
        if comp_parts:
            comp_text = "  ".join(comp_parts)
            comp_surf = self.font_sm.render(comp_text, True, (220, 220, 240))
            self.screen.blit(comp_surf, (SCREEN_W//2 - comp_surf.get_width()//2, 44))

        # Right side
        enemy_text = f"Enemies: {enemies}  |  Bases: {bases}"
        enemy_surf = self.font_md.render(enemy_text, True, (255, 120, 120))
        self.screen.blit(enemy_surf, (SCREEN_W - enemy_surf.get_width() - 15, 4))
        stats = f"Defeated: {self.total_enemies_defeated}  |  Recruited: {self.total_recruited}"
        stats_surf = self.font_sm.render(stats, True, (200, 200, 220))
        self.screen.blit(stats_surf, (SCREEN_W - stats_surf.get_width() - 15, 28))

        # Dash cooldown indicator
        if p.dash_cooldown > 0:
            dash_text = f"Dash: {p.dash_cooldown // 6}"
            dash_surf = self.font_tiny.render(dash_text, True, (150, 150, 200))
        else:
            dash_surf = self.font_tiny.render("Dash: Ready", True, (100, 255, 100))
        self.screen.blit(dash_surf, (SCREEN_W - dash_surf.get_width() - 15, 46))

    def _draw_minimap(self):
        mm_w, mm_h = 180, 180
        mm_x, mm_y = SCREEN_W - mm_w - 10, SCREEN_H - mm_h - 10
        s = pygame.Surface((mm_w, mm_h), pygame.SRCALPHA)
        s.fill((0, 0, 0, 160))
        sx_scale = mm_w / WORLD_W
        sy_scale = mm_h / WORLD_H

        for camp in self.camps:
            mx, my = int(camp.x * sx_scale), int(camp.y * sy_scale)
            c = (100, 200, 255) if camp.team == 'friendly' else (255, 80, 80)
            pygame.draw.circle(s, c, (mx, my), 4)

        for u in self.units:
            if u.dead: continue
            mx, my = int(u.x * sx_scale), int(u.y * sy_scale)
            if u.team == 'enemy':
                c = (255, 40, 40) if u.enemy_type == 'boss' else (255, 80, 80)
                r = 3 if u.enemy_type == 'boss' else 1
                pygame.draw.circle(s, c, (mx, my), r)
            elif u.recruited:
                pygame.draw.circle(s, (100, 200, 255), (mx, my), 1)

        px, py = int(self.player.x * sx_scale), int(self.player.y * sy_scale)
        pygame.draw.circle(s, (255, 255, 0), (px, py), 3)
        pygame.draw.circle(s, (255, 255, 255), (px, py), 4, 1)

        cx, cy = int(self.camera.x * sx_scale), int(self.camera.y * sy_scale)
        cw, ch = int(SCREEN_W * sx_scale), int(SCREEN_H * sy_scale)
        pygame.draw.rect(s, (255, 255, 255, 80), (cx, cy, cw, ch), 1)
        pygame.draw.rect(s, (200, 200, 200, 120), (0, 0, mm_w, mm_h), 2)
        self.screen.blit(s, (mm_x, mm_y))

    def _draw_overlay(self, title, color, subtitle):
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 150))
        self.screen.blit(s, (0, 0))
        title_surf = self.font_xl.render(title, True, color)
        self.screen.blit(title_surf, (SCREEN_W//2 - title_surf.get_width()//2, SCREEN_H//2 - 70))
        sub_surf = self.font_md.render(subtitle, True, (220, 220, 220))
        self.screen.blit(sub_surf, (SCREEN_W//2 - sub_surf.get_width()//2, SCREEN_H//2))
        emoji_choice = self.emoji['skull'] if self.game_over else self.emoji['crown']
        bob = math.sin(self.frame * 0.05) * 5
        self.screen.blit(emoji_choice, (SCREEN_W//2 - emoji_choice.get_width()//2,
                                         SCREEN_H//2 - 110 + bob))


if __name__ == "__main__":
    game = Game()
    game.run()
