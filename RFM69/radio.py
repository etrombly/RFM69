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
            auto_acknowledge (bool): Automatically send acknowledgements
            isHighPower (bool): Is this a high power radio model
            power (int): Power level - a percentage in range 10 to 100.
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

        self.auto_acknowledge = kwargs.get('autoAcknowledge', True)
        self.isRFM69HW = kwargs.get('isHighPower', True)
        self.intPin = kwargs.get('interruptPin', 18)
        self.rstPin = kwargs.get('resetPin', 29)
        self.spiBus = kwargs.get('spiBus', 0)
        self.spiDevice = kwargs.get('spiDevice', 0)
        self.promiscuousMode = kwargs.get('promiscuousMode', 0)
        
        self.intLock = False
        self.sendLock = False
        self.mode = ""
        self.mode_name = ""
        

        self.sendSleepTime = 0.05

        # 
        self.packets = []
        self.acks = {}
        #
        #         
        self._init_spi()
        self._init_gpio()
        self._reset_radio()
        self._set_config(get_config(freqBand, networkID))
        self._encrypt(kwargs.get('encryptionKey', 0))
        self._setHighPower(self.isRFM69HW)
        self.set_power_level(kwargs.get('power', 70))

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
        self.begin_receive()
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
        self.powerLevel = int( round(31 * (percent / 100)))
        self._writeReg(REG_PALEVEL, (self._readReg(REG_PALEVEL) & 0xE0) | self.powerLevel)


    def _send(self, toAddress, buff = "", requestACK = False):
        self._writeReg(REG_PACKETCONFIG2, (self._readReg(REG_PACKETCONFIG2) & 0xFB) | RF_PACKET2_RXRESTART)
        now = time.time()
        while (not self._canSend()) and time.time() - now < RF69_CSMA_LIMIT_S:
            self.has_received_packet()
        self._sendFrame(toAddress, buff, requestACK, False)


    def send(self, toAddress, buff = "", **kwargs):
        """Send a message
        
        Args:
            toAddress (int): Recipient node's ID
            buff (str): Message buffer to send 
        
        Keyword Args:
            attempts (int): Number of attempts
            waitTime (int): Milliseconds to wait for acknowledgement

        Returns:
            bool: If acknowledgement received
        
        """

        attempts = kwargs.get('attempts', 3)
        wait_time = kwargs.get('waitTime', 50)

        for _ in range(0, attempts):

            self._send(toAddress, buff, attempts>0 )

            sentTime = time.time()
            while (time.time() - sentTime) * 1000 < wait_time:
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
        return len(self.packets) > 0

    def get_packets(self):
        """Get newly received packets.

        Returns:
            RFM69.Packet: Packet objects containing received data and associated meta data.
        """
        # Create packet
        packets = list(self.packets)
        self.packets = []
        return packets

   
    def send_ack(self, toAddress, buff = ""):
        """Send an acknowledgemet packet

        Args: 
            toAddress (int): Recipient node's ID

        """
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
            self.mode_name = "TX"
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_TRANSMITTER)
            if self.isRFM69HW:
                self._setHighPowerRegs(True)
        elif newMode == RF69_MODE_RX:
            self.mode_name = "RX"
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_RECEIVER)
            if self.isRFM69HW:
                self._setHighPowerRegs(False)
        elif newMode == RF69_MODE_SYNTH:
            self.mode_name = "Synth"
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_SYNTHESIZER)
        elif newMode == RF69_MODE_STANDBY:
            self.mode_name = "Standby"
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_STANDBY)
        elif newMode == RF69_MODE_SLEEP:
            self.mode_name = "Sleep"
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_SLEEP)
        else:
            self.mode_name = "Unknown"
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
        #if signal stronger than -100dBm is detected assume channel activity - removed self.PAYLOADLEN == 0 and
        elif self.mode == RF69_MODE_RX and self._readRSSI() < CSMA_LIMIT:
            self._setMode(RF69_MODE_STANDBY)
            return True
        return False

    def _ACKReceived(self, fromNodeID):
        if fromNodeID in self.acks:
            self.acks.pop(fromNodeID, None)
            return True
        return False
        # if self.has_received_packet():
        #     return (self.SENDERID == fromNodeID or fromNodeID == RF69_BROADCAST_ADDR) and self.ACK_RECEIVED
        # return False

    

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

        self.sendLock = True
        self._setMode(RF69_MODE_TX)
        slept = 0
        while self.sendLock:
            time.sleep(self.sendSleepTime)
            slept += self.sendSleepTime
            if slept > 1.0:
                break
        self._setMode(RF69_MODE_RX)

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
 
    # 
    # Radio interrupt handler
    # 

    def _interruptHandler(self, pin):
        self.intLock = True
        self.sendLock = False

        if self.mode == RF69_MODE_RX and self._readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_PAYLOADREADY:
            self._setMode(RF69_MODE_STANDBY)
        
            payload_length, target_id, sender_id, CTLbyte = self.spi.xfer2([REG_FIFO & 0x7f,0,0,0,0])[1:]
        
            if payload_length > 66:
                payload_length = 66

            if not (self.promiscuousMode or target_id == self.address or target_id == RF69_BROADCAST_ADDR):
                self._debug("IGNORE")
                self.intLock = False
                return

            data_length = payload_length - 3
            ack_received  = bool(CTLbyte & 0x80)
            ack_requested = bool(CTLbyte & 0x40)
            data = self.spi.xfer2([REG_FIFO & 0x7f] + [0 for i in range(0, data_length)])[1:]
            rssi = self._readRSSI()

            if ack_received:
                self._debug("Incoming ack")
                self._debug(sender_id)
                # Record acknowledgement
                self.acks.setdefault(sender_id, 1)
         
            elif ack_requested:
                self._debug("replying to ack request")
            else:
                self._debug("Other ??")

            # When message received
            if not ack_received:
                self._debug("Incoming data packet")
                self.packets.append(
                    Packet(int(target_id), int(sender_id), int(rssi), list(data))
                )

            # Send acknowledgement if needed
            if ack_requested and self.auto_acknowledge:
                self.intLock = False
                self.send_ack(sender_id)
             
        self.intLock = False
        self.begin_receive()