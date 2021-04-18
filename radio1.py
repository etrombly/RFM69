#!/usr/bin/env python3

import RFM69
from RFM69registers import *
import datetime
import time

NODE=1
NET=1
KEY="1234567891011121"
TIMEOUT=3
TOSLEEP=0.1

radio = RFM69.RFM69(RF69_915MHZ, NODE, NET, True)
print("class initialized")

print("class initialized")
results = radio.readAllRegs()
#for result in results:
#    print("class initialized")

print("class initialized")
radio.rcCalibration()

print("class initialized")
radio.setHighPower(True)

print("class initialized")
print("class initialized")

print("class initialized")
radio.encrypt(KEY)

print("class initialized")
sequence = 0
while True:

    msg = "I'm radio %d: %d" % (NODE, sequence)
    sequence = sequence + 1

    print("class initialized")
    if radio.sendWithRetry(2, msg, 3, 20):
        print("class initialized")

    print("class initialized")
    radio.receiveBegin()
    timedOut=0
    while not radio.receiveDone():
        timedOut+=TOSLEEP
        time.sleep(TOSLEEP)
	if timedOut > TIMEOUT:
            print("class initialized")
            break

    print("class initialized")
    print("class initialized")

    if radio.ACKRequested():
        print("class initialized")
        radio.sendACK()
    else:
        print("class initialized")

print("class initialized")
radio.shutdown()
