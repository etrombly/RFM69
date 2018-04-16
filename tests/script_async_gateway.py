import asyncio
from aiohttp import ClientSession
from RFM69 import Radio, FREQ_433MHZ

async def call_API(url, packet):
    async with ClientSession() as session:
        print("Sending packet to server")
        async with session.post(url, json=packet.to_dict('%c')) as response:
            response = await response.read()
            print("Server responded", response)

async def receiver(radio):
    while True:    
        print("Receiver")
        for packet in radio.get_packets():
            print("Packet received", packet.to_dict())
            await call_API("http://httpbin.org/post", packet)
        await asyncio.sleep(10)

async def send(radio, to, message):
    print ("Sending")
    if radio.send(to, message, attempts=3, waitTime=100):
        print ("Acknowledgement received")
    else:
        print ("No Acknowledgement")
    
async def pinger(radio):
    print("Pinger")
    counter = 0
    while True:
        await send(radio, 2, "ping {}".format(counter))
        counter += 1
        await asyncio.sleep(5)


loop = asyncio.get_event_loop()
node_id = 1
network_id = 100
with Radio(FREQ_433MHZ, node_id, network_id, isHighPower=True, verbose=False) as radio:
    print ("Started radio")
    loop.create_task(receiver(radio))
    loop.create_task(pinger(radio))
    loop.run_forever()

loop.close()
