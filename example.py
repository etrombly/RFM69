#!/usr/bin/env python

import RFM69
from RFM69registers import *

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
test.send(2, "blah", False)
#print "setting encryption"
#test.encrypt("123456789101112")
print "sending blah to 2"
test.send(2, "blah", True)
print "reading"
while True:
    test.receiveBegin()
    while not test.receiveDone():
        pass
    if test.ACKRequested():
        print "sending ack"
        test.sendACK("ok")
    print "".join([chr(letter) for letter in test.DATA])
print "shutting down"
test.shutdown()
