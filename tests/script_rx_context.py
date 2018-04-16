#!/usr/bin/env python2

from RFM69Radio import Radio, FREQ_433MHZ
import datetime
import time

NODE=1
NET=100
TIMEOUT=3
TOSLEEP=0.1
KEY=0

with Radio(FREQ_433MHZ, NODE, NET, isHighPower=True) as radio:
    print ("class initialized")
    print ("starting loop...")
    sequence = 0
    while True:

        for packet in radio.getPackets():
            print ("end recv...")
            print (packet.to_dict())

        if radio._ACKRequested():
            print ("sending ack...")
            radio._sendACK()
       

        time.sleep(0.2)

