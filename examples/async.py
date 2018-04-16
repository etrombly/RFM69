import time
from RFM69 import Radio, FREQ_433MHZ
import asyncio
from aiohttp import ClientSession

async def call_API(url, packet):
    async with ClientSession() as session:
        print("Sending packet to server")
        async with session.post(url, json=packet.to_dict('%c')) as response:
            response = await response.read()
            print("Server responded", response)

loop = asyncio.get_event_loop()

with Radio(FREQ_433MHZ, 1, encryptionKey="sampleEncryptKey") as radio:
    while True:
        for packet in radio.getPackets():
            print("Packet received", packet.to_dict())
            loop.run_until_complete(call_API("http://httpbin.org/post", packet))
        time.sleep(1)