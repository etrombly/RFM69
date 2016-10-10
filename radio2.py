#!/usr/bin/env python2

import RFM69
from RFM69registers import *
import datetime
import time

NODE=2
NET=1
KEY="1234567891011121"

radio = RFM69.RFM69(RF69_915MHZ, NODE, NET, True)
print "class initialized"

print "reading all registers"
results = radio.readAllRegs()
#for result in results:
#    print result

print "Performing rcCalibration"
radio.rcCalibration()

print "setting high power"
radio.setHighPower(True)

print "Checking temperature"
print radio.readTemperature(0)

print "setting encryption"
radio.encrypt(KEY)

sequence=0
print "starting loop..."
while True:


    msg = "I'm radio %d: %d" % (NODE, sequence)
    sequence = sequence + 1

    print "tx to radio 1: " + msg
    if radio.sendWithRetry(1, msg, 3, 20):
        print "ack recieved"

    print "starting recv..."
    radio.receiveBegin()
    while not radio.receiveDone():
        time.sleep(1)

    print "end recv..."
    print " ### %s from %s RSSI:%s " % ("".join([chr(letter) for letter in radio.DATA]), radio.SENDERID, radio.RSSI)

    if radio.ACKRequested():
        radio.sendACK()
    else:
        print "ack not requested..."

print "shutting down"
radio.shutdown()
