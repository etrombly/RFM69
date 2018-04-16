import time
from RFM69 import Radio, FREQ_433MHZ

to_node_id = 12    # Recipient
attempts = 3       # Attempts to make

with Radio(FREQ_433MHZ, 1, encryptionKey="sampleEncryptKey", isHighPower=True, verbose=True) as radio:
    if radio.send(to_node_id, "Banana", attempts):
        print("Success")
    else:
        print("Failed")
