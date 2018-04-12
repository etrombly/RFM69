#!/usr/bin/env python2

import sys
import RFM69
from RFM69registers import *

NODE=1
RECEIVER=2
NET=1
KEY="1234567891011121"
TIMEOUT=3
TOSLEEP=0.1
RETIES=30
RETRYWAIT=100
HIGH=False
VERBOSE=True

radio = RFM69.RFM69(RF69_433MHZ, NODE, NET, True)
radio.rcCalibration()
if HIGH:
  if VERBOSE: print "setting high power"
  radio.setHighPower(True)

if VERBOSE: print "setting encryption"
radio.encrypt(KEY)

msg = sys.argv[1]

if VERBOSE: print "* TX to radio 2: " + msg

if radio.sendWithRetry(RECEIVER, msg, RETIES, RETRYWAIT): # sendWithRetry(toAddress, buff = "", retries = 3, retryWaitTime = 10)
  if VERBOSE: print "ack recieved!!!!!!"
  radio.shutdown()
  sys.exit(0)
else:
  if VERBOSE: print "shutting down"
  radio.shutdown()
  sys.exit(1)

