from RFM69 import Radio, FREQ_433MHZ
import datetime
import time

node_id = 1
network_id = 100

radio = Radio(FREQ_433MHZ, node_id, network_id, isHighPower=True)

print ("Performing Calibration")
radio.calibrate_radio()

print ("Checking temperature")
print (radio.read_temperature(0))

print ("Starting loop...")
while True:

    radio.begin_receive()

    while not radio.has_received_packet():
        time.sleep(0.1)

    packet = radio.get_packet(False)
    print ("Packet Received:")
    print(packet)    

    if radio.ack_requested():
        print ("Sending ack.")
        radio.send_ack()
   
print ("Shutting down")
radio._shutdown()
