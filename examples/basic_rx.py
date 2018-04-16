import time
from RFM69Radio import Radio, FREQ_433MHZ

with Radio(FREQ_433MHZ, 1, encryptionKey="sampleEncryptKey", verbose=True, isHighPower=True,) as radio:
    while True:
        for packet in radio.getPackets():
            print(packet.to_dict())

        time.sleep(1)
        