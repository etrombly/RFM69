import pytest
import time
from RFM69 import Radio, FREQ_433MHZ


def test_transmit():
    with Radio(FREQ_433MHZ, 1, 100, isHighPower=True, verbose=True) as radio:
        success = radio.send(2, "Banana", attempts=5, waitTime=100)
        assert success == True

def test_receive():
    with Radio(FREQ_433MHZ, 1, 100, isHighPower=True, verbose=True) as radio:
        while True:
            for _ in radio.get_packets():
                assert True
                return True
            time.sleep(.1)
