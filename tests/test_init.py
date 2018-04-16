import pytest
from RFM69Radio import Radio, FREQ_433MHZ

def test_init_success():
    radio = Radio(FREQ_433MHZ, 1)
    assert type(radio) == Radio

def test_init_bad_interupt():
    with pytest.raises(ValueError) as _:
        Radio(FREQ_433MHZ, 1, interruptPin=0)

def test_init_bad_reset():
    with pytest.raises(ValueError) as _:
        Radio(FREQ_433MHZ, 1, resetPin=0)

def test_init_bad_spi_bus():
    with pytest.raises(IOError) as _:
        Radio(FREQ_433MHZ, 1, spiBus=-1)

def test_init_bad_spi_device():
    with pytest.raises(IOError) as _:
        Radio(FREQ_433MHZ, 1, spiDevice=-1)

# def test_encryption_key_set():
#     with Radio(FREQ_433MHZ, 1, encryptionKey="sampleEncryptKey") as radio:
#         assert radio._enc