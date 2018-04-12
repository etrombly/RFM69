#!/usr/bin/env python2

import RFM69
from RFM69registers import *
import datetime
import time

NODE=2
NET=1
KEY="1234567891011121"
TIMEOUT=99999
TOSLEEP=0.1
VERBOSE=True

radio = RFM69.RFM69(RF69_433MHZ, NODE, NET, True)

radio.rcCalibration()

if VERBOSE: print "setting encryption"
radio.encrypt(KEY)

sequence=0
if VERBOSE: print "starting loop..."
while True:
    sequence = sequence + 1

    if VERBOSE: print "starting recv..."
    radio.receiveBegin()
    timedOut=0
    while not radio.receiveDone():
        timedOut+=TOSLEEP
        time.sleep(TOSLEEP)
        if timedOut > TIMEOUT:
            if VERBOSE: print "timed out waiting for recv"
            break

    if VERBOSE: print "end recv..."
    print " ### %s from %s RSSI:%s " % ("".join([chr(letter) for letter in radio.DATA]), radio.SENDERID, radio.RSSI)

    if radio.ACKRequested():
        radio.sendACK()
    else:
        if VERBOSE: print "ack not requested..."

if VERBOSE: print "shutting down"
radio.shutdown()

