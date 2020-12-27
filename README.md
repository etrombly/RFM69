# Main repo

* https://github.com/etrombly/RFM69

# Description

This is a port of the RFM69 library for arduino from https://github.com/LowPowerLab/RFM69 to python for raspberry pi.

# Hardware setup

Attach the RFM69 as follows:

| RFM pin | #  | Pi pin header description| Pi pin header description | #  | RFM pin
| ------- |----|-------------- |------------- |----| -------
| 3v3     | 17 | 3.3V Power    | (GPIO24)     | 18 | DIO0
| MOSI    | 19 | MOSI (GPIO10) | GND          | 20 | Ground
| MISO    | 21 | MISO (GPIO9)  | (GPIO25)     | 22 |
| CLK     | 23 | SCLK (GPIO11) | CE0 (GPIO8)  | 24 | NSS (CS)
| Ground  | 25 | GND           | CE1 (GPIO7)  | 26 |
|         | 27 | ID_SD (N/A)   | ID_SC (N/A)  | 28 |
| RESET   | 29 | (GPIO5)       | GND          | 30 | Ground

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

And don't forget to enable the SPI interface:

```bash
sudo raspi-config
```

Select "Interface Options", -> "SPI", choose "Yes" to enable it and reboot.

```bash
sudo reboot
```
