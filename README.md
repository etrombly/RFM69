# Warning

-- THIS VERSION IS CURRENTLY BEING REFACTORED AND YOU SHOULD NOT USE WHILE THIS MESSAGE IS HERE --

# Main repo
This Repo is adapted form https://github.com/etrombly/RFM69. The examples have been updated and the library is now Python 3.

# Description
This is a port of the RFM69 library for Arduino from https://github.com/LowPowerLab/RFM69 to python for raspberry pi.

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
| RESET   | 29

You can change the interrupt pin (GPIO24) in the class init.
Remember to choose correct frequency for your hardware (315, 433, 868 or 915 MHz).

# Dependencies
* ```pip install RPi.GPIO```
* ```pip install spidev```
