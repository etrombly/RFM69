#!/usr/bin/env python3

import RFM69
from RFM69registers import *
import datetime
import time

network_id = 1
node_id = 1
is_rfm_69HW = True

radio = RFM69.RFM69(RF69_433MHZ, node_id, network_id, is_rfm_69HW)
print("class initialized")
print("reading all registers")
results = radio.readAllRegs()
for result in results:
    print(result)
print("Performing rcCalibration")
radio.rcCalibration()
print("setting high power")
radio.setHighPower(True)
#radio.setPowerLevel(31)
print("Checking temperature")
print(radio.readTemperature(0))
print("setting encryption")
radio.encrypt("1234567890123456")

radio.setFrequency(433500000)

radio.writeReg(REG_BITRATEMSB, RF_BITRATEMSB_1200)
radio.writeReg(REG_BITRATELSB, RF_BITRATELSB_1200)

radio.writeReg(REG_FDEVMSB, RF_FDEVMSB_5000)
radio.writeReg(REG_FDEVLSB, RF_FDEVLSB_5000)

freq = radio.getFrequency()
print(f"frequency set to {freq / 1000000} MHz")

print("sending to 2")
if radio.sendWithRetry(2, "012345678901234567890123456789012345678901234567890123456789", 3, 100):
    print("ack received")
time.sleep(0.5)
print("reading (interrupt to stop)")
try:
    while True:
        radio.receiveBegin()
        while not radio.receiveDone():
            time.sleep(.1)
        print("%s from %s RSSI:%s" % ("".join([chr(letter) for letter in radio.DATA]), radio.SENDERID, radio.RSSI))
        if radio.ACKRequested():
            radio.sendACK()
except KeyboardInterrupt:
    # Clean up properly to not leave GPIO/SPI in an unusable state
    pass

print("shutting down")
radio.shutdown()
