
from .registers import *

frfMSB = {RF69_315MHZ: RF_FRFMSB_315, RF69_433MHZ: RF_FRFMSB_433, RF69_868MHZ: RF_FRFMSB_868, RF69_915MHZ: RF_FRFMSB_915}
frfMID = {RF69_315MHZ: RF_FRFMID_315, RF69_433MHZ: RF_FRFMID_433, RF69_868MHZ: RF_FRFMID_868, RF69_915MHZ: RF_FRFMID_915}
frfLSB = {RF69_315MHZ: RF_FRFLSB_315, RF69_433MHZ: RF_FRFLSB_433, RF69_868MHZ: RF_FRFLSB_868, RF69_915MHZ: RF_FRFLSB_915}

def get_config(freqBand, networkID):
    return {
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