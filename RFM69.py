#!/usr/bin/env python2

from RFM69registers import *
import spidev
import RPi.GPIO as GPIO
import time

class RFM69(object):
    def __init__(self, freqBand, nodeID, networkID, isRFM69HW = False, intPin = 18, rstPin = 29, spiBus = 0, spiDevice = 0):

        self.freqBand = freqBand
        self.address = nodeID
        self.networkID = networkID
        self.isRFM69HW = isRFM69HW
        self.intPin = intPin
        self.rstPin = rstPin
        self.spiBus = spiBus
        self.spiDevice = spiDevice
        self.intLock = False
        self.mode = ""
        self.promiscuousMode = False
        self.DATASENT = False
        self.DATALEN = 0
        self.SENDERID = 0
        self.TARGETID = 0
        self.PAYLOADLEN = 0
        self.ACK_REQUESTED = 0
        self.ACK_RECEIVED = 0
        self.RSSI = 0
        self.DATA = []

        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.intPin, GPIO.IN)
        GPIO.setup(self.rstPin, GPIO.OUT)

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
        GPIO.output(self.rstPin, GPIO.HIGH);
        time.sleep(0.1)
        GPIO.output(self.rstPin, GPIO.LOW);
        time.sleep(0.1)

        #verify chip is syncing?
        while self.readReg(REG_SYNCVALUE1) != 0xAA:
            self.writeReg(REG_SYNCVALUE1, 0xAA)

        while self.readReg(REG_SYNCVALUE1) != 0x55:
            self.writeReg(REG_SYNCVALUE1, 0x55)

        #write config
        for value in self.CONFIG.values():
            self.writeReg(value[0], value[1])

        self.encrypt(0)
        self.setHighPower(self.isRFM69HW)
        # Wait for ModeReady
        while (self.readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_MODEREADY) == 0x00:
            pass

        GPIO.remove_event_detect(self.intPin)
        GPIO.add_event_detect(self.intPin, GPIO.RISING, callback=self.interruptHandler)

    def setFreqeuncy(self, FRF):
        self.writeReg(REG_FRFMSB, FRF >> 16)
        self.writeReg(REG_FRFMID, FRF >> 8)
        self.writeReg(REG_FRFLSB, FRF)

    def setMode(self, newMode):
        if newMode == self.mode:
            return

        if newMode == RF69_MODE_TX:
            self.writeReg(REG_OPMODE, (self.readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_TRANSMITTER)
            if self.isRFM69HW:
                self.setHighPowerRegs(True)
        elif newMode == RF69_MODE_RX:
            self.writeReg(REG_OPMODE, (self.readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_RECEIVER)
            if self.isRFM69HW:
                self.setHighPowerRegs(False)
        elif newMode == RF69_MODE_SYNTH:
            self.writeReg(REG_OPMODE, (self.readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_SYNTHESIZER)
        elif newMode == RF69_MODE_STANDBY:
            self.writeReg(REG_OPMODE, (self.readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_STANDBY)
        elif newMode == RF69_MODE_SLEEP:
            self.writeReg(REG_OPMODE, (self.readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_SLEEP)
        else:
            return

        # we are using packet mode, so this check is not really needed
        # but waiting for mode ready is necessary when going from sleep because the FIFO may not be immediately available from previous mode
        while self.mode == RF69_MODE_SLEEP and self.readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_MODEREADY == 0x00:
            pass

        self.mode = newMode;

    def sleep(self):
        self.setMode(RF69_MODE_SLEEP)

    def setAddress(self, addr):
        self.address = addr
        self.writeReg(REG_NODEADRS, self.address)

    def setNetwork(self, networkID):
        self.networkID = networkID
        self.writeReg(REG_SYNCVALUE2, networkID)

    def setPowerLevel(self, powerLevel):
        if powerLevel > 31:
            powerLevel = 31
        self.powerLevel = powerLevel
        self.writeReg(REG_PALEVEL, (self.readReg(REG_PALEVEL) & 0xE0) | self.powerLevel)

    def canSend(self):
        if self.mode == RF69_MODE_STANDBY:
            self.receiveBegin()
            return True
        #if signal stronger than -100dBm is detected assume channel activity
        elif self.mode == RF69_MODE_RX and self.PAYLOADLEN == 0 and self.readRSSI() < CSMA_LIMIT:
            self.setMode(RF69_MODE_STANDBY)
            return True
        return False

    def send(self, toAddress, buff = "", requestACK = False):
        self.writeReg(REG_PACKETCONFIG2, (self.readReg(REG_PACKETCONFIG2) & 0xFB) | RF_PACKET2_RXRESTART)
        now = time.time()
        while (not self.canSend()) and time.time() - now < RF69_CSMA_LIMIT_S:
            self.receiveDone()
        self.sendFrame(toAddress, buff, requestACK, False)

#    to increase the chance of getting a packet across, call this function instead of send
#    and it handles all the ACK requesting/retrying for you :)
#    The only twist is that you have to manually listen to ACK requests on the other side and send back the ACKs
#    The reason for the semi-automaton is that the lib is ingterrupt driven and
#    requires user action to read the received data and decide what to do with it
#    replies usually take only 5-8ms at 50kbps@915Mhz

    def sendWithRetry(self, toAddress, buff = "", retries = 3, retryWaitTime = 10):
        for i in range(0, retries):
            self.send(toAddress, buff, True)
            sentTime = time.time()
            while (time.time() - sentTime) * 1000 < retryWaitTime:
                if self.ACKReceived(toAddress):
                    return True
        return False

    def ACKReceived(self, fromNodeID):
        if self.receiveDone():
            return (self.SENDERID == fromNodeID or fromNodeID == RF69_BROADCAST_ADDR) and self.ACK_RECEIVED
        return False

    def ACKRequested(self):
        return self.ACK_REQUESTED and self.TARGETID != RF69_BROADCAST_ADDR

    def sendACK(self, toAddress = 0, buff = ""):
        toAddress = toAddress if toAddress > 0 else self.SENDERID
        while not self.canSend():
            self.receiveDone()
        self.sendFrame(toAddress, buff, False, True)

    def sendFrame(self, toAddress, buff, requestACK, sendACK):
        #turn off receiver to prevent reception while filling fifo
        self.setMode(RF69_MODE_STANDBY)
        #wait for modeReady
        while (self.readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_MODEREADY) == 0x00:
            pass
        # DIO0 is "Packet Sent"
        self.writeReg(REG_DIOMAPPING1, RF_DIOMAPPING1_DIO0_00)

        if (len(buff) > RF69_MAX_DATA_LEN):
            buff = buff[0:RF69_MAX_DATA_LEN]

        ack = 0
        if sendACK:
            ack = 0x80
        elif requestACK:
            ack = 0x40
        if isinstance(buff, basestring):
            self.spi.xfer2([REG_FIFO | 0x80, len(buff) + 3, toAddress, self.address, ack] + [int(ord(i)) for i in list(buff)])
        else:
            self.spi.xfer2([REG_FIFO | 0x80, len(buff) + 3, toAddress, self.address, ack] + buff)

        startTime = time.time()
        self.DATASENT = False
        self.setMode(RF69_MODE_TX)
        while not self.DATASENT:
            if time.time() - startTime > 1.0:
                break
        self.setMode(RF69_MODE_RX)

    def interruptHandler(self, pin):
        self.intLock = True
        self.DATASENT = True
        if self.mode == RF69_MODE_RX and self.readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_PAYLOADREADY:
            self.setMode(RF69_MODE_STANDBY)
            self.PAYLOADLEN, self.TARGETID, self.SENDERID, CTLbyte = self.spi.xfer2([REG_FIFO & 0x7f,0,0,0,0])[1:]
            if self.PAYLOADLEN > 66:
                self.PAYLOADLEN = 66
            if not (self.promiscuousMode or self.TARGETID == self.address or self.TARGETID == RF69_BROADCAST_ADDR):
                self.PAYLOADLEN = 0
                self.intLock = False
                return
            self.DATALEN = self.PAYLOADLEN - 3
            self.ACK_RECEIVED = CTLbyte & 0x80
            self.ACK_REQUESTED = CTLbyte & 0x40

            self.DATA = self.spi.xfer2([REG_FIFO & 0x7f] + [0 for i in range(0, self.DATALEN)])[1:]

            self.RSSI = self.readRSSI()
        self.intLock = False

    def receiveBegin(self):

        while self.intLock:
            time.sleep(.1)
        self.DATALEN = 0
        self.SENDERID = 0
        self.TARGETID = 0
        self.PAYLOADLEN = 0
        self.ACK_REQUESTED = 0
        self.ACK_RECEIVED = 0
        self.RSSI = 0
        if (self.readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_PAYLOADREADY):
            # avoid RX deadlocks
            self.writeReg(REG_PACKETCONFIG2, (self.readReg(REG_PACKETCONFIG2) & 0xFB) | RF_PACKET2_RXRESTART)
        #set DIO0 to "PAYLOADREADY" in receive mode
        self.writeReg(REG_DIOMAPPING1, RF_DIOMAPPING1_DIO0_01)
        self.setMode(RF69_MODE_RX)

    def receiveDone(self):
        if (self.mode == RF69_MODE_RX or self.mode == RF69_MODE_STANDBY) and self.PAYLOADLEN > 0:
            self.setMode(RF69_MODE_STANDBY)
            return True
        if self.readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_TIMEOUT:
            # https://github.com/russss/rfm69-python/blob/master/rfm69/rfm69.py#L112
            # Russss figured out that if you leave alone long enough it times out
            # tell it to stop being silly and listen for more packets
            self.writeReg(REG_PACKETCONFIG2, (self.readReg(REG_PACKETCONFIG2) & 0xFB) | RF_PACKET2_RXRESTART)
        elif self.mode == RF69_MODE_RX:
            # already in RX no payload yet
            return False
        self.receiveBegin()
        return False

    def readRSSI(self, forceTrigger = False):
        rssi = 0
        if forceTrigger:
            self.writeReg(REG_RSSICONFIG, RF_RSSI_START)
            while self.readReg(REG_RSSICONFIG) & RF_RSSI_DONE == 0x00:
                pass
        rssi = self.readReg(REG_RSSIVALUE) * -1
        rssi = rssi >> 1
        return rssi

    def encrypt(self, key):
        self.setMode(RF69_MODE_STANDBY)
        if key != 0 and len(key) == 16:
            self.spi.xfer([REG_AESKEY1 | 0x80] + [int(ord(i)) for i in list(key)])
            self.writeReg(REG_PACKETCONFIG2,(self.readReg(REG_PACKETCONFIG2) & 0xFE) | RF_PACKET2_AES_ON)
        else:
            self.writeReg(REG_PACKETCONFIG2,(self.readReg(REG_PACKETCONFIG2) & 0xFE) | RF_PACKET2_AES_OFF)

    def readReg(self, addr):
        return self.spi.xfer([addr & 0x7F, 0])[1]

    def writeReg(self, addr, value):
        self.spi.xfer([addr | 0x80, value])

    def promiscuous(self, onOff):
        self.promiscuousMode = onOff

    def setHighPower(self, onOff):
        if onOff:
            self.writeReg(REG_OCP, RF_OCP_OFF)
            #enable P1 & P2 amplifier stages
            self.writeReg(REG_PALEVEL, (self.readReg(REG_PALEVEL) & 0x1F) | RF_PALEVEL_PA1_ON | RF_PALEVEL_PA2_ON)
        else:
            self.writeReg(REG_OCP, RF_OCP_ON)
            #enable P0 only
            self.writeReg(REG_PALEVEL, RF_PALEVEL_PA0_ON | RF_PALEVEL_PA1_OFF | RF_PALEVEL_PA2_OFF | powerLevel)

    def setHighPowerRegs(self, onOff):
        if onOff:
            self.writeReg(REG_TESTPA1, 0x5D)
            self.writeReg(REG_TESTPA2, 0x7C)
        else:
            self.writeReg(REG_TESTPA1, 0x55)
            self.writeReg(REG_TESTPA2, 0x70)

    def readAllRegs(self):
        results = []
        for address in range(1, 0x50):
            results.append([str(hex(address)), str(bin(self.readReg(address)))])
        return results

    def readTemperature(self, calFactor):
        self.setMode(RF69_MODE_STANDBY)
        self.writeReg(REG_TEMP1, RF_TEMP1_MEAS_START)
        while self.readReg(REG_TEMP1) & RF_TEMP1_MEAS_RUNNING:
            pass
        # COURSE_TEMP_COEF puts reading in the ballpark, user can add additional correction
        #'complement'corrects the slope, rising temp = rising val
        return (int(~self.readReg(REG_TEMP2)) * -1) + COURSE_TEMP_COEF + calFactor


    def rcCalibration(self):
        self.writeReg(REG_OSC1, RF_OSC1_RCCAL_START)
        while self.readReg(REG_OSC1) & RF_OSC1_RCCAL_DONE == 0x00:
            pass

    def shutdown(self):
        self.setHighPower(False)
        self.sleep()
        GPIO.cleanup()
