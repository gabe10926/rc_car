import asyncio
from bleak import BleakClient
import pygame
import sys

ADDRESS = "B0:10:A0:74:F3:6D"
CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("No controller")
    sys.exit()

joy = pygame.joystick.Joystick(0)
joy.init()

def scale(v):
    return int((v + 1) / 2 * 255)

def dz(v):
    return 0 if abs(v) < 0.1 else v

## movement commands matching the Arduino differential drive:
## X: turn (0=left, 127=center, 255=right)
## Y: forward/backward (0=backward, 127=stop, 255=forward)

def go_forward(speed=255):
    ## forward > 0, turn = 0  ->  both motors forward
    return f"X:127 Y:255\n"

def go_backward(speed=255):
    ## forward < 0, turn = 0  ->  both motors backward, right motor reversed vs forward
    return f"X:127 Y:0\n"

def turn_left():
    ## forward = 0, turn < 0  ->  left backward, right forward
    return f"X:0 Y:127\n"

def turn_right():
    ## turn_left logic reversed on left/right: left forward, right backward
    ## forward = 0, turn > 0  ->  left forward, right backward
    return f"X:255 Y:127\n"

async def main():
    async with BleakClient(ADDRESS) as client:
        if not client.is_connected:
            print("FAILED TO CONNECT")
            return

        print("Connected")

        last_msg = ""

        while True:
            pygame.event.pump()

            ly = -joy.get_axis(1)
            rx = joy.get_axis(3)  ## change if needed

            ly = dz(ly)
            rx = dz(rx)

            x = scale(rx)
            y = scale(ly)

            msg = f"X:{x} Y:{y}\n"

            if msg != last_msg:
                await client.write_gatt_char(
                    CHAR_UUID,
                    msg.encode(),
                    response=False
                )
                print("SENT:", msg.strip())
                last_msg = msg

            await asyncio.sleep(0.05)

asyncio.run(main())
