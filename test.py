import asyncio
import pygame
import sys
import math
import cv2
import numpy as np
import threading
from bleak import BleakClient
from collections import deque

## condfig 
ADDRESS   = "B0:10:A0:74:F3:6D"
CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
CAMERA_URL = "FILL WITH IPHONE STREAM URL"

SCREEN_W = 1280
SCREEN_H = 720

CURVE_LINEAR = "LINEAR"
CURVE_EXPO   = "EXPO"
CURVE_CUBIC  = "CUBIC"
CURVES = [CURVE_LINEAR, CURVE_EXPO, CURVE_CUBIC]
 
## colors
BG      = (10,  12,  20)
PANEL   = (18,  22,  36)
ACCENT  = (0,  200, 255)
ACCENT2 = (255,  60, 120)
TEXT    = (220, 230, 255)
DIM     = (80,   90, 120)
GREEN   = (0,  240, 120)
YELLOW  = (255, 200,   0)

## camera thread 
camera_frame   = None
camera_lock    = threading.Lock()
camera_running = True

def camera_thread_fn():
    global camera_frame, camera_running
    cap = cv2.VideoCapture(CAMERA_URL)
    while camera_running:
        ret, frame = cap.read()
        if ret:
            frame = cv2.resize(frame, (640, 360))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            with camera_lock:
                camera_frame = frame
    cap.release()

## helpers
def apply_curve(v, mode):
    sign = 1 if v >= 0 else -1
    mag  = abs(v)
    if mode == CURVE_LINEAR:
        return v
    elif mode == CURVE_EXPO:
        return sign * (mag ** 1.7)
    elif mode == CURVE_CUBIC:
        return sign * (mag ** 3)
    return v

def scale(v):
    return int((v + 1) / 2 * 255)

def dz(v, threshold=0.1):
    return 0.0 if abs(v) < threshold else v
 
## draw helpers
def draw_panel(surf, rect, color=PANEL, radius=12):
    pygame.draw.rect(surf, color, rect, border_radius=radius)

def draw_label(surf, text, x, y, font, color=DIM):
    s = font.render(text, True, color)
    surf.blit(s, (x, y))

def draw_stick(surf, cx, cy, r, raw_x, raw_y, curve_x, curve_y, label, font):
    pygame.draw.circle(surf, (30, 36, 58), (cx, cy), r)
    pygame.draw.circle(surf, ACCENT, (cx, cy), r, 2)
    pygame.draw.line(surf, (40, 48, 70), (cx - r, cy), (cx + r, cy), 1)
    pygame.draw.line(surf, (40, 48, 70), (cx, cy - r), (cx, cy + r), 1)

    ## raw dot
    rx = cx + int(raw_x * (r - 8))
    ry = cy - int(raw_y * (r - 8))
    pygame.draw.circle(surf, DIM, (rx, ry), 5)

    ## curved dot
    cx2 = cx + int(curve_x * (r - 8))
    cy2 = cy - int(curve_y * (r - 8))
    pygame.draw.circle(surf, ACCENT, (cx2, cy2), 10)
    pygame.draw.circle(surf, (255, 255, 255), (cx2, cy2), 4)

    draw_label(surf, label, cx - r, cy + r + 6, font)

def draw_imu_bar(surf, x, y, w, h, value, vmin, vmax, label, color, font):
    pygame.draw.rect(surf, (25, 30, 50), (x, y, w, h), border_radius=4)
    norm    = max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))
    fill_w  = int(norm * w)
    if fill_w > 0:
        pygame.draw.rect(surf, color, (x, y, fill_w, h), border_radius=4)
    draw_label(surf, f"{label}: {value:+.2f}", x, y - 18, font, TEXT)

def draw_speedometer(surf, cx, cy, r, speed_frac, font_big, font_sm):
    pygame.draw.circle(surf, (20, 25, 42), (cx, cy), r)
    pygame.draw.circle(surf, ACCENT, (cx, cy), r, 2)
    start_angle = math.pi * 1.1
    end_angle   = math.pi * 1.9
    steps = 60
    for i in range(steps):
        t = i / steps
        if t > speed_frac:
            break
        a  = start_angle + t * (end_angle - start_angle)
        px = cx + int(math.cos(a) * (r - 8))
        py = cy - int(math.sin(a) * (r - 8))
        c  = (int(t * 255), int(240 - t * 180), int(120 - t * 120))
        pygame.draw.circle(surf, c, (px, py), 4)

    pct = int(speed_frac * 100)
    txt = font_big.render(f"{pct}%", True, TEXT)
    surf.blit(txt, (cx - txt.get_width() // 2, cy - txt.get_height() // 2))
    lbl = font_sm.render("SPEED", True, DIM)
    surf.blit(lbl, (cx - lbl.get_width() // 2, cy + 20))

def draw_direction_arrow(surf, cx, cy, r, forward, turn, font):
    pygame.draw.circle(surf, (20, 25, 42), (cx, cy), r)
    pygame.draw.circle(surf, ACCENT2, (cx, cy), r, 2)
    mag = math.sqrt(forward ** 2 + turn ** 2)
    if mag > 0.05:
        nx = turn    / mag
        ny = -forward / mag
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
    surf.blit(lbl, (cx - lbl.get_width() // 2, cy + r + 6))
## main
async def main():
    global camera_running

    pygame.init()
    pygame.joystick.init()

    print(f"Controllers found: {pygame.joystick.get_count()}")

    if pygame.joystick.get_count() == 0:
        print("No controller found")
        sys.exit()

    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("RC CAR CONTROL")
    clock = pygame.time.Clock()

    font_lg = pygame.font.SysFont("monospace", 28, bold=True)
    font_md = pygame.font.SysFont("monospace", 18)
    font_sm = pygame.font.SysFont("monospace", 13)

    joy = pygame.joystick.Joystick(0)
    joy.init()

    cam_thread = threading.Thread(target=camera_thread_fn, daemon=True)
    cam_thread.start()

    imu_ax = imu_ay = imu_az = imu_gz = 0.0
    imu_history = deque(maxlen=80)
    curve_idx = 0
    last_msg  = ""
    last_x    = 127
    last_y    = 127

    async with BleakClient(ADDRESS) as client:
        if not client.is_connected:
            print("FAILED TO CONNECT")
            return
        print("Connected ")

        def on_notify(sender, data):
            nonlocal imu_ax, imu_ay, imu_az, imu_gz
            try:
                msg = data.decode().strip()
                if msg.startswith("IMU:"):
                    parts = msg[4:].split(",")
                    if len(parts) == 4:
                        imu_ax = float(parts[0])
                        imu_ay = float(parts[1])
                        imu_az = float(parts[2])
                        imu_gz = float(parts[3])
                        imu_history.append(math.sqrt(imu_ax**2 + imu_ay**2))
            except:
                pass

        await client.start_notify(CHAR_UUID, on_notify)

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_c:
                        curve_idx = (curve_idx + 1) % len(CURVES)
                    if event.key == pygame.K_ESCAPE:
                        running = False

            pygame.event.pump()

            raw_ly = dz(-joy.get_axis(1))
            raw_rx = dz( joy.get_axis(3), 0.2)

            curve_mode = CURVES[curve_idx]
            curved_ly  = apply_curve(raw_ly, curve_mode)
            curved_rx  = apply_curve(raw_rx, curve_mode)

            x = scale(curved_rx)
            y = scale(curved_ly)

            msg = f"X:{x} Y:{y}\n"
            if msg != last_msg:
                try:
                    await client.write_gatt_char(CHAR_UUID, msg.encode(), response=False)
                except:
                    pass
                last_msg = msg
                last_x   = x
                last_y   = y

            ## draw 
            screen.fill(BG)

            # title
            title = font_lg.render("RC CAR CONTROL", True, ACCENT)
            screen.blit(title, (20, 14))
            curve_lbl = font_md.render(f"CURVE: {curve_mode}  [C to cycle]", True, YELLOW)
            screen.blit(curve_lbl, (SCREEN_W - curve_lbl.get_width() - 20, 18))

            # camera
            cam_rect = pygame.Rect(20, 50, 640, 360)
            draw_panel(screen, cam_rect, (14, 18, 30))
            with camera_lock:
                frame = camera_frame
            if frame is not None:
                surf = pygame.surfarray.make_surface(np.rot90(frame))
                surf = pygame.transform.scale(surf, (640, 360))
                screen.blit(surf, (20, 50))
            else:
                no_cam = font_md.render("NO CAMERA FEED", True, DIM)
                screen.blit(no_cam, (20 + 320 - no_cam.get_width() // 2, 230))
            pygame.draw.rect(screen, ACCENT, cam_rect, 2, border_radius=4)

            ## right column
            rx_col = 680

            ## stick panel
            draw_panel(screen, pygame.Rect(rx_col, 50, 580, 220), radius=10)
            stick_r = 70
            draw_stick(screen, rx_col + 100, 160, stick_r,
                       0, raw_ly, 0, curved_ly, "LEFT STICK (FWD)", font_sm)
            draw_stick(screen, rx_col + 380, 160, stick_r,
                       raw_rx, 0, curved_rx, 0, "RIGHT STICK (TURN)", font_sm)
            draw_label(screen, f"Y raw:{raw_ly:+.2f} curved:{curved_ly:+.2f}", rx_col + 20,  58, font_sm, DIM)
            draw_label(screen, f"X raw:{raw_rx:+.2f} curved:{curved_rx:+.2f}", rx_col + 300, 58, font_sm, DIM)

            ## speedo + direction
            draw_panel(screen, pygame.Rect(rx_col, 282, 580, 200), radius=10)
            speed_frac = (abs(curved_ly) + abs(curved_rx)) / 2.0
            draw_speedometer(screen, rx_col + 120, 382, 80, speed_frac, font_lg, font_sm)
            draw_direction_arrow(screen, rx_col + 420, 382, 75, curved_ly, curved_rx, font_sm)

            ## IMU bars
            draw_panel(screen, pygame.Rect(20, 422, 640, 278), radius=10)
            draw_label(screen, "IMU TELEMETRY", 36, 430, font_md, ACCENT)
            bar_x, bar_w, bar_h = 40, 580, 18
            draw_imu_bar(screen, bar_x, 472, bar_w, bar_h, imu_ax, -2,   2,   "ACCEL X",     ACCENT,  font_sm)
            draw_imu_bar(screen, bar_x, 514, bar_w, bar_h, imu_ay, -2,   2,   "ACCEL Y",     GREEN,   font_sm)
            draw_imu_bar(screen, bar_x, 556, bar_w, bar_h, imu_az, -2,   2,   "ACCEL Z",     YELLOW,  font_sm)
            draw_imu_bar(screen, bar_x, 598, bar_w, bar_h, imu_gz, -250, 250, "GYRO Z (yaw)",ACCENT2, font_sm)

            if len(imu_history) > 1:
                pts = [(bar_x + int(i / (imu_history.maxlen - 1) * bar_w),
                        680 - int(min(v / 3.0, 1.0) * 50))
                       for i, v in enumerate(imu_history)]
                pygame.draw.lines(screen, ACCENT, False, pts, 2)
            draw_label(screen, "ACCEL MAGNITUDE", bar_x, 636, font_sm, DIM)

            ## IMU values panel
            draw_panel(screen, pygame.Rect(rx_col, 494, 580, 206), radius=10)
            draw_label(screen, "TELEMETRY VALUES", rx_col + 16, 502, font_md, ACCENT)
            vals = [
                (f"Accel X : {imu_ax:+.3f} g",   ACCENT),
                (f"Accel Y : {imu_ay:+.3f} g",   GREEN),
                (f"Accel Z : {imu_az:+.3f} g",   YELLOW),
                (f"Gyro  Z : {imu_gz:+.1f} deg/s", ACCENT2),
                (f"Send  X : {last_x:3d}   Y : {last_y:3d}", TEXT),
            ]
            for i, (txt, col) in enumerate(vals):
                draw_label(screen, txt, rx_col + 20, 530 + i * 30, font_md, col)

            pygame.display.flip()
            clock.tick(30)
            await asyncio.sleep(0.001)

        camera_running = False
        await client.stop_notify(CHAR_UUID)

    pygame.quit()

asyncio.run(main())
