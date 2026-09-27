import pygame
import sys
import math
import numpy as np
from collections import deque
import time

pygame.init()
print("pygame init done")
pygame.joystick.init()
print(f"Controllers found: {pygame.joystick.get_count()}")

SCREEN_W = 2560
SCREEN_H = 1440

## accerlation curves
CURVE_LINEAR = "LINEAR"
CURVE_EXPO = "EXPO"
CURVE_CUBIC = "CUBIC"
## acceleration curve modes
CURVES = [CURVE_LINEAR, CURVE_EXPO, CURVE_CUBIC]

BG = (10, 12, 20)
PANEL = (18, 22, 26)
ACCENT = (80, 160, 200)
ACCENT2 = (180, 100, 140)
TEXT = (200, 210, 230)
DIM = (100, 110, 140)
GREEN = (100, 180, 120)
RED = (200, 80, 80)
YELLOW = (200, 160, 60)

## apply acceleration curve
def apply_curve(v, mode):
    sign = 1 if v >= 0 else -1
    mag = abs(v)
    if mode == CURVE_LINEAR:
        return v
    elif mode == CURVE_EXPO:
        return  sign * (mag ** 1.7)
    elif mode == CURVE_CUBIC:
        return sign * (mag ** 3)
    return v

## draw helpers

## draw rounded rectangle
def draw_panel(surf, rect, color=PANEL, radius=12):
    pygame.draw.rect(surf, color, rect, border_radius=radius)

## render text
def draw_label(surf, text, x, y, font, color=DIM):
    s = font.render(text, True, color)
    surf.blit(s, (x, y))

## visualize joystick
def draw_stick(surf, cx, cy, r, raw_x, raw_y, curve_x, curve_y, label, font):
    pygame.draw.circle(surf, (30, 36, 58), (cx, cy), r)
    pygame.draw.circle(surf, ACCENT, (cx, cy), r, 2)

    pygame.draw.line(surf, (40, 48, 70), (cx - r, cy), (cx + r, cy), 1)
    pygame.draw.line(surf, (40, 48, 70), (cx, cy - r), (cx, cy + r), 1)

    rx = cx + int(raw_x * (r - 8))
    ry = cy - int(raw_y * (r - 8))
    pygame.draw.circle(surf, DIM, (rx, ry), 5)

    cx2 = cx + int(curve_x * (r - 8))
    cy2 = cy - int(curve_y * (r - 8))
    pygame.draw.circle(surf, ACCENT, (cx2, cy2), 10)
    pygame.draw.circle(surf, (255, 255, 255), (cx2, cy2), 4)

    draw_label(surf, label, cx - r, cy + r + 12, font, DIM)

## draw vertical bar
def draw_vertical_bar(surf, x, y, w, h, value, vmin, vmax, label, color, font):
    norm = (value - vmin) / (vmax - vmin)
    norm = max(0.0, min(1.0, norm))

    ## draw background bar
    pygame.draw.rect(surf, (25, 30, 50), (x, y, w, h), border_radius=4)

    ## draw filled portion from bottom
    fill_h = int(norm * h)
    if fill_h > 0:
        pygame.draw.rect(surf, color, (x, y + h - fill_h, w, fill_h), border_radius=4)

    ## draw label below bar
    lbl_text = f"{label}\n{value:+.2f}"
    for i, line in enumerate(lbl_text.split('\n')):
        lbl = font.render(line, True, TEXT)
        surf.blit(lbl, (x - lbl.get_width()//2 + w//2, y + h + 10 + i*25))

## speed gauge
def draw_speedometer(surf, cx, cy, r, speed_frac, font_big, font_sm):
    pygame.draw.circle(surf, (20, 25, 42), (cx, cy), r)
    pygame.draw.circle(surf, ACCENT, (cx, cy), r, 2)

    start_angle = math.pi * 1.1
    end_angle = math.pi * 1.9
    steps = 60
    for i in range(steps):
        t = i / steps
        if t > speed_frac:
            break
        a = start_angle + t * (end_angle - start_angle)
        px = cx + int(math.cos(a) * (r - 8))
        py = cy - int(math.sin(a) * (r - 8))
        color = (
            int(80 + t * 100),
            int(160 - t * 100),
            int(200 - t * 100)
        )
        pygame.draw.circle(surf, color, (px, py), 4)

    pct = int(speed_frac * 100)
    txt = font_big.render(f"{pct}%", True, TEXT)
    surf.blit(txt, (cx - txt.get_width() // 2, cy - txt.get_height() // 2))
    lbl = font_sm.render("SPEED", True, DIM)
    surf.blit(lbl, (cx - lbl.get_width() // 2, cy + 30))

## direction indicator
def draw_direction_arrow(surf, cx, cy, r, forward, turn, font):
    pygame.draw.circle(surf, (20, 25, 42), (cx, cy), r)
    pygame.draw.circle(surf, ACCENT2, (cx, cy), r, 2)

    mag = math.sqrt(forward**2 + turn**2)
    if mag > 0.05:
        nx = turn / max(mag, 1)
        ny = -forward / max(mag, 1)
        ex = cx + int(nx * (r - 12))
        ey = cy + int(ny * (r - 12))
        pygame.draw.line(surf, ACCENT2, (cx, cy), (ex, ey), 3)

        angle = math.atan2(ey - cy, ex - cx)
        for da in [0.4, -0.4]:
            ax = ex - int(math.cos(angle + da) * 12)
            ay = ey - int(math.sin(angle + da) * 12)
            pygame.draw.line(surf, ACCENT2, (ex, ey), (ax, ay), 3)
    else:
        pygame.draw.circle(surf, DIM, (cx, cy), 6)

    lbl = font.render("DIR", True, DIM)
    surf.blit(lbl, (cx - lbl.get_width() // 2, cy + r + 12))

## demo main loop
def main():
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("RC CAR TELEMETRY - DEMO MODE")
    clock = pygame.time.Clock()

    font_lg = pygame.font.SysFont("arial", 56, bold=True)
    font_md = pygame.font.SysFont("arial", 36, bold=True)
    font_sm = pygame.font.SysFont("arial", 26, bold=True)

    ## simulated data
    imu_ax = 0.0
    imu_ay = 0.0
    imu_az = 0.0
    imu_gz = 0.0
    imu_history = deque(maxlen=80)

    curve_idx = 0
    raw_ly = 0.0
    raw_rx = 0.0
    curved_ly = 0.0
    curved_rx = 0.0
    last_x = 127
    last_y = 127

    ## generate dummy camera frame
    dummy_frame = np.random.randint(30, 60, (260, 640, 3), dtype=np.uint8)

    running = True
    frame_count = 0

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_c:
                    curve_idx = (curve_idx + 1) % len(CURVES)
                if event.key == pygame.K_ESCAPE:
                    running = False

        ## simulate oscillating control values
        frame_count += 1
        t = frame_count * 0.01
        raw_ly = math.sin(t) * 0.7
        raw_rx = math.cos(t * 0.5) * 0.5

        curve_mode = CURVES[curve_idx]
        curved_ly = apply_curve(raw_ly, curve_mode)
        curved_rx = apply_curve(raw_rx, curve_mode)

        ## simulate IMU data
        imu_ax = math.sin(t * 0.5) * 1.2
        imu_ay = math.cos(t * 0.7) * 0.8
        imu_az = 0.5 + math.sin(t * 0.3) * 0.3
        imu_gz = math.sin(t * 1.5) * 60
        imu_history.append(math.sqrt(imu_ax**2 + imu_ay**2))

        last_x = int((curved_rx + 1) / 2 * 255)
        last_y = int((curved_ly + 1) / 2 * 255)

        ## draw
        screen.fill(BG)

        ## title bar
        title = font_lg.render("RC CAR CONTROL", True, ACCENT)
        screen.blit(title, (20, 14))
        curve_lbl = font_md.render(f"CURVE: {curve_mode} [C to cycle]", True, TEXT)
        screen.blit(curve_lbl, (SCREEN_W - curve_lbl.get_width() - 20, 18))

        ## camera feed: on the left
        cam_rect = pygame.Rect(40, 100, 1280, 720)

        surf = pygame.surfarray.make_surface(dummy_frame.swapaxes(0, 1))
        surf = pygame.transform.scale(surf, (1280, 720))
        screen.blit(surf, (40, 100))

        pygame.draw.rect(screen, ACCENT, cam_rect, 4, border_radius=8)

        ## right column
        rx_col = 1360

        ## stick visualizers
        draw_panel(screen, pygame.Rect(rx_col, 100, 1160, 440), radius=10)

        stick_r = 140
        ## left stick
        draw_stick(screen,
                   rx_col + 200, 280,
                   stick_r,
                   0, raw_ly,
                   0, curved_ly,
                   "LEFT STICK", font_sm)

        ## right stick
        draw_stick(screen,
                   rx_col + 760, 280,
                   stick_r,
                   0, raw_rx,
                   0, curved_rx,
                   "RIGHT STICK", font_sm)

        ## stick values
        draw_label(screen, f"Forward: {curved_ly:+.2f}", rx_col + 40, 50, font_sm, DIM)
        draw_label(screen, f"Steering: {curved_rx:+.2f}", rx_col + 600, 50, font_sm, DIM)

        ## speedometer + direction
        draw_panel(screen, pygame.Rect(rx_col, 564, 1160, 400), radius=10)

        speed_frac = (abs(curved_ly) + abs(curved_rx)) / 2.0
        draw_speedometer(screen, rx_col + 240, 764, 160, speed_frac, font_lg, font_sm)
        draw_direction_arrow(screen, rx_col + 840, 764, 150, curved_ly, curved_rx, font_sm)

        ## IMU panel with vertical bars
        draw_panel(screen, pygame.Rect(40, 844, 1280, 556), radius=10)
        draw_label(screen, "IMU TELEMETRY", 72, 860, font_md, ACCENT)

        ## vertical bars arranged side by side
        bar_start_x = 120
        bar_spacing = 290
        bar_w = 60
        bar_h = 200
        bar_y = 920

        draw_vertical_bar(screen, bar_start_x, bar_y, bar_w, bar_h, imu_ax, -2, 2, "ACCEL X", ACCENT, font_sm)
        draw_vertical_bar(screen, bar_start_x + bar_spacing, bar_y, bar_w, bar_h, imu_ay, -2, 2, "ACCEL Y", ACCENT, font_sm)
        draw_vertical_bar(screen, bar_start_x + bar_spacing*2, bar_y, bar_w, bar_h, imu_az, -2, 2, "ACCEL Z", ACCENT, font_sm)
        draw_vertical_bar(screen, bar_start_x + bar_spacing*3, bar_y, bar_w, bar_h, imu_gz, -2, 2, "GYRO Z", ACCENT2, font_sm)

        ## IMU right panel
        draw_panel(screen, pygame.Rect(rx_col, 988, 1160, 412), radius=10)
        draw_label(screen, "TELEMETRY VALUES", rx_col + 32, 1004, font_md, ACCENT)
        vals = [
            (f"Accel X : {imu_ax:+.3f} g", ACCENT),
            (f"Accel Y : {imu_ay:+.3f} g", ACCENT),
            (f"Accel Z : {imu_az:+.3f} g", ACCENT),
            (f"Gyro Z : {imu_gz:+.1f} °/s", ACCENT2),
            (f"Send X : {last_x:3d} Y : {last_y:3d}", TEXT),
        ]
        for i, (txt, col) in enumerate(vals):
            draw_label(screen, txt, rx_col + 40, 1060 + i * 30, font_md, col)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()
