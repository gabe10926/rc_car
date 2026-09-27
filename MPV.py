import asyncio
from bleak import BleakClient

ADDRESS = "B0:10:A0:74:F3:6D"  # HMSoft address
UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

async def main():
    async with BleakClient(ADDRESS) as client:
        print("Connected!")

        while True:
            msg = "X:128 Y:255\n"
            await client.write_gatt_char(UUID, msg.encode())
            await asyncio.sleep(1)

asyncio.run(main())
