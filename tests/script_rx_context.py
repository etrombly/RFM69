from RFM69 import Radio, FREQ_433MHZ
import datetime
import time

node_id = 1
network_id = 100

with Radio(FREQ_433MHZ, node_id, network_id, isHighPower=True) as radio:
    print ("Starting loop...")

    while True:
        radio.begin_receive()

        while not radio.has_received_packet():
            time.sleep(0.1)

        packet = radio.get_packet(True)
        print ("Packet Received:")
        print (packet.to_dict())

        time.sleep(0.2)
