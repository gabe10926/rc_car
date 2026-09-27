import asyncio
from bleak import BleakClient
import pygame
import sys

ADDRESS = "B0:10:A0:74:F3:6D"
CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("No controller found")
    sys.exit()

joy = pygame.joystick.Joystick(0)
joy.init()

print("Controls:")
print("  DPAD UP    -> Motor A (LEFT  side: M1+M4) FORWARD")
print("  DPAD DOWN  -> Motor A (LEFT  side: M1+M4) REVERSE")
print("  DPAD RIGHT -> Motor B (RIGHT side: M2+M3) FORWARD")
print("  DPAD LEFT  -> Motor B (RIGHT side: M2+M3) REVERSE")
print("  No input   -> STOP")

async def main():
    async with BleakClient(ADDRESS) as client:
        if not client.is_connected:
            print("FAILED TO CONNECT")
            return

        print("Connected ")
        last_cmd = ""

        while True:
            pygame.event.pump()

            hat = joy.get_hat(0)  # (x, y): x=-1/0/1, y=-1/0/1
            hx, hy = hat

            if hy == 1:
                cmd = "MA_FWD"   # dpad up -> left motors forward
            elif hy == -1:
                cmd = "MA_REV"   # dpad down  -> left motors reverse
            elif hx == 1:
                cmd = "MB_FWD"   # dpad right -> right motors forward
            elif hx == -1:
                cmd = "MB_REV"   # dpad left  -> right motors reverse
            else:
                cmd = "STOP"

            if cmd != last_cmd:
                await client.write_gatt_char(
                    CHAR_UUID,
                    (cmd + "\n").encode(),
                    response=False
                )
                print(f"SENT: {cmd}")
                last_cmd = cmd

            await asyncio.sleep(0.05)

asyncio.run(main())
