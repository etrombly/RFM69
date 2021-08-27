# Main repo

* https://github.com/etrombly/RFM69

# Description

This is a port of the RFM69 library for Arduino from https://github.com/LowPowerLab/RFM69 to Python for the Raspberry Pi and Orange Pi.

# Hardware setup

Attach the RFM69 as follows:

| RFM pin | Pi pin  
| ------- |-------
| 3V3     | 17  
| DIO0    | 18 (GPIO24)  
| MOSI    | 19  
| MISO    | 21  
| CLK     | 23  
| NSS     | 24 (CE0)  
| Ground  | 25  
| RESET   | 22 (GPIO25)  

You can change the interrupt and reset pins in the class init.

Remember to choose a correct frequency for your hardware (315, 433, 868 or 915 MHz).

# Prerequisites

The following Python packages must be installed for the Raspberry Pi (using pip3):

* RPi.GPIO
* spidev

For Orange Pi, these packages are required instead:

* OrangePi.GPIO
* spidev

Be sure to enable the SPI interface on your GPIO header using either the command `raspi-config` or `armbian-config`.
Orange Pi systems running Armbian also require this extra step to enable the SPI bus:
Edit the file /boot/armbianEnv.txt and insert the line

    param_spidev_spi_bus=1

after the existing line similar to

    overlays=spi-spidev

Then reboot the system in any case.

You can use this SPI test program to verify that SPI is set up properly: https://github.com/rm-hull/spidev-test

The code in this repository is configured for the Raspberry Pi.
To use this on an Orange Pi, follow the instructions in the file RFM69.py to change the imported package name, SPI bus (1 instead of 0) and tell the GPIO package the board type you have (preconfigured to Orange Pi Zero).

# Simple usage

The example.py script shows some method calls. Its function isn't necessarily meaningful.

The scripts radio1.py and radio2.py are set up to talk to each other in a ping pong style.
They can be used to test the communication between two nodes, for specific antenna setup, power level and modulation parameters.
Both scripts are almost identical, just the definitions at the top differ to give both their identity.
Run one on one device and the other on another device, both connected to an RFM69 module for the same frequency range.
The scripts will print each received message with its RSSI to indicate how strong the received signal was.

Before running any of these scripts, be sure to review them and make necessary changes, like the RF frequency or H-model type.

Class initialisation:

    radio = RFM69.RFM69(RF69_433MHZ, node_id, network_id, is_rfm_69HW)

This creates a new instance of the class that you can use to call methods on.

    radio.setHighPower(True)

This must be called on any RFM69 device with an "H" in its model (for high power), otherwise it won't send anything.
It's the same condition as the `is_rfm_69HW` parameter above.

    radio.encrypt("1234567890123xyz")

This will set up the embedded AES encryption.
The key must be exactly 16 ASCII characters and of course it must be the same for each node that should talk to each other because AES is a symmetric cipher.

    radio.setFrequency(433500000)

This must be called in any case to set the actual frequency to transmit and receive on.
The number is in Hz but the resolution is only about 61 Hz.
This example sets the frequency to 433.5 MHz.

    radio.send(2, "Hello world")
    radio.sendWithRetry(2, "Hello world", 3, 100)

This call sends a message "Hello world" to the node 2.
The second one also waits for an acknowledgement within 100 milliseconds and, if none was received, resends the message for a total of up to 3 times.

Additional methods can be called to start receiving messages, handle ACKs, set the modulation parameters, or shut down the device.
You should always call the shutdown method so that the radio module isn't kept in an active state when you're no longer using it.
The sample scripts show a method how to do this in Python with try/except.

Setting the transmit power level is currently incomplete and needs some rework.
It can only access some of the available levels on H-models, see the [original code issue](https://github.com/LowPowerLab/RFM69/issues/61).
(This Python port has a slightly different implementation, but still incomplete.)
It is currently possible with this call:

    radio.setPowerLevel(0)

Set the number to a value between 0 and 31.
Due to the limitations, probably only the values 0 and 31 are useful now, for minimum and maximum output power, respectively.
