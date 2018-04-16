#!/usr/bin/env python2

from RFM69Radio import Radio, FREQ_433MHZ
import datetime
import time

NODE=1
NET=100
TIMEOUT=3
TOSLEEP=0.1
KEY=0

radio = Radio(FREQ_433MHZ, NODE, NET, isHighPower=True)
print ("class initialized")

print ("Performing rcCalibration")
radio.calibrate_radio()

print ("setting high power")
radio._setHighPower(True)

print ("Checking temperature")
print (radio.read_temperature(0))

print ("setting encryption")
radio._encrypt(KEY)

print ("starting loop...")
sequence = 0
while True:

    print ("start recv...")
    radio._receiveBegin()
    timedOut=0
    while not radio._receiveDone():
        timedOut+=TOSLEEP
        time.sleep(TOSLEEP)

    if timedOut > TIMEOUT:
            print ("timed out waiting for recv")
            break

    print ("end recv...")
    print (" *** %s from %s RSSI:%s" % ("".join([chr(letter) for letter in radio.DATA]), radio.SENDERID, radio.RSSI))

    if radio._ACKRequested():
        print ("sending ack...")
        radio._sendACK()
    else:
        print ("ack not requested...")

print ("shutting down")
radio._shutdown()
