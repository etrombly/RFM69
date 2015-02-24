#!/usr/bin/env python

import RFM69
from RFM69registers import *
import datetime

test = RFM69.RFM69(RF69_915MHZ, 1, 1, True)
test.promiscuous(True)
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
print "sending blah to 2"
if test.sendWithRetry(2, "blah", 3, 20):
    print "ack recieved"
#print "setting encryption"
#test.encrypt("123456789101112")
#print "sending blah to 2"
#if test.sendWithRetry(2, "blah"):
#    print "ack recieved"
print "reading"
while False:
    test.receiveBegin()
    while not test.receiveDone():
        pass
    recieved_time = datetime.datetime.now()
    if test.ACKRequested():
        print "sending ack"
        test.sendACK("ok")
        sent_time = datetime.datetime.now()
        elapsed_time = sent_time - recieved_time
        print "responded in %s milliseconds" % (elapsed_time.total_seconds() * 1000,)
    print "".join([chr(letter) for letter in test.DATA])
print "shutting down"
test.shutdown()
