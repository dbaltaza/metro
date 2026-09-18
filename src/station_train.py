"""Drawing the Lisbon Metro train in the station scene: silver cars, dark
window band, red M, cab board, sliding doors."""

import pygame

from src import sprites
from src.metro import Metro
from src.route import TEXT
from src.sprites import OUTLINE, shade
from src.station_layout import (
    BAND, BOARD_AMBER, CARS, CAR_GAP, CAR_LEN, DOOR_FRACTIONS, DOOR_W, GLASS_PANE,
    HEADLIGHT, INTERIOR, ML_RED, PLATFORM_1, ROOF_GREY, ROOF_H, SIDE_H, SILVER,
    SILVER_HI, SILVER_LO, SKIRT, TRAIN_LEN, box,
)

def door_xs(x: float) -> list[float]:
    left = x - TRAIN_LEN / 2
    xs = []
    for car in range(CARS):
        cx = left + car * (CAR_LEN + CAR_GAP)
        xs.extend(cx + f * CAR_LEN for f in DOOR_FRACTIONS)
    return xs


def draw_train(view, s, metro: Metro, x: float, pit: pygame.Rect) -> None:
    """A Lisbon Metro train: silver cars, dark window band, red M, lit cab board."""
    color = view.line.color
    y0 = pit.top - 5
    left = round(x - TRAIN_LEN / 2)
    dwelling = metro.current_station == view.name and metro.cooldown > 0
    doors_visible = view._side(metro) > 0
    open_k = view._door_state(metro) if dwelling else 0.0
    side_y = y0 + ROOF_H

    s.blit(view.train_shadow, (left - 2, y0 + ROOF_H + SIDE_H - 4))
    heads = len(metro.riders)
    front_car = 0 if metro.direction < 0 else CARS - 1
    rear_car = CARS - 1 - front_car
    for car in range(CARS):
        cx = left + car * (CAR_LEN + CAR_GAP)
        if car:
            pygame.draw.rect(s, OUTLINE, (cx - CAR_GAP, side_y + 5, CAR_GAP, 10))
            pygame.draw.rect(s, SKIRT, (cx - CAR_GAP + 1, side_y + 7, CAR_GAP - 2, 5))
        body = pygame.Rect(cx, y0, CAR_LEN, ROOF_H + SIDE_H)
        pygame.draw.rect(s, OUTLINE, body.inflate(2, 2), border_radius=3)

        # Roof with air-conditioning units.
        pygame.draw.rect(s, ROOF_GREY, (cx, y0, CAR_LEN, ROOF_H), border_top_left_radius=3, border_top_right_radius=3)
        pygame.draw.line(s, shade(ROOF_GREY, 30), (cx + 2, y0 + 1), (cx + CAR_LEN - 3, y0 + 1))
        pygame.draw.line(s, shade(ROOF_GREY, -40), (cx, y0 + ROOF_H - 1), (cx + CAR_LEN - 1, y0 + ROOF_H - 1))
        for ax in (cx + 28, cx + CAR_LEN - 52):
            box(s, pygame.Rect(ax, y0 + 4, 24, 8), shade(ROOF_GREY, -24))
            pygame.draw.line(s, shade(ROOF_GREY, -46), (ax + 2, y0 + 7), (ax + 21, y0 + 7))

        # Side, top to bottom: silver, the dark window band, the line stripe,
        # then the skirt over the underframe.
        pygame.draw.rect(s, SILVER, (cx, side_y, CAR_LEN, SIDE_H))
        pygame.draw.line(s, SILVER_HI, (cx, side_y), (cx + CAR_LEN - 1, side_y))
        pygame.draw.line(s, SILVER_HI, (cx, side_y + 1), (cx + CAR_LEN - 1, side_y + 1))
        pygame.draw.rect(s, BAND, (cx, side_y + 3, CAR_LEN, 9))
        pygame.draw.line(s, shade(BAND, 26), (cx, side_y + 3), (cx + CAR_LEN - 1, side_y + 3))
        pygame.draw.rect(s, color, (cx, side_y + 18, CAR_LEN, 2))
        pygame.draw.rect(s, SILVER_LO, (cx, side_y + 20, CAR_LEN, 1))
        pygame.draw.rect(s, SKIRT, (cx, side_y + 21, CAR_LEN, SIDE_H - 21))

        car_doors = [cx + f * CAR_LEN for f in DOOR_FRACTIONS]
        for wx in range(cx + 7, cx + CAR_LEN - 9, 11):
            if any(abs(wx + 4 - d) < DOOR_W / 2 + 5 for d in car_doors):
                continue
            pygame.draw.rect(s, GLASS_PANE, (wx, side_y + 4, 9, 7))
            pygame.draw.line(s, shade(GLASS_PANE, 50), (wx, side_y + 4), (wx + 8, side_y + 4))
            pygame.draw.line(s, shade(GLASS_PANE, -40), (wx, side_y + 10), (wx + 8, side_y + 10))
            if heads > 0:
                # A head and shoulders in the window, so a full train looks full.
                pygame.draw.rect(s, (48, 42, 52), (wx + 3, side_y + 6, 4, 5))
                pygame.draw.rect(s, (96, 76, 62), (wx + 4, side_y + 6, 2, 2))
                heads -= 1

        # Red M roundel on the silver below the windows, as on the real cars.
        lx, ly = cx + CAR_LEN // 2 - 4, side_y + 13
        pygame.draw.rect(s, ML_RED, (lx, ly, 8, 5), border_radius=1)
        for px_, py_ in ((1, 1), (1, 2), (1, 3), (6, 1), (6, 2), (6, 3), (2, 2), (3, 2), (4, 2), (5, 2)):
            s.set_at((lx + px_, ly + py_), (250, 250, 250))

        # Doors: two leaves that slide apart, dark rubber edges.
        for d in car_doors:
            door = pygame.Rect(round(d - DOOR_W / 2), side_y + 1, DOOR_W, SIDE_H - 2)
            slide = round(open_k * (DOOR_W / 2 - 1)) if doors_visible else 0
            if slide:
                pygame.draw.rect(s, INTERIOR, door)
                pygame.draw.rect(s, shade(INTERIOR, -70), (door.x, door.bottom - 2, door.width, 2))
            leaf_w = DOOR_W // 2
            for leaf_x in (door.x - slide, door.centerx + slide):
                leaf = pygame.Rect(leaf_x, door.y, leaf_w, door.height)
                leaf.clamp_ip(pygame.Rect(door.x - leaf_w, door.y, DOOR_W + leaf_w * 2, door.height))
                pygame.draw.rect(s, SILVER_LO, leaf)
                pygame.draw.rect(s, BAND, (leaf.x + 1, side_y + 3, leaf_w - 2, 9))
                pygame.draw.rect(s, GLASS_PANE, (leaf.x + 1, side_y + 4, leaf_w - 2, 6))
                pygame.draw.rect(s, color, (leaf.x, side_y + 18, leaf_w, 2))
                pygame.draw.line(s, OUTLINE, (leaf.x, leaf.y), (leaf.x, leaf.bottom - 1))
                pygame.draw.line(s, OUTLINE, (leaf.right - 1, leaf.y), (leaf.right - 1, leaf.bottom - 1))
            # Silver body shows again outside the door opening.
            pygame.draw.rect(s, OUTLINE, (door.x - 1, door.y, 1, door.height))
            pygame.draw.rect(s, OUTLINE, (door.right, door.y, 1, door.height))

        # Bogies under the car.
        for bx in (cx + 16, cx + CAR_LEN - 34):
            pygame.draw.rect(s, OUTLINE, (bx, y0 + ROOF_H + SIDE_H, 18, 4))
            pygame.draw.rect(s, (28, 28, 32), (bx + 2, y0 + ROOF_H + SIDE_H + 1, 5, 3))
            pygame.draw.rect(s, (28, 28, 32), (bx + 11, y0 + ROOF_H + SIDE_H + 1, 5, 3))

        # Cab end: wrap-around windshield, destination board, lights.
        if car == front_car:
            fx = cx + 1 if metro.direction < 0 else cx + CAR_LEN - 9
            pygame.draw.rect(s, BAND, (fx, side_y + 2, 8, 11))
            pygame.draw.rect(s, GLASS_PANE, (fx + 1, side_y + 3, 6, 8))
            pygame.draw.line(s, shade(GLASS_PANE, 60), (fx + 1, side_y + 3), (fx + 6, side_y + 3))
            lamp_x = cx + 1 if metro.direction < 0 else cx + CAR_LEN - 5
            pygame.draw.rect(s, HEADLIGHT, (lamp_x, side_y + 15, 4, 3))
            board = pygame.Rect(0, y0 + 3, 38, 6)
            board.x = cx + 5 if metro.direction < 0 else cx + CAR_LEN - 43
            box(s, board, (30, 30, 36))
            dest = view._next_stop(metro)[:11]
            view.labels.append((sprites.text(view.tiny, dest.upper(), BOARD_AMBER), (board.centerx, board.centery)))
        if car == rear_car:
            lamp_x = cx + CAR_LEN - 5 if metro.direction < 0 else cx + 1
            pygame.draw.rect(s, ML_RED, (lamp_x, side_y + 15, 4, 3))

    if dwelling and not doors_visible and open_k > 0:
        for d in door_xs(x):
            s.blit(view.spill, (round(d - DOOR_W / 2) - 4, PLATFORM_1.bottom - 9))

    tag = sprites.text(view.small, f"#{metro.id}", TEXT)
    view.labels.append((tag, (x, y0 + ROOF_H + SIDE_H + 11)))
    body_full = pygame.Rect(left, y0, TRAIN_LEN, ROOF_H + SIDE_H)
    if body_full.collidepoint(view._mouse_world()):
        view.hover = ("train", metro, (x, y0 - 4))
