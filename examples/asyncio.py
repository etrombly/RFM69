# The next two lines are just to make the examples work in this directory for now
import sys
sys.path.append("../")
# --------------------

import signal
import sys, json, time, string, datetime
import asyncio
from aiohttp import ClientSession
from RFM69 import RFM69Radio
from RFM69registers import RF69_433MHZ 

loop  = None
radio = None

def init_radio(node_id=1, network=100, high_power=False, interrupt_pin=18, reset_pin=29):
    radio = RFM69Radio(RFM69Radio.FREQ_433MHZ, node_id, network, high_power, interrupt_pin, reset_pin)
    print ("Calibrating")
    radio.rcCalibration()
    print ("Setting high power to False - RPI can't supply enough current for high power")
    radio.setHighPower(False)
    print ("Set encryption")
    radio.encrypt("sampleEncryptKey")
    return radio
   
def terminate_radio():
    print ("Shutting down radio")
    radio.shutdown()    

async def process_message(sender, rssi, message):
    url = "http://localhost/api/"
    async with ClientSession() as session:
        async with session.get(url) as response:
            response = await response.read()
            print(response)

async def tx(msg, retries=3, wait_ms=100):
    if radio.sendWithRetry(2, msg, retries, wait_ms):
        print ("Ack Received")
        return
    print ("NO Ack")

async def rx():
    while True:
        radio.receiveBegin()
        if not radio.receiveDone():
            asyncio.sleep(0)
        # Prepare data
        data = "".join([chr(letter) for letter in radio.DATA])
        # Add task to process message
        loop.create_task(process_message(radio.SENDERID, radio.RSSI, data))
        # Must come last as it overwrites radio vars
        if radio.ACKRequested():
            radio.sendACK()
    

# =============================================================================
# Main event loop manager
# =============================================================================

def signal_handler(signal, frame):
    print ('Stopping...')
    if loop is not None:
        loop.stop()
    if radio is not None:
        terminate_radio()
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    radio = init_radio()

    loop = asyncio.get_event_loop()
    loop.create_task(rx())
    loop.run_forever()
    loop.close()

