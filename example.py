#!/usr/bin/env python2

import RFM69
from RFM69registers import *
import datetime
import time

network_id = 1
node_id = 1
is_rfm_69HW = True

test = RFM69.RFM69(RF69_915MHZ, node_id, network_id, is_rfm_69HW)
print "class initialized"
print "reading all registers"
results = test.readAllRegs()
for result in results:
    print result
print "Performing rcCalibration"
test.rcCalibration()
print "setting high power"
test.setHighPower(True)
print "Checking temperature"
print test.readTemperature(0)
print "setting encryption"
test.encrypt("1234567891011121")
print "sending blah to 2"
if test.sendWithRetry(2, "blah", 3, 20):
    print "ack recieved"
print "reading"
test.receiveBegin()
while True:
    if test.receiveDone():
        print "%s from %s RSSI:%s" % ("".join([chr(letter) for letter in test.DATA]), test.SENDERID, test.RSSI)
        if test.ACKRequested():
            test.sendACK()
        else:
            test.receiveBegin()
print "shutting down"
test.shutdown()
