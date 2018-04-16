# RFM69 Radio interface for the Raspberry Pi
This package provides a Python wrapper of the [LowPowerLabs RFM69 library](https://github.com/LowPowerLab/RFM69) and is largely based on the work of [Eric Trombly](https://github.com/etrombly/RFM69) who ported the library from C.

The package expects to be installed on a Raspberry Pi and depends on the [RPI.GPIO](https://pypi.org/project/RPi.GPIO/) and [spidev](https://pypi.org/project/spidev/) libraries. In addition you need to have an RFM69 radio module directly attached to the Pi. 

For details on how to connect such a module and further information regarding the API check out the [documentation](http://rfm69radio.readthedocs.io/).