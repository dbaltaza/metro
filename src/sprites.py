"""Pixel-art sprites and caches shared by the map and the station scene.

Everything here draws in world pixels: small surfaces that get scaled up by
an integer factor with no smoothing, which is what gives the chunky look.
"""

import random

import pygame

OUTLINE = (24, 22, 26)

SKIN_TONES = [(246, 210, 176), (226, 184, 142), (192, 142, 100), (150, 104, 72), (110, 78, 54)]
HAIR_COLORS = [(38, 30, 28), (84, 56, 36), (150, 100, 52), (212, 178, 96), (150, 56, 40), (66, 66, 74), (232, 226, 210), (120, 60, 130)]
SHIRTS = [
    (226, 96, 84), (86, 152, 226), (236, 182, 62), (108, 190, 112), (188, 118, 216),
    (238, 136, 64), (84, 196, 196), (240, 240, 240), (60, 66, 90), (220, 80, 130), (110, 110, 118), (40, 120, 90),
]
PANTS = [(46, 56, 96), (68, 68, 76), (96, 72, 54), (34, 34, 42), (150, 140, 120)]
SHOES = [(30, 28, 32), (90, 60, 40), (200, 200, 205)]
HAIR_STYLES = ["short", "long", "bald", "cap", "bun", "spiky"]
STAFF_BLUE = (44, 52, 90)


def shade(color, delta: int):
    return tuple(min(max(c + delta, 0), 255) for c in color)


class Look:
    """A stable appearance for a character, derived from their id."""

    def __init__(self, pid: int):
        rng = random.Random(pid * 104729 + 7)
        self.skin = rng.choice(SKIN_TONES)
        self.hair = rng.choice(HAIR_COLORS)
        self.style = rng.choice(HAIR_STYLES)
        self.shirt = rng.choice(SHIRTS)
        self.pants = rng.choice(PANTS)
        self.shoes = rng.choice(SHOES)
        self.backpack = rng.random() < 0.28
        self.glasses = rng.random() < 0.15
        self.wide = rng.random() < 0.2
        self.cap_color = rng.choice(SHIRTS)
        if pid < 0:  # station staff: uniform, cap, badge
            self.shirt, self.pants, self.style = STAFF_BLUE, (30, 30, 40), "cap"
            self.cap_color, self.backpack, self.wide = STAFF_BLUE, False, False


LOOK_POOL = 512

_looks: dict[int, Look] = {}


def look_key(pid: int) -> int:
    """A bounded stand-in for a person's id. Passenger ids climb into the tens
    of thousands over a session, so caching appearance against the raw id
    grows without limit; appearance comes from a fixed pool instead. All
    staff (negative ids) share one uniform."""
    return -1 if pid < 0 else pid % LOOK_POOL


def look_for(pid: int) -> Look:
    key = look_key(pid)
    look = _looks.get(key)
    if look is None:
        look = _looks[key] = Look(key)
    return look


def _evict(cache: dict, limit: int) -> None:
    """Drop the oldest quarter once a cache is full. Clearing the whole thing
    instead means a busy scene rebuilds every sprite it is still using, over
    and over."""
    if len(cache) <= limit:
        return
    for key in list(cache)[:max(len(cache) // 4, 1)]:
        del cache[key]


# --- big characters (station scene) ------------------------------------------------

CHAR_W, CHAR_H = 18, 32
CHAR_FEET = 29  # y of the feet inside the sprite

_char_cache: dict[tuple[int, int, int], pygame.Surface] = {}


def _build_character(pid: int, facing: int, step: int, pose: str = "stand") -> pygame.Surface:
    """Poses: "stand" (with walking steps), "phone" (looking at a phone held in
    front), "sit" (on a bench, legs forward). Feet stay at CHAR_FEET."""
    look = look_for(pid)
    s = pygame.Surface((CHAR_W, CHAR_H), pygame.SRCALPHA)
    ox = CHAR_W // 2
    half = 6 if look.wide else 5
    drop = 4 if pose == "sit" else 0   # a seated body sits lower
    torso = pygame.Rect(ox - half, 12 + drop, half * 2, 10)
    head = pygame.Rect(ox - 5, 3 + drop, 10, 9)
    lift_l = 1 if step == 1 else 0
    lift_r = 1 if step == 2 else 0
    if pose == "sit":
        # Thighs forward, shins down: feet still on the ground at CHAR_FEET.
        leg_l = pygame.Rect(ox - 6, 26, 3, 3)
        leg_r = pygame.Rect(ox + 3, 26, 3, 3)
        thighs = pygame.Rect(ox - 6, 24, 12, 3)
    else:
        leg_l = pygame.Rect(ox - 4, 22 - lift_l, 3, 7)
        leg_r = pygame.Rect(ox + 1, 22 - lift_r, 3, 7)
        thighs = None
    arm_l = pygame.Rect(torso.left - 2, torso.y + 1, 2, 8)
    arm_r = pygame.Rect(torso.right, torso.y + 1, 2, 8)
    if pose == "phone" and facing > 0:
        arm_r = pygame.Rect(torso.right, torso.y + 1, 2, 4)   # upper arm, then a bent forearm

    shadow = pygame.Surface((14, 5), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 85), shadow.get_rect())
    s.blit(shadow, (ox - 7, CHAR_FEET - 3))

    parts = [leg_l, leg_r, arm_l, arm_r, torso, head]
    if thighs:
        parts.insert(2, thighs)
    for part in parts:
        pygame.draw.rect(s, OUTLINE, part.inflate(2, 2))

    if thighs:
        pygame.draw.rect(s, look.pants, thighs)
    for leg, lift in ((leg_l, lift_l), (leg_r, lift_r)):
        pygame.draw.rect(s, look.pants, leg)
        pygame.draw.rect(s, look.shoes, (leg.x, leg.bottom - 2, leg.width, 2))

    pygame.draw.rect(s, look.shirt, torso)
    pygame.draw.rect(s, shade(look.shirt, -34), (torso.right - 2, torso.y, 2, torso.height))
    pygame.draw.rect(s, shade(look.shirt, 22), (torso.x, torso.y, 1, torso.height))
    pygame.draw.rect(s, shade(look.shirt, -30), (torso.x, torso.bottom - 1, torso.width, 1))
    for arm in (arm_l, arm_r):
        pygame.draw.rect(s, shade(look.shirt, -10), arm)
        pygame.draw.rect(s, look.skin, (arm.x, arm.bottom - 2, 2, 2))
    if pose == "phone" and facing > 0:
        # Forearm across the chest holding a phone, screen lit.
        fore = pygame.Rect(ox + 1, torso.y + 4, torso.right - ox, 2)
        pygame.draw.rect(s, shade(look.shirt, -10), fore)
        pygame.draw.rect(s, look.skin, (fore.x, fore.y, 2, 2))
        phone = pygame.Rect(ox - 1, torso.y + 2, 2, 4)
        pygame.draw.rect(s, OUTLINE, phone.inflate(2, 2))
        pygame.draw.rect(s, (30, 30, 36), phone)
        pygame.draw.rect(s, (150, 210, 255), (phone.x, phone.y + 1, 1, 2))
    if facing < 0 and look.backpack:
        pack = pygame.Rect(ox - 3, 13, 6, 7)
        pygame.draw.rect(s, OUTLINE, pack.inflate(2, 2))
        pygame.draw.rect(s, shade(look.cap_color, -20), pack)
    if pid < 0:
        pygame.draw.rect(s, (240, 200, 70), (torso.x + 2, torso.y + 2, 2, 2))

    pygame.draw.rect(s, look.skin, head)
    pygame.draw.rect(s, shade(look.skin, -28), (head.right - 2, head.y + 1, 2, head.height - 1))
    if facing > 0:
        eye_y = head.y + 5 + (1 if pose == "phone" else 0)   # looking down at the phone
        pygame.draw.rect(s, OUTLINE, (ox - 3, eye_y, 2, 2))
        pygame.draw.rect(s, OUTLINE, (ox + 1, eye_y, 2, 2))
        pygame.draw.rect(s, shade(look.skin, -40), (ox - 1, eye_y + 2, 2, 1))
        if look.glasses:
            pygame.draw.line(s, (40, 40, 50), (ox - 4, eye_y), (ox + 3, eye_y))

    hair = look.hair
    d = drop
    if look.style == "cap":
        pygame.draw.rect(s, OUTLINE, (ox - 6, 1 + d, 12, 5))
        pygame.draw.rect(s, look.cap_color, (ox - 5, 2 + d, 10, 3))
        brim_y = (5 if facing > 0 else 2) + d
        pygame.draw.rect(s, shade(look.cap_color, -40), (ox - 6, brim_y, 12, 1))
    elif look.style == "bald":
        pygame.draw.rect(s, shade(look.skin, 16), (ox - 4, 3 + d, 8, 1))
    else:
        top = pygame.Rect(ox - 5, 2 + d, 10, 3)
        pygame.draw.rect(s, OUTLINE, top.inflate(2, 2))
        pygame.draw.rect(s, hair, top)
        if look.style == "spiky":
            for sx in (ox - 4, ox - 1, ox + 2):
                pygame.draw.rect(s, hair, (sx, 1 + d, 2, 1))
        if look.style in ("long", "bun") or facing < 0:
            depth = 9 if look.style == "long" else 5
            for side in (ox - 6, ox + 4):
                pygame.draw.rect(s, OUTLINE, (side, 3 + d, 2, depth + 1))
                pygame.draw.rect(s, hair, (side, 3 + d, 2, depth))
        if facing < 0:
            pygame.draw.rect(s, hair, (ox - 5, 4 + d, 10, 4))
            if look.style == "bun":
                pygame.draw.rect(s, OUTLINE, (ox - 2, 0 + d, 4, 4))
                pygame.draw.rect(s, hair, (ox - 1, 1 + d, 2, 2))
    return s


def character(pid: int, facing: int = 1, step: int = 0, pose: str = "stand") -> pygame.Surface:
    looks = look_key(pid)
    key = (looks, facing, step, pose)
    sprite = _char_cache.get(key)
    if sprite is None:
        _evict(_char_cache, 4000)
        sprite = _char_cache[key] = _build_character(looks, facing, step, pose)
    return sprite


def draw_character(surface: pygame.Surface, x: float, y: float, pid: int, facing: int = 1, step: int = 0, alpha: int = 255, pose: str = "stand") -> None:
    """Blit a character with their feet at (x, y)."""
    sprite = character(pid, facing, step, pose)
    if alpha < 255:
        sprite = sprite.copy()
        sprite.set_alpha(alpha)
    surface.blit(sprite, (round(x) - CHAR_W // 2, round(y) - CHAR_FEET))


# --- tiny people (map view) -----------------------------------------------------------

TINY_LOOKS = 24
_tiny_cache: dict[int, pygame.Surface] = {}


def tiny_person(seed: int) -> pygame.Surface:
    """A 4x7 person for crowds on the map. Feet at the bottom."""
    key = seed % TINY_LOOKS
    sprite = _tiny_cache.get(key)
    if sprite is None:
        look = look_for(1000 + key)
        sprite = pygame.Surface((5, 8), pygame.SRCALPHA)
        pygame.draw.rect(sprite, OUTLINE, (0, 0, 5, 8))
        pygame.draw.rect(sprite, look.hair, (1, 1, 3, 1))
        pygame.draw.rect(sprite, look.skin, (1, 2, 3, 2))
        pygame.draw.rect(sprite, look.shirt, (1, 4, 3, 2))
        pygame.draw.rect(sprite, look.pants, (1, 6, 3, 1))
        _tiny_cache[key] = sprite
    return sprite


# --- text and rotation caches --------------------------------------------------------

_text_cache: dict[tuple[int, str, tuple], pygame.Surface] = {}


def text(font: pygame.font.Font, string: str, color) -> pygame.Surface:
    """Render text once and reuse it. Fonts render slowly enough to matter at 60fps."""
    key = (id(font), string, tuple(color))
    surface = _text_cache.get(key)
    if surface is None:
        _evict(_text_cache, 4000)
        surface = _text_cache[key] = font.render(string, True, color)
    return surface


_rot_cache: dict[tuple[int, int], pygame.Surface] = {}
ROTATION_STEP = 10


def rotated(key: int, base: pygame.Surface, angle: float) -> pygame.Surface:
    """A rotated copy snapped to 10 degree steps, cached per base sprite."""
    bucket = round(angle / ROTATION_STEP) % (360 // ROTATION_STEP)
    cache_key = (key, bucket)
    surface = _rot_cache.get(cache_key)
    if surface is None:
        surface = _rot_cache[cache_key] = pygame.transform.rotate(base, bucket * ROTATION_STEP)
    return surface
