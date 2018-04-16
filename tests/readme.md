# Testing
Because the library is specifically designed to be tested on a RaspberryPi we also need to test it on one. To help with this process there is a Fabric script. In addition we need a node with which to interact.


## Setup test node
Use the Arduino IDE to upload the script: ```test-node/test-node.ino``` to an Adafruit Feather with RFM69.


## Setup test environment on remote RaspberryPi
Run the following commands inside a Python 3 environment.

```
pip install -r requirements_local.txt
fab init - H raspberrypi.local 
```

## Run tests on remote environment
From inside your testing environment run:

```
fab test - H raspberrypi.local 
```
