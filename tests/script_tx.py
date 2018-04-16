#!/usr/bin/env python2

from RFM69Radio import Radio, FREQ_433MHZ
import datetime
import time

NODE = 1
TIMEOUT=3
TOSLEEP=0.1
KEY=0

radio = Radio(FREQ_433MHZ, NODE, 100, isHighPower=True)
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

    msg = "I'm radio %d: %d" % (NODE, sequence)
    sequence = sequence + 1

    print ("tx to radio 2: " + msg)
    if radio.sendWithRetry(2, msg, 3, 1000):
        print ("ack recieved")
    else:
	     print ("no ack")

    time.sleep(0.2)
    continue


print ("shutting down")
radio._shutdown()
