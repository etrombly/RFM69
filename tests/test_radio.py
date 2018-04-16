import pytest
import time
from RFM69Radio import Radio, FREQ_433MHZ


def test_transmit():
    with Radio(FREQ_433MHZ, 1) as radio:
        success = radio.send(2, "Banana", 3, 500)
        assert success == True

# @pytest.mark.timeout(15)å
def test_receive():
    with Radio(FREQ_433MHZ, 1, verbose=True, promiscuousMode=True) as radio:
        while True:
            for _ in radio.getPackets():
                assert True 
            time.sleep(.1)
    