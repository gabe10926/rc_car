import asyncio
import pygame
import sys
import math
import cv2
import numpy as np
from bleak import BleakClient
from collections import deque

## init pygame and controller
pygame.init()
print("pygame init done")
pygame.joystick.init()
print(f"Controllers found: {pygame.joystick.get_count()}")

## config for the bluetooth connection
## bluetooth device address
ADDRESS = "B0:10:A0:74:F3:6D"
CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

## iphone camera streaming settup
CAMERA_URL = "FILL LATER WITH THE ACTUAL IPHONE STREAM URL"

SCREEN_W = 2560
SCREEN_H = 1440

## accerlation curves
CURVE_LINEAR = "LINEAR"
CURVE_EXPO = "EXPO"
CURVE_CUBIC = "CUBIC"
CURVES = [CURVE_LINEAR,CURVE_EXPO,CURVE_CUBIC]

BG = (10, 12, 20)
PANEL = (18, 22, 26)
ACCENT = (80, 160, 200)
ACCENT2 = (180, 100, 140)
TEXT = (200, 210, 230)
DIM = (100, 110, 140)
GREEN = (100, 180, 120)
RED = (200, 80, 80)
YELLOW = (200, 160, 60)

## apply acceleration curve based on mode
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


## helpers
## scale analog stick value to 0-255
def scale(v):
    return int((v +1)/2 *255)

## deadzone filter
def dz(v, threshold=0.1):
    return 0.0 if abs(v) < threshold else v

## camera logic
import threading

camera_frame = None
camera_lock = threading.Lock()
camera_running = True

## camera capture thread
def camera_thread_fn():
    global camera_frame, camera_running
    cap = cv2.VideoCapture(CAMERA_URL)
    while camera_running:
        ret, frame = cap.read()
        if ret:
            ## resize to fit camera panel
            frame = cv2.resize(frame, (640, 260))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            with camera_lock:
                camera_frame = frame
    cap.release()

## draw helpers

## draw rounded rectangle panel
def draw_panel(surf, rect, color=PANEL, radius=12):
    pygame.draw.rect(surf, color, rect, border_radius=radius)

## render text label
def draw_label(surf, text, x, y, font, color=DIM):
    s = font.render(text, True, color)
    surf.blit(s, (x,y))

## draw joystick visualization
def draw_stick(surf, cx, cy, r, raw_x, raw_y, curve_x, curve_y, label, font):
    pygame.draw.circle(surf, (30, 36, 58), (cx, cy), r)
    pygame.draw.circle(surf, ACCENT, (cx, cy), r, 2)

    ## crosshair
    pygame.draw.line(surf, (40, 48, 70), (cx -r, cy), (cx + r, cy), 1)
    pygame.draw.line(surf, (40, 48, 70), (cx, cy-r), (cx, cy +r), 1)

    ## raw position (dim)
    rx = cx + int(raw_x * (r-8))
    ry = cy - int(raw_y * (r-8))
    pygame.draw.circle(surf, DIM, (rx, ry), 5)

    ## curved position (bright)
    cx2 = cx + int(curve_x * (r-8))
    cy2 = cy - int(curve_y * (r-8))
    pygame.draw.circle(surf, ACCENT, (cx2, cy2), 10)
    pygame.draw.circle(surf, (255, 255, 255), (cx2, cy2), 4)

    draw_label(surf, label, cx - r - 20, cy + r + 40, font, DIM)

## draw vertical bar gauge
def draw_vertical_bar(surf, x, y, w, h, value, vmin, vmax, label, color, font):
    ## vertical bar for IMU value
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

## draw speed gauge
def draw_speedometer(surf, cx, cy, r, speed_frac, font_big, font_sm):
    pygame.draw.circle(surf, (20, 25, 42), (cx, cy), r)
    pygame.draw.circle(surf, ACCENT, (cx, cy), r, 2)

    start_angle = math.pi * 1.1
    end_angle = math.pi * 1.9
    sweep = (end_angle - start_angle) * speed_frac
    steps = 60
    for i in range(steps):
        t = i / steps
        if t > speed_frac:
            break
        a = start_angle + t * (end_angle - start_angle)
        px = cx + int(math.cos(a) * (r-8))
        py = cy - int(math.sin(a) * (r-8))
        color = (
            int(80 + t * 100),
            int(160 - t * 100),
            int(200 - t * 100)
        )
        pygame.draw.circle(surf, color, (px, py), 4)

    pct = int(speed_frac * 100)
    txt = font_big.render(f"{pct}%", True, TEXT)
    surf.blit(txt, (cx - txt.get_width() // 2, cy - txt.get_height() //2))
    lbl = font_sm.render("SPEED", True, DIM)
    surf.blit(lbl, (cx - lbl.get_width() // 2, cy + 70))

## draw direction indicator
def draw_direction_arrow(surf, cx, cy, r, forward, turn, font):
    pygame.draw.circle(surf, (20, 25, 42), (cx, cy), r)
    pygame.draw.circle(surf, ACCENT2, (cx, cy), r, 2)

    mag = math.sqrt(forward**2 + turn**2)
    if mag > 0.05:
        nx = turn /max(mag, 1)
        ny = -forward / max(mag, 1)
        ex = cx + int(nx * (r-12))
        ey = cy + int(ny * (r-12))
        pygame.draw.line(surf, ACCENT2, (cx, cy), (ex, ey), 3)

        ## arrowhead
        angle = math.atan2(ey -cy, ex - cx)
        for da in [0.4, -0.4]:
            ax = ex - int(math.cos(angle + da) * 12)
            ay = ey - int(math.sin(angle + da) * 12)
            pygame.draw.line(surf, ACCENT2, (ex, ey), (ax, ay), 3)

    else:
        pygame.draw.circle(surf, DIM, (cx, cy), 6)

    lbl = font.render("DIR", True, DIM)
    surf.blit(lbl, (cx - lbl.get_width() // 2, cy + r + 40))

    ## main async loop
async def main():
        global camera_running

        pygame.init()
        pygame.joystick.init()


        screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("RC CAR CONTROL")
        clock = pygame.time.Clock()

        font_lg = pygame.font.SysFont("arial", 56, bold=True)
        font_md = pygame.font.SysFont("arial", 36, bold=True)
        font_sm = pygame.font.SysFont("arial", 26, bold=True)

        if pygame.joystick.get_count() == 0:
            print("No Controller found")
            sys.exit()

        joy = pygame.joystick.Joystick(0)
        joy.init()

        ## start camera thread
        cam_thread = threading.Thread(target=camera_thread_fn, daemon=True)
        cam_thread.start()

        ## IMU state
        imu_ax = imu_ay = imu_az = imu_gz = 0.0
        imu_history = deque(maxlen=80)

        curve_idx = 0 ## current curve mode index

        last_msg = ""
        last_x = 127
        last_y = 127

        async with BleakClient(ADDRESS) as client:
            if not client.is_connected:
                print("FAILED TO CONNECT")
                return
            print("Connected")

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
                            curve_idx = (curve_idx +1) % len(CURVES)
                        if event.key == pygame.K_ESCAPE:
                            running = False

                pygame.event.pump()

                ## read sticks
                raw_ly = dz(-joy.get_axis(1)) # sitck y
                raw_rx = dz(joy.get_axis(3))  ## right stick

                curve_mode = CURVES[curve_idx]
                curved_ly = apply_curve(raw_ly, curve_mode)
                curved_rx = apply_curve(raw_rx, curve_mode)

                x = scale(curved_rx)
                y = scale(curved_ly)

                msg = f"X:{x} Y:{y}\n"
                if msg != last_msg:
                    try:
                        await client.write_gatt_char(CHAR_UUID, msg.encode(), response=False)
                    except:
                        pass
                    last_msg = msg
                    last_x = x
                    last_y = y


                    ## draw
                    screen.fill(BG)

                    ## title bar
                    title = font_lg.render("RC CAR CONTROL", True, ACCENT)
                    screen.blit(title, (40, 28))
                    curve_lbl = font_md.render(f"CURVE: {curve_mode} [C to cycle]", True, TEXT)
                    screen.blit(curve_lbl, (SCREEN_W - curve_lbl.get_width() - 40, 36))


                    ## camera feed: on the left
                    cam_rect = pygame.Rect(40, 100, 1280, 720)
                    with camera_lock:
                        frame = camera_frame
                    if frame is not None:
                        surf = pygame.surfarray.make_surface(np.rot90(frame))
                        surf = pygame.transform.scale(surf, (1280, 720))
                        screen.blit(surf, (40, 100))
                    else:
                        draw_panel(screen, cam_rect, (14, 18, 30))
                        no_cam = font_md.render("NO CAMERA FEED", True, DIM)
                        screen.blit(no_cam, (40 + 1280//2 - no_cam.get_width() //2, 100 + 360 - 20))

                    pygame.draw.rect(screen, ACCENT, cam_rect, 4, border_radius=8)

                    rx_col = 1360

                    ## stick visualizers
                    draw_panel(screen, pygame.Rect(rx_col, 100, 1160, 440), radius=20)

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
                               "RIGHT STICK", font_sm
                               )

                    ## stick values
                    draw_label(screen, f"Forward: {curved_ly:+.2f}", rx_col + 40, 116, font_sm, DIM)
                    draw_label(screen, f"Steering: {curved_rx:+.2f}", rx_col + 600, 116, font_sm, DIM)

                    ## speedmomeeter + direction
                    draw_panel(screen, pygame.Rect(rx_col, 564, 1160, 400), radius=20)

                    speed_frac = (abs(curved_ly) + abs(curved_rx)) / 2.0
                    draw_speedometer(screen, rx_col + 240, 764, 160, speed_frac, font_lg, font_sm)
                    draw_direction_arrow(screen, rx_col + 840, 764, 150, curved_ly, curved_rx, font_sm)

                    ## imu panel with vertical bars
                    draw_panel(screen, pygame.Rect(40, 844, 1280, 556), radius=20)
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


                    ## imu right panel
                    draw_panel(screen, pygame.Rect(rx_col, 988, 1160, 412), radius=20)
                    draw_label(screen, "TELEMETRY VALUES", rx_col + 32, 1004, font_md, ACCENT)
                    vals = [
                        (f"Accel X : {imu_ax:+.3f} g", ACCENT),
                        (f"Accel Y : {imu_ay:+.3f} g", ACCENT),
                        (f"Accel Z : {imu_az:+.3f} g", ACCENT),
                        (f"Gyro Z : {imu_gz:+.1f} °/s", ACCENT2),
                        (f"Send X : {last_x:3d} Y : {last_y:3d}", TEXT),
                    ]
                    for i, (txt, col) in enumerate(vals):
                        draw_label(screen, txt, rx_col + 40, 1060 + i * 60, font_md, col)

                    pygame.display.flip()
                    clock.tick(30)
                    await asyncio.sleep(0.001)

                    camera_running = False
                    await client.stop_notify(CHAR_UUID)

                pygame.quit()

            asyncio.run(main())
