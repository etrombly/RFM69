import sys, time
from datetime import datetime
import logging
import spidev
import RPi.GPIO as GPIO
from .registers import *
from .packet import Packet

class Radio(object):

    def __init__(self, freqBand, nodeID=1, networkID=100, **kwargs):
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

        self.freqBand = freqBand
        self.address = nodeID
        self.networkID = networkID
        self.isRFM69HW = kwargs.get('isHighPower', False)
        self.intPin = kwargs.get('interruptPin', 18)
        self.rstPin = kwargs.get('resetPin', 29)
        self.spiBus = kwargs.get('spiBus', 0)
        self.spiDevice = kwargs.get('spiDevice', 0)
        self.intLock = False
        self.mode = ""
        self._promiscuousMode = kwargs.get('promiscuousMode', False)
        self._DATASENT = False
        self._DATALEN = 0
        self._SENDERID = 0
        self._TARGETID = 0
        self._PAYLOADLEN = 0
        self._ACK_REQUESTED = 0
        self._ACK_RECEIVED = 0
        self._RSSI = 0
        self._DATA = []
        self.packets = []

        self._debug('Init config complete')

        GPIO.setmode(GPIO.BOARD)
        # GPIO.setwarnings(False)
        GPIO.setup(self.intPin, GPIO.IN)
        GPIO.setup(self.rstPin, GPIO.OUT)
        self._debug('GPIOs configured')

        frfMSB = {RF69_315MHZ: RF_FRFMSB_315, RF69_433MHZ: RF_FRFMSB_433,
                  RF69_868MHZ: RF_FRFMSB_868, RF69_915MHZ: RF_FRFMSB_915}
        frfMID = {RF69_315MHZ: RF_FRFMID_315, RF69_433MHZ: RF_FRFMID_433,
                  RF69_868MHZ: RF_FRFMID_868, RF69_915MHZ: RF_FRFMID_915}
        frfLSB = {RF69_315MHZ: RF_FRFLSB_315, RF69_433MHZ: RF_FRFLSB_433,
                  RF69_868MHZ: RF_FRFLSB_868, RF69_915MHZ: RF_FRFLSB_915}

        self.CONFIG = {
          0x01: [REG_OPMODE, RF_OPMODE_SEQUENCER_ON | RF_OPMODE_LISTEN_OFF | RF_OPMODE_STANDBY],
          #no shaping
          0x02: [REG_DATAMODUL, RF_DATAMODUL_DATAMODE_PACKET | RF_DATAMODUL_MODULATIONTYPE_FSK | RF_DATAMODUL_MODULATIONSHAPING_00],
          #default:4.8 KBPS
          0x03: [REG_BITRATEMSB, RF_BITRATEMSB_55555],
          0x04: [REG_BITRATELSB, RF_BITRATELSB_55555],
          #default:5khz, (FDEV + BitRate/2 <= 500Khz)
          0x05: [REG_FDEVMSB, RF_FDEVMSB_50000],
          0x06: [REG_FDEVLSB, RF_FDEVLSB_50000],

          0x07: [REG_FRFMSB, frfMSB[freqBand]],
          0x08: [REG_FRFMID, frfMID[freqBand]],
          0x09: [REG_FRFLSB, frfLSB[freqBand]],

          # looks like PA1 and PA2 are not implemented on RFM69W, hence the max output power is 13dBm
          # +17dBm and +20dBm are possible on RFM69HW
          # +13dBm formula: Pout=-18+OutputPower (with PA0 or PA1**)
          # +17dBm formula: Pout=-14+OutputPower (with PA1 and PA2)**
          # +20dBm formula: Pout=-11+OutputPower (with PA1 and PA2)** and high power PA settings (section 3.3.7 in datasheet)
          #0x11: [REG_PALEVEL, RF_PALEVEL_PA0_ON | RF_PALEVEL_PA1_OFF | RF_PALEVEL_PA2_OFF | RF_PALEVEL_OUTPUTPOWER_11111],
          #over current protection (default is 95mA)
          #0x13: [REG_OCP, RF_OCP_ON | RF_OCP_TRIM_95],

          # RXBW defaults are { REG_RXBW, RF_RXBW_DCCFREQ_010 | RF_RXBW_MANT_24 | RF_RXBW_EXP_5} (RxBw: 10.4khz)
          #//(BitRate < 2 * RxBw)
          0x19: [REG_RXBW, RF_RXBW_DCCFREQ_010 | RF_RXBW_MANT_16 | RF_RXBW_EXP_2],
          #for BR-19200: //* 0x19 */ { REG_RXBW, RF_RXBW_DCCFREQ_010 | RF_RXBW_MANT_24 | RF_RXBW_EXP_3 },
          #DIO0 is the only IRQ we're using
          0x25: [REG_DIOMAPPING1, RF_DIOMAPPING1_DIO0_01],
          #must be set to dBm = (-Sensitivity / 2) - default is 0xE4=228 so -114dBm
          0x29: [REG_RSSITHRESH, 220],
          #/* 0x2d */ { REG_PREAMBLELSB, RF_PREAMBLESIZE_LSB_VALUE } // default 3 preamble bytes 0xAAAAAA
          0x2e: [REG_SYNCCONFIG, RF_SYNC_ON | RF_SYNC_FIFOFILL_AUTO | RF_SYNC_SIZE_2 | RF_SYNC_TOL_0],
          #attempt to make this compatible with sync1 byte of RFM12B lib
          0x2f: [REG_SYNCVALUE1, 0x2D],
          #NETWORK ID
          0x30: [REG_SYNCVALUE2, networkID],
          0x37: [REG_PACKETCONFIG1, RF_PACKET1_FORMAT_VARIABLE | RF_PACKET1_DCFREE_OFF |
                RF_PACKET1_CRC_ON | RF_PACKET1_CRCAUTOCLEAR_ON | RF_PACKET1_ADRSFILTERING_OFF],
          #in variable length mode: the max frame size, not used in TX
          0x38: [REG_PAYLOADLENGTH, 66],
          #* 0x39 */ { REG_NODEADRS, nodeID }, //turned off because we're not using address filtering
          #TX on FIFO not empty
          0x3C: [REG_FIFOTHRESH, RF_FIFOTHRESH_TXSTART_FIFONOTEMPTY | RF_FIFOTHRESH_VALUE],
          #RXRESTARTDELAY must match transmitter PA ramp-down time (bitrate dependent)
          0x3d: [REG_PACKETCONFIG2, RF_PACKET2_RXRESTARTDELAY_2BITS | RF_PACKET2_AUTORXRESTART_ON | RF_PACKET2_AES_OFF],
          #for BR-19200: //* 0x3d */ { REG_PACKETCONFIG2, RF_PACKET2_RXRESTARTDELAY_NONE | RF_PACKET2_AUTORXRESTART_ON | RF_PACKET2_AES_OFF }, //RXRESTARTDELAY must match transmitter PA ramp-down time (bitrate dependent)
          #* 0x6F */ { REG_TESTDAGC, RF_DAGC_CONTINUOUS }, // run DAGC continuously in RX mode
          # run DAGC continuously in RX mode, recommended default for AfcLowBetaOn=0
          0x6F: [REG_TESTDAGC, RF_DAGC_IMPROVED_LOWBETA0],
          0x00: [255, 0]
        }

        #initialize SPI
        self.spi = spidev.SpiDev()
        self.spi.open(self.spiBus, self.spiDevice)
        self.spi.max_speed_hz = 4000000

        # Hard reset the RFM module
        GPIO.output(self.rstPin, GPIO.HIGH)
        time.sleep(0.1)
        GPIO.output(self.rstPin, GPIO.LOW)
        time.sleep(0.1)

        #verify chip is syncing?
        while self._readReg(REG_SYNCVALUE1) != 0xAA:
            self._writeReg(REG_SYNCVALUE1, 0xAA)

        while self._readReg(REG_SYNCVALUE1) != 0x55:
            self._writeReg(REG_SYNCVALUE1, 0x55)

        #write config
        for value in self.CONFIG.values():
            self._writeReg(value[0], value[1])

        self._setEncryptionKey(kwargs.get('encryptionKey', 0))

        self._setHighPower(self.isRFM69HW)
        # Wait for ModeReady
        while (self._readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_MODEREADY) == 0x00:
            pass

        GPIO.remove_event_detect(self.intPin)
        GPIO.add_event_detect(self.intPin, GPIO.RISING, callback=self._interruptHandler)
        

    def __enter__(self):
        """When the context begins"""
        self.readTemperature()
        self.calibrate()
        self._receiveBegin()
        return self

    def __exit__(self, *args):
        """When context exits (including when the script is terminated)"""
        self.shutdown()

  

    # def send(self, toAddress, buff="", attempts=1, requestACK=True, waitTime=500):
    #     """Send a packet.
        
    #     To increase the chance of getting a packet across, this function handles all the ACK requesting/retrying for you. 

    #     Args:
    #         toAddress (int): Node ID of recipient
    #         buff (string): Data buffer to send (max 60 bytes)
    #         attempts (int): Number of attempts to make
    #         requestACK (bool): Request an acknowledgement. If attempts > 1 then automatically set to True.
    #         waitTime (int): Time to wait for acknowledgement in ms

    #     """
    #     assert attempts > 0
    #     if attempts > 1:
    #         requestACK = True

    #     # Try to send
    #     for i in range(0, attempts):
    #         self._debug("Attempt No. {}".format(i))
    #         self._writeReg(REG_PACKETCONFIG2, (self._readReg(REG_PACKETCONFIG2) & 0xFB) | RF_PACKET2_RXRESTART)
            
    #         # Wait for an opportunity to send
    #         now = time.time()
    #         while (not self._canSend()) and time.time() - now < RF69_CSMA_LIMIT_S:
    #             self._receiveDone()

    #         self._debug("Sent")

    #         # Send the frame
    #         self._sendFrame(toAddress, buff, requestACK, False)

    #         # Wait for an acknowledgement
    #         if requestACK:
    #             self._debug("Waiting for ACK")

    #             sentTime = time.time()
    #             while (time.time() - sentTime) * 1000 < waitTime:
    #                 if self._ACKReceived(toAddress):
    #                     self._debug("ACK received")
    #                     return True
    #                 time.sleep(.1)
                
    #         else:
    #             return True

    #     self._debug("No ACK received")
    #     return False

    def send(self, toAddress, buff = "", requestACK = False):
        self._writeReg(REG_PACKETCONFIG2, (self._readReg(REG_PACKETCONFIG2) & 0xFB) | RF_PACKET2_RXRESTART)
        now = time.time()
        while (not self._canSend()) and time.time() - now < RF69_CSMA_LIMIT_S:
            self._receiveDone()
        self._sendFrame(toAddress, buff, requestACK, False)

    def sendWithRetry(self, toAddress, buff = "", retries = 3, retryWaitTime = 10):
        for i in range(0, retries):
            self.send(toAddress, buff, True)
            sentTime = time.time()
            while (time.time() - sentTime) * 1000 < retryWaitTime:
                if self._ACKReceived(toAddress):
                    return True
        return False


    def setFrequency(self, FRF):
        """Set the frequency"""
        self._writeReg(REG_FRFMSB, FRF >> 16)
        self._writeReg(REG_FRFMID, FRF >> 8)
        self._writeReg(REG_FRFLSB, FRF)

    def sleep(self):
        """Put the radio to sleep"""
        self._setMode(RF69_MODE_SLEEP)

    def readRegisters(self):
        """Get all register values.

        Returns:
            list: Register values
        """
        results = []
        for address in range(1, 0x50):
            results.append([str(hex(address)), str(bin(self._readReg(address)))])
        return results

    def readTemperature(self, calFactor=0):
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
        return (int(~self._readReg(REG_TEMP2)) * -1) + COURSE_TEMP_COEF + calFactor

    def calibrate(self):
        """Calibrate the internal RC oscillator for use in wide temperature variations.
        
        See RFM69 datasheet section [4.3.5. RC Timer Accuracy] for more information.
        """
        self._debug("Calibrating Radio")
        self._writeReg(REG_OSC1, RF_OSC1_RCCAL_START)
        while self._readReg(REG_OSC1) & RF_OSC1_RCCAL_DONE == 0x00:
            pass

    def shutdown(self):
        """Shutdown the radio.

        Puts the radio to sleep and cleans up the GPIO connections.
        """
        self._setHighPower(False)
        self.sleep()
        GPIO.cleanup()

    def getPackets(self):
        """Get newly received packets.

        Once packets have been yielded they are removed from the internal cache.
    
        Yields:
            RFM69Radio.Packet: Packet objects containing received data and associated meta data.
        """
        self._receiveDone()
        if len(self.packets) > 0:
            yield self.packets.pop()
        return

    def setPowerLevel(self, powerLevel):
        """Set the power level
        
        Args:
            powerLevel (int): Power level between 0 and 31.
        """
        if powerLevel > 31:
            powerLevel = 31
        self.powerLevel = powerLevel
        self._writeReg(REG_PALEVEL, (self._readReg(REG_PALEVEL) & 0xE0) | self.powerLevel)

    # 
    # Internal functions
    # 

    def _sendACK(self, toAddress=0, buff=""):
        """Respond to acknowledgement requests"""
        self._debug('[send Ack]')
        toAddress = toAddress if toAddress > 0 else self._SENDERID
        while not self._canSend():
            self._receiveDone()
        self._sendFrame(toAddress, buff, False, True)

    def _receiveBegin(self):
        """Start receiving"""
        self._debug('RX Begin')
        while self.intLock:
            self._debug('Waiting for int lock')
            time.sleep(.1)
        self._DATALEN = 0
        self._SENDERID = 0
        self._TARGETID = 0
        self._PAYLOADLEN = 0
        self._ACK_REQUESTED = 0
        self._ACK_RECEIVED = 0
        self._RSSI = 0
        if (self._readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_PAYLOADREADY):
            # avoid RX deadlocks
            self._writeReg(REG_PACKETCONFIG2, (self._readReg(REG_PACKETCONFIG2) & 0xFB) | RF_PACKET2_RXRESTART)
        #set DIO0 to "PAYLOADREADY" in receive mode
        self._writeReg(REG_DIOMAPPING1, RF_DIOMAPPING1_DIO0_01)
        self._setMode(RF69_MODE_RX)

    def _receiveDone(self):
        """Process received packets"""
        if (self.mode == RF69_MODE_RX or self.mode == RF69_MODE_STANDBY) and self._PAYLOADLEN > 0:
            self._setMode(RF69_MODE_STANDBY)
            # # Create packet
            # packet = Packet(self._TARGETID, self._SENDERID, self._RSSI, self._DATA)
            # self.packets.append(packet)
            # # Send acknowledgement if needed
            # if self._ACKRequested():
            #     self._sendACK(self._SENDERID)
            #     self._debug('Acknowledgement send')
            # else:
            #     self._debug('No acknowledgement request')
            # # self._receiveBegin() - not sure this is
            return True

        if self._readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_TIMEOUT:
            # https://github.com/russss/rfm69-python/blob/master/rfm69/rfm69.py#L112
            # Russss figured out that if you leave alone long enough it times out
            # tell it to stop being silly and listen for more packets
            self._writeReg(REG_PACKETCONFIG2, (self._readReg(REG_PACKETCONFIG2) & 0xFB) | RF_PACKET2_RXRESTART)
        elif self.mode == RF69_MODE_RX:
            # already in RX no payload yet
            return False
        self._receiveBegin()
        return False


  

    def _ACKReceived(self, fromNodeID):
        if self._receiveDone():
            return (self._SENDERID == fromNodeID or fromNodeID == RF69_BROADCAST_ADDR) and self._ACK_RECEIVED
        return False

    def _ACKRequested(self):
        return self._ACK_REQUESTED and self._TARGETID != RF69_BROADCAST_ADDR

    def _setMode(self, newMode):
        if newMode == self.mode:
            return
        if newMode == RF69_MODE_TX:
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_TRANSMITTER)
            if self.isRFM69HW:
                self._setHighPowerRegs(True)
            self._debug('TX Mode Set')
        elif newMode == RF69_MODE_RX:
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_RECEIVER)
            if self.isRFM69HW:
                self._setHighPowerRegs(False)
            self._debug('RX Mode Set')
        elif newMode == RF69_MODE_SYNTH:
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_SYNTHESIZER)
            self._debug('SYNTH Mode Set')
        elif newMode == RF69_MODE_STANDBY:
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_STANDBY)
            self._debug('STANDBY Mode Set')
        elif newMode == RF69_MODE_SLEEP:
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_SLEEP)
            self._debug('SLEEP Mode Set')
        else:
            self._error('Unknown {} Mode'.format(newMode))
            return
        # we are using packet mode, so this check is not really needed
        # but waiting for mode ready is necessary when going from sleep because the FIFO may not be immediately available from previous mode
        while self.mode == RF69_MODE_SLEEP and self._readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_MODEREADY == 0x00:
            pass
        self.mode = newMode
        

    def _setEncryptionKey(self, key):
        self._setMode(RF69_MODE_STANDBY)
        if key != 0 and len(key) == 16:
            self.spi.xfer([REG_AESKEY1 | 0x80] + [int(ord(i)) for i in list(key)])
            self._writeReg(REG_PACKETCONFIG2,(self._readReg(REG_PACKETCONFIG2) & 0xFE) | RF_PACKET2_AES_ON)
            return
        self._writeReg(REG_PACKETCONFIG2,(self._readReg(REG_PACKETCONFIG2) & 0xFE) | RF_PACKET2_AES_OFF)

    def _setAddress(self, addr):
        self.address = addr
        self._writeReg(REG_NODEADRS, self.address)

    def _setNetwork(self, networkID):
        self.networkID = networkID
        self._writeReg(REG_SYNCVALUE2, networkID)

    def _canSend(self):
        if self.mode == RF69_MODE_STANDBY:
            self._receiveBegin()
            return True
        #if signal stronger than -100dBm is detected assume channel activity
        elif self.mode == RF69_MODE_RX and self._PAYLOADLEN == 0 and self._readRSSI() < CSMA_LIMIT:
            self._setMode(RF69_MODE_STANDBY)
            return True
        return False

    def _sendFrame(self, toAddress, buff, requestACK, sendACK):
        self._debug('_sendFrame to {} "{}" ack: {}'.format(toAddress, buff, requestACK))
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
        self._DATASENT = False
        self._setMode(RF69_MODE_TX)
        while not self._DATASENT:
            if time.time() - startTime > 1.0:
                break
        self._setMode(RF69_MODE_RX)

    def _interruptHandler(self, pin):
        self._debug('---- Interrupt ----')
        self.intLock = True
        self.DATASENT = True
        if self.mode == RF69_MODE_RX and self._readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_PAYLOADREADY:
            self._setMode(RF69_MODE_STANDBY)
            self.PAYLOADLEN, self.TARGETID, self.SENDERID, CTLbyte = self.spi.xfer2([REG_FIFO & 0x7f,0,0,0,0])[1:]
            if self.PAYLOADLEN > 66:
                self.PAYLOADLEN = 66
            if not (self._promiscuousMode or self.TARGETID == self.address or self.TARGETID == RF69_BROADCAST_ADDR):
                self.PAYLOADLEN = 0
                self.intLock = False
                return
            self.DATALEN = self.PAYLOADLEN - 3
            self.ACK_RECEIVED = CTLbyte & 0x80
            self.ACK_REQUESTED = CTLbyte & 0x40

            self.DATA = self.spi.xfer2([REG_FIFO & 0x7f] + [0 for i in range(0, self.DATALEN)])[1:]

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

    def _readReg(self, addr):
        return self.spi.xfer([addr & 0x7F, 0])[1]

    def _writeReg(self, addr, value):
        self.spi.xfer([addr | 0x80, value])

    def _promiscuous(self, onOff):
        self._promiscuousMode = onOff

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


    def __str__(self):
        return "Radio RFM69 on Frequency {}".format(self.freqBand)

    def __repr__(self):
        return "Radio({}, {}, {})".format(self.freqBand, self._SENDERID, self.networkID)

    def _debug(self, *args):
        if self.logger is not None:
             self.logger.debug(*args)

    def _error(self, *args):
        if self.logger is not None:
             self.logger.error(*args)

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