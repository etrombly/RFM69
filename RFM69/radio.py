import sys, time, logging
from datetime import datetime
import logging
import spidev
import RPi.GPIO as GPIO
from .registers import *
from .packet import Packet
from .config import get_config

class Radio(object):

    def __init__(self, freqBand, nodeID, networkID=100, **kwargs):
        """RFM69 Radio interface for the Raspberry PI.

        An RFM69 module is expected to be connected to the SPI interface of the Raspberry Pi. The class is as a context manager so you can instantiate it using the 'with' keyword.

        Args: 
            freqBand: Frequency band of radio - 315MHz, 868Mhz, 433MHz or 915MHz.
            nodeID (int): The node ID of this device.
            networkID (int): The network ID

        Keyword Args:
            isHighPower (bool): Is this a high power radio model
            interruptPin (int): Pin number of interrupt pin. This is a pin index not a GPIO number.
            resetPin (int): Pin number of reset pin. This is a pin index not a GPIO number.
            spiBus (int): SPI bus number.
            spiDevice (int): SPI device number.
            promiscuousMode (bool): Listen to all messages not just those addressed to this node ID.
            encryptionKey (str): 16 character encryption key.
            verbose (bool): Verbose mode - Activates logging to console.

        """
        self.logger = None
        if kwargs.get('verbose', False):
            self.logger = self._init_log()

        self.address = nodeID
   
        self.isRFM69HW = kwargs.get('isHighPower', False)
        self.intPin = kwargs.get('interruptPin', 18)
        self.rstPin = kwargs.get('resetPin', 29)
        self.spiBus = kwargs.get('spiBus', 0)
        self.spiDevice = kwargs.get('spiDevice', 0)
        self.promiscuousMode = kwargs.get('promiscuousMode', 0)

        self.intLock = False
        self.mode = ""
        self.DATASENT = False
        self.SENDERID = 0
        self.TARGETID = 0
        self.PAYLOADLEN = 0
        self.ACK_REQUESTED = 0
        self.ACK_RECEIVED = 0
        self.RSSI = 0
        self.DATA = []

        self._init_spi()
        self._init_gpio()
        self._reset_radio()
        self._set_config(get_config(freqBand, networkID))
        self._encrypt(kwargs.get('encryptionKey', 0))
        self._setHighPower(self.isRFM69HW)

        # Wait for ModeReady
        while (self._readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_MODEREADY) == 0x00:
            pass

        self._init_interrupt()

    def _init_gpio(self):
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.intPin, GPIO.IN)
        GPIO.setup(self.rstPin, GPIO.OUT)

    def _init_spi(self):
        #initialize SPI
        self.spi = spidev.SpiDev()
        self.spi.open(self.spiBus, self.spiDevice)
        self.spi.max_speed_hz = 4000000

    def _reset_radio(self):
        # Hard reset the RFM module
        GPIO.output(self.rstPin, GPIO.HIGH)
        time.sleep(0.3)
        GPIO.output(self.rstPin, GPIO.LOW)
        time.sleep(0.3)
        #verify chip is syncing?
        start = time.time()
        while self._readReg(REG_SYNCVALUE1) != 0xAA:
            self._writeReg(REG_SYNCVALUE1, 0xAA)
            if time.time() - start > 15000:
                raise Exception('Failed to sync with chip')
        start = time.time()
        while self._readReg(REG_SYNCVALUE1) != 0x55:
            self._writeReg(REG_SYNCVALUE1, 0x55)
            if time.time() - start > 15000:
                raise Exception('Failed to sync with chip')

    def _set_config(self, config):
        for value in config.values():
            self._writeReg(value[0], value[1])

    def _init_interrupt(self):
        GPIO.remove_event_detect(self.intPin)
        GPIO.add_event_detect(self.intPin, GPIO.RISING, callback=self._interruptHandler)


    # 
    # End of Init
    # 

    def __enter__(self):
        """When the context begins"""
        self.read_temperature()
        self.calibrate_radio()
        return self

    def __exit__(self, *args):
        """When context exits (including when the script is terminated)"""
        self._shutdown()     
       
    def set_frequency(self, FRF):
        """Set the radio frequency"""
        self._writeReg(REG_FRFMSB, FRF >> 16)
        self._writeReg(REG_FRFMID, FRF >> 8)
        self._writeReg(REG_FRFLSB, FRF)

    def sleep(self):
        """Put the radio into sleep mode"""
        self._setMode(RF69_MODE_SLEEP)

    def set_network(self, network_id):
        """Set the network ID (sync)
        
        Args:
            network_id (int): Value between 1 and 254.

        """
        assert type(network_id) == int
        assert network_id > 0 and network_id < 255
        self._writeReg(REG_SYNCVALUE2, network_id)

    def set_power_level(self, percent):
        """Set the transmit power level
        
        Args:
            percent (int): Value between 0 and 100.

        """
        assert type(percent) == int
        self.powerLevel = int(round(powerLevel = 31 * percent))
        self._writeReg(REG_PALEVEL, (self._readReg(REG_PALEVEL) & 0xE0) | self.powerLevel)


    def send(self, toAddress, buff = "", requestACK = False):
        self._writeReg(REG_PACKETCONFIG2, (self._readReg(REG_PACKETCONFIG2) & 0xFB) | RF_PACKET2_RXRESTART)
        now = time.time()
        while (not self._canSend()) and time.time() - now < RF69_CSMA_LIMIT_S:
            self.has_received_packet()
        self._sendFrame(toAddress, buff, requestACK, False)

    def sendWithRetry(self, toAddress, buff = "", retries = 3, retryWaitTime = 10):
        for i in range(0, retries):
            self.send(toAddress, buff, True)
            sentTime = time.time()
            while (time.time() - sentTime) * 1000 < retryWaitTime:
                if self._ACKReceived(toAddress):
                    return True
        return False

    def read_temperature(self, calFactor=0):
        """Read the temperature of the radios CMOS chip.
        
        Args:
            calFactor: Additional correction to corrects the slope, rising temp = rising val

        Returns:
            int: Temperature in centigrade
        """
        self._setMode(RF69_MODE_STANDBY)
        self._writeReg(REG_TEMP1, RF_TEMP1_MEAS_START)
        while self._readReg(REG_TEMP1) & RF_TEMP1_MEAS_RUNNING:
            pass
        # COURSE_TEMP_COEF puts reading in the ballpark, user can add additional correction
        #'complement'corrects the slope, rising temp = rising val
        return (int(~self._readReg(REG_TEMP2)) * -1) + COURSE_TEMP_COEF + calFactor


    def calibrate_radio(self):
        """Calibrate the internal RC oscillator for use in wide temperature variations.
        
        See RFM69 datasheet section [4.3.5. RC Timer Accuracy] for more information.
        """
        self._writeReg(REG_OSC1, RF_OSC1_RCCAL_START)
        while self._readReg(REG_OSC1) & RF_OSC1_RCCAL_DONE == 0x00:
            pass

    def read_registers(self):
        """Get all register values.

        Returns:
            list: Register values
        """
        results = []
        for address in range(1, 0x50):
            results.append([str(hex(address)), str(bin(self._readReg(address)))])
        return results

    def begin_receive(self):
        """Begin listening for packets"""
        while self.intLock:
            time.sleep(.1)
        self.SENDERID = 0
        self.TARGETID = 0
        self.PAYLOADLEN = 0
        self.ACK_REQUESTED = 0
        self.ACK_RECEIVED = 0
        self.RSSI = 0
        if (self._readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_PAYLOADREADY):
            # avoid RX deadlocks
            self._writeReg(REG_PACKETCONFIG2, (self._readReg(REG_PACKETCONFIG2) & 0xFB) | RF_PACKET2_RXRESTART)
        #set DIO0 to "PAYLOADREADY" in receive mode
        self._writeReg(REG_DIOMAPPING1, RF_DIOMAPPING1_DIO0_01)
        self._setMode(RF69_MODE_RX)

    def has_received_packet(self):
        """Check if packet received

        Returns:
            bool: True if packet has been received

        """
        if (self.mode == RF69_MODE_RX or self.mode == RF69_MODE_STANDBY) and self.PAYLOADLEN > 0:
            self._setMode(RF69_MODE_STANDBY)
            return True
        if self._readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_TIMEOUT:
            # https://github.com/russss/rfm69-python/blob/master/rfm69/rfm69.py#L112
            # Russss figured out that if you leave alone long enough it times out
            # tell it to stop being silly and listen for more packets
            self._writeReg(REG_PACKETCONFIG2, (self._readReg(REG_PACKETCONFIG2) & 0xFB) | RF_PACKET2_RXRESTART)
        elif self.mode == RF69_MODE_RX:
            # already in RX no payload yet
            return False
        self.begin_receive()
        return False

    def get_packet(self, auto_acknowledge=True):
        """Get newly received packet.

        Args:
            auto_acknowledge (bool): Send an acknowledgement if requested

        Returns:
            RFM69Radio.Packet: Packet objects containing received data and associated meta data.
        """
         # Create packet
        packet = Packet(int(self.TARGETID), int(self.SENDERID), int(self.RSSI), list(self.DATA))
        
        # Send acknowledgement if needed
        if auto_acknowledge:
            if self.ack_requested():
                self.send_ack(self.SENDERID)
                self._debug('Acknowledgement send')
            else:
                self._debug('No acknowledgement request')
        
        return packet

    def ack_requested(self):
        return self.ACK_REQUESTED and self.TARGETID != RF69_BROADCAST_ADDR

    def send_ack(self, toAddress = 0, buff = ""):
        toAddress = toAddress if toAddress > 0 else self.SENDERID
        while not self._canSend():
            self.has_received_packet()
        self._sendFrame(toAddress, buff, False, True)


    # 
    # Internal functions
    # 

    def _setMode(self, newMode):
        if newMode == self.mode:
            return
        if newMode == RF69_MODE_TX:
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_TRANSMITTER)
            if self.isRFM69HW:
                self._setHighPowerRegs(True)
        elif newMode == RF69_MODE_RX:
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_RECEIVER)
            if self.isRFM69HW:
                self._setHighPowerRegs(False)
        elif newMode == RF69_MODE_SYNTH:
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_SYNTHESIZER)
        elif newMode == RF69_MODE_STANDBY:
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_STANDBY)
        elif newMode == RF69_MODE_SLEEP:
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_SLEEP)
        else:
            return
        # we are using packet mode, so this check is not really needed
        # but waiting for mode ready is necessary when going from sleep because the FIFO may not be immediately available from previous mode
        while self.mode == RF69_MODE_SLEEP and self._readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_MODEREADY == 0x00:
            pass
        self.mode = newMode;

    def _setAddress(self, addr):
        self.address = addr
        self._writeReg(REG_NODEADRS, self.address)

    def _canSend(self):
        if self.mode == RF69_MODE_STANDBY:
            self.begin_receive()
            return True
        #if signal stronger than -100dBm is detected assume channel activity
        elif self.mode == RF69_MODE_RX and self.PAYLOADLEN == 0 and self._readRSSI() < CSMA_LIMIT:
            self._setMode(RF69_MODE_STANDBY)
            return True
        return False

    def _ACKReceived(self, fromNodeID):
        if self.has_received_packet():
            return (self.SENDERID == fromNodeID or fromNodeID == RF69_BROADCAST_ADDR) and self.ACK_RECEIVED
        return False

    

    def _sendFrame(self, toAddress, buff, requestACK, sendACK):
        #turn off receiver to prevent reception while filling fifo
        self._setMode(RF69_MODE_STANDBY)
        #wait for modeReady
        while (self._readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_MODEREADY) == 0x00:
            pass
        # DIO0 is "Packet Sent"
        self._writeReg(REG_DIOMAPPING1, RF_DIOMAPPING1_DIO0_00)

        if (len(buff) > RF69_MAX_DATA_LEN):
            buff = buff[0:RF69_MAX_DATA_LEN]

        ack = 0
        if sendACK:
            ack = 0x80
        elif requestACK:
            ack = 0x40
        if isinstance(buff, str):
            self.spi.xfer2([REG_FIFO | 0x80, len(buff) + 3, toAddress, self.address, ack] + [int(ord(i)) for i in list(buff)])
        else:
            self.spi.xfer2([REG_FIFO | 0x80, len(buff) + 3, toAddress, self.address, ack] + buff)

        startTime = time.time()
        self.DATASENT = False
        self._setMode(RF69_MODE_TX)
        while not self.DATASENT:
            if time.time() - startTime > 1.0:
                break
        self._setMode(RF69_MODE_RX)

    def _interruptHandler(self, pin):
        self._debug("-- Interrupt -- ")
        self.intLock = True
        self.DATASENT = True

        if self.mode == RF69_MODE_RX and self._readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_PAYLOADREADY:
            self._setMode(RF69_MODE_STANDBY)
        
            self.PAYLOADLEN, self.TARGETID, self.SENDERID, CTLbyte = self.spi.xfer2([REG_FIFO & 0x7f,0,0,0,0])[1:]
        
            if self.PAYLOADLEN > 66:
                self.PAYLOADLEN = 66

            if not (self.promiscuousMode or self.TARGETID == self.address or self.TARGETID == RF69_BROADCAST_ADDR):
                self._debug("IGNORE")
                self.PAYLOADLEN = 0
                self.intLock = False
                return

            data_length = self.PAYLOADLEN - 3
            self.ACK_RECEIVED = CTLbyte & 0x80
            self.ACK_REQUESTED = CTLbyte & 0x40
            self.DATA = self.spi.xfer2([REG_FIFO & 0x7f] + [0 for i in range(0, data_length)])[1:]
            self.RSSI = self._readRSSI()

        self.intLock = False

    

    def _readRSSI(self, forceTrigger = False):
        rssi = 0
        if forceTrigger:
            self._writeReg(REG_RSSICONFIG, RF_RSSI_START)
            while self._readReg(REG_RSSICONFIG) & RF_RSSI_DONE == 0x00:
                pass
        rssi = self._readReg(REG_RSSIVALUE) * -1
        rssi = rssi >> 1
        return rssi

    def _encrypt(self, key):
        self._setMode(RF69_MODE_STANDBY)
        if key != 0 and len(key) == 16:
            self.spi.xfer([REG_AESKEY1 | 0x80] + [int(ord(i)) for i in list(key)])
            self._writeReg(REG_PACKETCONFIG2,(self._readReg(REG_PACKETCONFIG2) & 0xFE) | RF_PACKET2_AES_ON)
        else:
            self._writeReg(REG_PACKETCONFIG2,(self._readReg(REG_PACKETCONFIG2) & 0xFE) | RF_PACKET2_AES_OFF)

    def _readReg(self, addr):
        return self.spi.xfer([addr & 0x7F, 0])[1]

    def _writeReg(self, addr, value):
        self.spi.xfer([addr | 0x80, value])

    def _promiscuous(self, onOff):
        self.promiscuousMode = onOff

    def _setHighPower(self, onOff):
        if onOff:
            self._writeReg(REG_OCP, RF_OCP_OFF)
            #enable P1 & P2 amplifier stages
            self._writeReg(REG_PALEVEL, (self._readReg(REG_PALEVEL) & 0x1F) | RF_PALEVEL_PA1_ON | RF_PALEVEL_PA2_ON)
        else:
            self._writeReg(REG_OCP, RF_OCP_ON)
            #enable P0 only
            self._writeReg(REG_PALEVEL, RF_PALEVEL_PA0_ON | RF_PALEVEL_PA1_OFF | RF_PALEVEL_PA2_OFF | powerLevel)

    def _setHighPowerRegs(self, onOff):
        if onOff:
            self._writeReg(REG_TESTPA1, 0x5D)
            self._writeReg(REG_TESTPA2, 0x7C)
        else:
            self._writeReg(REG_TESTPA1, 0x55)
            self._writeReg(REG_TESTPA2, 0x70)

    def _shutdown(self):
        """Shutdown the radio.

        Puts the radio to sleep and cleans up the GPIO connections.
        """
        self._setHighPower(False)
        self.sleep()
        GPIO.cleanup()

    def __str__(self):
        return "Radio RFM69"

    def __repr__(self):
        return "Radio()"

    def _init_log(self):
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger(__name__)
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
        return logger

    def _debug(self, *args):
        if self.logger is not None:
             self.logger.debug(*args)
      
    def _error(self, *args):
        if self.logger is not None:
             self.logger.error(*args)
 