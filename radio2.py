#!/usr/bin/env python3

import RFM69
from RFM69registers import *
import datetime
import time

NODE = 2
OTHERNODE = 1
NET = 1
KEY = "1234567890123456"
TIMEOUT = 6
TOSLEEP = 0.1

radio = RFM69.RFM69(RF69_433MHZ, NODE, NET, True)
print("class initialized")

#print("reading all registers")
#results = radio.readAllRegs()
#for result in results:
#    print(result)

print("Performing rcCalibration")
radio.rcCalibration()

print("setting high power")
radio.setHighPower(True)
#radio.setPowerLevel(0)

print("Checking temperature")
print(radio.readTemperature(0))

print("setting encryption")
radio.encrypt(KEY)

radio.setFrequency(433500000)

radio.writeReg(REG_BITRATEMSB, RF_BITRATEMSB_1200)
radio.writeReg(REG_BITRATELSB, RF_BITRATELSB_1200)

radio.writeReg(REG_FDEVMSB, RF_FDEVMSB_5000)
radio.writeReg(REG_FDEVLSB, RF_FDEVLSB_5000)

print("starting loop...")
sequence = 0
try:
    while True:
        msg = "I'm radio %d: %d" % (NODE, sequence)
        sequence += 1

        print(f"TX >> {OTHERNODE}: {msg}")
        if radio.sendWithRetry(OTHERNODE, msg, 3, 500):
            print("ACK received")

        print("receiving...")
        radio.receiveBegin()
        timedOut = 0
        while not radio.receiveDone():
            timedOut += TOSLEEP
            time.sleep(TOSLEEP)
            if timedOut > TIMEOUT:
                print("nothing received")
                break

        if timedOut <= TIMEOUT:
            sender = radio.SENDERID
            msg = "".join([chr(letter) for letter in radio.DATA])
            ackReq = radio.ACKRequested()
            print(f"RX << {sender}: {msg} (RSSI: {radio.RSSI})")
            if ackReq:
                print("sending ACK...")
                time.sleep(0.05)
                radio.sendACK()
            time.sleep(TIMEOUT / 2)
except KeyboardInterrupt:
    # Clean up properly to not leave GPIO/SPI in an unusable state
    pass

print("shutting down")
radio.shutdown()
