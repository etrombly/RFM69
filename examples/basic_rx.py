#!/usr/bin/env python3

import signal, sys
import RFM69
from RFM69registers import RF69_433MHZ
import datetime
import time

node_id    = 1
network_id = 100
frequency  = RF69_433MHZ
high_power = False
encryptkey = "sampleEncryptKey"
interrupt_pin = 18
reset_pin     = 29
radio = None

def signal_handler(signal, frame):
    print ('Stopping...')
    if radio is not None:
        radio.shutdown()
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    print("Starting")
    radio = RFM69.RFM69(frequency, node_id, network_id, high_power, interrupt_pin, reset_pin)

    print ("All registers")
    results = radio.readAllRegs()
    for result in results:
        print (result)

    print ("Performing Calibration")
    radio.rcCalibration()

    print ("Setting high power to {}".format(high_power))
    radio.setHighPower(high_power)

    print ("Radio temperature: {}".format(radio.readTemperature(0)))

    print ("Setting encryption {}".format(encryptkey))
    radio.encrypt(encryptkey)

    print ("Listening")
    while True:
        radio.receiveBegin()
        while not radio.receiveDone():
            time.sleep(.1)

        print ("Packet received from {} (RSSI: {})".format(radio.SENDERID, radio.RSSI))
        print ("Data", radio.DATA)

        if radio.ACKRequested():
            radio.sendACK()



