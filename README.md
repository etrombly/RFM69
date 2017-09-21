# Main repo

* https://github.com/etrombly/RFM69

# Description

This is a port of the RFM69 library for arduino from https://github.com/LowPowerLab/RFM69 to python for raspberry pi.

# Hardware setup

Attach the RFM69 as follows:

| RFM pin | Pi pin  
| ------- |-------
| 3v3     | 17  
| DIO0    | 18 (GPIO24)  
| MOSI    | 19  
| MISO    | 21  
| CLK     | 23  
| NSS     | 24  
| Ground  | 25  
| RESET   | 28

You can change the interrupt pin (GPIO24) in the class init.

Remember to choose correct frequency for your hardware (315, 433, 868 or 915 MHz).

# Prerequisites

RPi.GPIO and spidev

If you are using newer firmware you'll need to get a newer spidev, the old one is no longer working:

```bash
git clone https://github.com/Gadgetoid/py-spidev
cd py-spidev
sudo make install
```

