#------------------------------------------------------------------------------
"""

Segger J-Link Driver

Tested with the J-Link Base

"""
#------------------------------------------------------------------------------

import struct
import time
import usb.core
import usb.util
from array import array as Array
from usbtools import UsbTools

#------------------------------------------------------------------------------

_TRST_TIME = 0.01
_SRST_TIME = 0.01

#------------------------------------------------------------------------------
# usb vendor:product IDs

_jlink_vps = (
    (0x1366, 0x0101), # J-Link Base
)

#------------------------------------------------------------------------------

class JLinkError(IOError):
    """Communication error with the J-Link device"""

class JLink(object):
  """J-Link Device Driver"""

  # Document RM08001-R7 J-Link USB Protocol
  # Commands
  EMU_CMD_VERSION                       = 0x01 # Retrieves the firmware version.
  EMU_CMD_RESET_TRST                    = 0x02
  EMU_CMD_RESET_TARGET                  = 0x03
  EMU_CMD_SET_SPEED                     = 0x05
  EMU_CMD_GET_STATE                     = 0x07
  EMU_CMD_SET_KS_POWER                  = 0x08
  EMU_CMD_REGISTER                      = 0x09
  EMU_CMD_GET_SPEEDS                    = 0xc0 # Retrieves the base freq. and the min.divider of the emulator CPU.
  EMU_CMD_GET_HW_INFO                   = 0xc1
  EMU_CMD_GET_COUNTERS                  = 0xc2
  EMU_CMD_SELECT_IF                     = 0xc7
  EMU_CMD_HW_CLOCK                      = 0xc8
  EMU_CMD_HW_TMS0                       = 0xc9
  EMU_CMD_HW_TMS1                       = 0xca
  EMU_CMD_HW_DATA0                      = 0xcb
  EMU_CMD_HW_DATA1                      = 0xcc
  EMU_CMD_HW_JTAG                       = 0xcd
  EMU_CMD_HW_JTAG2                      = 0xce
  EMU_CMD_HW_JTAG3                      = 0xcf
  EMU_CMD_HW_RELEASE_RESET_STOP_EX      = 0xd0
  EMU_CMD_HW_RELEASE_RESET_STOP_TIMED   = 0xd1
  EMU_CMD_GET_MAX_MEM_BLOCK             = 0xd4  # Retrieves the maximum memory block-size.
  EMU_CMD_HW_JTAG_WRITE                 = 0xd5
  EMU_CMD_HW_JTAG_GET_RESULT            = 0xd6
  EMU_CMD_HW_RESET0                     = 0xdc
  EMU_CMD_HW_RESET1                     = 0xdd
  EMU_CMD_HW_TRST0                      = 0xde
  EMU_CMD_HW_TRST1                      = 0xdf
  EMU_CMD_GET_CAPS                      = 0xe8 # Retrieves capabilities of the emulator.
  EMU_CMD_GET_CPU_CAPS                  = 0xe9
  EMU_CMD_EXEC_CPU_CMD                  = 0xea
  EMU_CMD_GET_CAPS_EX                   = 0xed # Retrieves capabilities (including extended ones) of the emulator.
  EMU_CMD_GET_HW_VERSION                = 0xf0 # Retrieves the hardware version of the emulator.
  EMU_CMD_WRITE_DCC                     = 0xf1
  EMU_CMD_READ_CONFIG                   = 0xf2
  EMU_CMD_WRITE_CONFIG                  = 0xf3
  EMU_CMD_WRITE_MEM                     = 0xf4
  EMU_CMD_READ_MEM                      = 0xf5
  EMU_CMD_MEASURE_RTCK_REACT            = 0xf6
  EMU_CMD_WRITE_MEM_ARM79               = 0xf7
  EMU_CMD_READ_MEM_ARM79                = 0xf8

  # Capabilities: EMU_CMD_GET_CAPS bits
  EMU_CAP_RESERVED_1            = 0
  EMU_CAP_GET_HW_VERSION        = 1
  EMU_CAP_WRITE_DCC             = 2
  EMU_CAP_ADAPTIVE_CLOCKING     = 3
  EMU_CAP_READ_CONFIG           = 4
  EMU_CAP_WRITE_CONFIG          = 5
  EMU_CAP_TRACE                 = 6
  EMU_CAP_WRITE_MEM             = 7
  EMU_CAP_READ_MEM              = 8
  EMU_CAP_SPEED_INFO            = 9
  EMU_CAP_EXEC_CODE             = 10
  EMU_CAP_GET_MAX_BLOCK_SIZE    = 11
  EMU_CAP_GET_HW_INFO           = 12
  EMU_CAP_SET_KS_POWER          = 13
  EMU_CAP_RESET_STOP_TIMED      = 14
  EMU_CAP_RESERVED_2            = 15
  EMU_CAP_MEASURE_RTCK_REACT    = 16
  EMU_CAP_SELECT_IF             = 17
  EMU_CAP_RW_MEM_ARM79          = 18
  EMU_CAP_GET_COUNTERS          = 19
  EMU_CAP_READ_DCC              = 20
  EMU_CAP_GET_CPU_CAPS          = 21
  EMU_CAP_EXEC_CPU_CMD          = 22
  EMU_CAP_SWO                   = 23
  EMU_CAP_WRITE_DCC_EX          = 24
  EMU_CAP_UPDATE_FIRMWARE_EX    = 25
  EMU_CAP_FILE_IO               = 26
  EMU_CAP_REGISTER              = 27
  EMU_CAP_INDICATORS            = 28
  EMU_CAP_TEST_NET_SPEED        = 29
  EMU_CAP_RAWTRACE              = 30
  EMU_CAP_RESERVED_3            = 31

  capabilities = {
    EMU_CAP_RESERVED_1         : "Always 1.",
    EMU_CAP_GET_HW_VERSION     : "EMU_CMD_GET_HARDWARE_VERSION",
    EMU_CAP_WRITE_DCC          : "EMU_CMD_WRITE_DCC",
    EMU_CAP_ADAPTIVE_CLOCKING  : "adaptive clocking",
    EMU_CAP_READ_CONFIG        : "EMU_CMD_READ_CONFIG",
    EMU_CAP_WRITE_CONFIG       : "EMU_CMD_WRITE_CONFIG",
    EMU_CAP_TRACE              : "trace commands",
    EMU_CAP_WRITE_MEM          : "EMU_CMD_WRITE_MEM",
    EMU_CAP_READ_MEM           : "EMU_CMD_READ_MEM",
    EMU_CAP_SPEED_INFO         : "EMU_CMD_GET_SPEED",
    EMU_CAP_EXEC_CODE          : "EMU_CMD_CODE_...",
    EMU_CAP_GET_MAX_BLOCK_SIZE : "EMU_CMD_GET_MAX_BLOCK_SIZE",
    EMU_CAP_GET_HW_INFO        : "EMU_CMD_GET_HW_INFO",
    EMU_CAP_SET_KS_POWER       : "EMU_CMD_SET_KS_POWER",
    EMU_CAP_RESET_STOP_TIMED   : "EMU_CMD_HW_RELEASE_RESET_STOP_TIMED",
    EMU_CAP_RESERVED_2         : "Reserved",
    EMU_CAP_MEASURE_RTCK_REACT : "EMU_CMD_MEASURE_RTCK_REACT",
    EMU_CAP_SELECT_IF          : "EMU_CMD_HW_SELECT_IF",
    EMU_CAP_RW_MEM_ARM79       : "EMU_CMD_READ/WRITE_MEM_ARM79",
    EMU_CAP_GET_COUNTERS       : "EMU_CMD_GET_COUNTERS",
    EMU_CAP_READ_DCC           : "EMU_CMD_READ_DCC",
    EMU_CAP_GET_CPU_CAPS       : "EMU_CMD_GET_CPU_CAPS",
    EMU_CAP_EXEC_CPU_CMD       : "EMU_CMD_EXEC_CPU_CMD",
    EMU_CAP_SWO                : "EMU_CMD_SWO",
    EMU_CAP_WRITE_DCC_EX       : "EMU_CMD_WRITE_DCC_EX",
    EMU_CAP_UPDATE_FIRMWARE_EX : "EMU_CMD_UPDATE_FIRMWARE_EX",
    EMU_CAP_FILE_IO            : "EMU_CMD_FILE_IO",
    EMU_CAP_REGISTER           : "EMU_CMD_REGISTER",
    EMU_CAP_INDICATORS         : "EMU_CMD_INDICATORS",
    EMU_CAP_TEST_NET_SPEED     : "EMU_CMD_TEST_NET_SPEED",
    EMU_CAP_RAWTRACE           : "EMU_CMD_RAWTRACE",
    EMU_CAP_RESERVED_3         : "Reserved",
  }

  # hardware types
  HW_TYPE_JLINK                 = 0
  HW_TYPE_JTRACE                = 1
  HW_TYPE_FLASHER               = 2
  HW_TYPE_JLINK_PRO             = 3
  HW_TYPE_JLINK_LITE_ADI        = 5
  HW_TYPE_JLINK_LITE_XMC4000    = 16
  HW_TYPE_JLINK_LITE_XMC4200    = 17
  HW_TYPE_LPCLINK2              = 18

  hw_type = {
    HW_TYPE_JLINK               : "J-Link",
    HW_TYPE_JTRACE              : "J-Trace",
    HW_TYPE_FLASHER             : "Flasher",
    HW_TYPE_JLINK_PRO           : "J-Link Pro",
    HW_TYPE_JLINK_LITE_ADI      : "J-Link Lite-ADI",
    HW_TYPE_JLINK_LITE_XMC4000  : "J-Link Lite-XMC4000",
    HW_TYPE_JLINK_LITE_XMC4200  : "J-Link Lite-XMC4200",
    HW_TYPE_LPCLINK2            : "J-Link on LPC-Link2",
  }

  def __init__(self):
    self.usb_dev = None
    self.usb_read_timeout = 5000
    self.usb_write_timeout = 5000
    self.readbuffer = Array('B')
    self.readoffset = 0
    self.readbuffer_chunksize = 4 << 10 # 4KiB
    self.writebuffer_chunksize = 4 << 10 # 4KiB
    self.interface = None
    self.index = None
    self.in_ep = None
    self.out_ep = None
    self._wrap_api()

  # --- Public API -------------------------------------------------------

  def open(self, vendor, product, interface=1, index=0, serial=None, description=None):
    """Open a new interface to the specified J-Link device"""
    self.usb_dev = UsbTools.get_device(vendor, product, index, serial, description)
    config = self.usb_dev.get_active_configuration()
    # detect invalid interface as early as possible
    if interface > config.bNumInterfaces:
      raise JLinkError('No such J-Link port: %d' % interface)
    self._set_interface(config, interface)
    self.max_packet_size = self._get_max_packet_size()
    self.caps = self.get_capabilities()

  def close(self):
    """Close the J-Link interface"""
    UsbTools.release_device(self.usb_dev)

  def write_data(self, data):
    """Write data in chunks to the chip"""
    offset = 0
    size = len(data)
    try:
      while offset < size:
        write_size = self.writebuffer_chunksize
        if offset + write_size > size:
          write_size = size - offset
        length = self._write(data[offset:offset+write_size])
        if length <= 0:
          raise JLinkError("Usb bulk write error")
        offset += length
      return offset
    except usb.core.USBError, e:
      raise JLinkError('UsbError: %s' % str(e))

  def read_data_bytes(self, size, attempt=1):
    """Read data in chunks from the chip."""
    # Packet size sanity check
    if not self.max_packet_size:
      raise JLinkError("max_packet_size is bogus")
    packet_size = self.max_packet_size
    length = 1 # initial condition to enter the usb_read loop
    data = Array('B')
    # everything we want is still in the cache?
    if size <= len(self.readbuffer) - self.readoffset:
      data = self.readbuffer[self.readoffset : self.readoffset + size]
      self.readoffset += size
      return data
    # something still in the cache, but not enough to satisfy 'size'?
    if len(self.readbuffer) - self.readoffset != 0:
      data = self.readbuffer[self.readoffset:]
      # end of readbuffer reached
      self.readoffset = len(self.readbuffer)
    # read from USB, filling in the local cache as it is empty
    try:
      while (len(data) < size) and (length > 0):
        while True:
          tempbuf = self._read()
          attempt -= 1
          length = len(tempbuf)
          if length > 0:
            # skip the status bytes
            chunks = (length + packet_size - 1) // packet_size
            count = packet_size
            self.readbuffer = Array('B')
            self.readoffset = 0
            srcoff = 0
            for i in xrange(chunks):
              self.readbuffer += tempbuf[srcoff : srcoff + count]
              srcoff += packet_size
            length = len(self.readbuffer)
            break
          else:
            # no data received, may be late, try again
            if attempt > 0:
              continue
            # no actual data
            self.readbuffer = Array('B')
            self.readoffset = 0
            # no more data to read?
            return data
        if length > 0:
          # data still fits in buf?
          if (len(data) + length) <= size:
            data += self.readbuffer[self.readoffset : self.readoffset + length]
            self.readoffset += length
            # did we read exactly the right amount of bytes?
            if len(data) == size:
              return data
          else:
            # partial copy, not enough bytes in the local cache to
            # fulfill the request
            part_size = min(size-len(data), len(self.readbuffer)-self.readoffset)
            if part_size < 0:
              raise AssertionError("Internal Error")
            data += self.readbuffer[self.readoffset:self.readoffset+part_size]
            self.readoffset += part_size
            return data
    except usb.core.USBError, e:
      raise JLinkError('UsbError: %s' % str(e))
    # never reached
    raise JLinkError("Internal error")

  def read_data(self, size):
    """Read data in chunks from the chip."""
    return self.read_data_bytes(size).tostring()

  def get_version(self):
    """Return the firmware version"""
    self.write_data(Array('B', [JLink.EMU_CMD_VERSION,]))
    n, = struct.unpack('<H', self.read_data(2))
    x = self.read_data(n)
    # split on nulls, get rid of empty strings
    return [s for s in x.split('\x00') if len(s)]

  def get_capabilities(self):
    """Return capabilities"""
    self.write_data(Array('B', [JLink.EMU_CMD_GET_CAPS,]))
    return struct.unpack('<I', self.read_data(4))[0]

  def get_hw_version(self):
    """Return the hardware version"""
    if not (self.caps & (1 << JLink.EMU_CAP_GET_HW_VERSION)):
      raise JLinkError("EMU_CMD_GET_HW_VERSION not supported")
    self.write_data(Array('B', [JLink.EMU_CMD_GET_HW_VERSION,]))
    return struct.unpack('<I', self.read_data(4))[0]

  def get_max_mem_block(self):
    """Return the maximum memory block sizwe of the device"""
    if not (self.caps & (1 << JLink.EMU_CAP_GET_MAX_BLOCK_SIZE)):
      raise JLinkError("EMU_CMD_GET_MAX_MEM_BLOCK not supported")
    self.write_data(Array('B', [JLink.EMU_CMD_GET_MAX_MEM_BLOCK,]))
    return struct.unpack('<I', self.read_data(4))[0]

  def get_config(self):
    """Return the 256 byte configuration block"""
    if not (self.caps & (1 << JLink.EMU_CAP_READ_CONFIG)):
      raise JLinkError("EMU_CMD_READ_CONFIG not supported")
    self.write_data(Array('B', [JLink.EMU_CMD_READ_CONFIG,]))
    return self.read_data(256)

  def trst(self, x):
    """Control the TRST line"""
    cmd = (JLink.EMU_CMD_HW_TRST0, JLink.EMU_CMD_HW_TRST1)[x]
    self.write_data(Array('B', [cmd,]))

  def srst(self, x):
    """Control the SRST line"""
    cmd = (JLink.EMU_CMD_HW_RESET0, JLink.EMU_CMD_HW_RESET1)[x]
    self.write_data(Array('B', [cmd,]))

  def __str__(self):
    s = ['%s' % x for x in self.get_version()]
    s.append('capabilities 0x%08x' % self.caps)
    for i in range(32):
      if self.caps & (1 << i):
        s.append('capability (%2d) %s' % (i, JLink.capabilities[i]))
    hw_version = self.get_hw_version()
    x = []
    x.append('hardware version %d:' % hw_version)
    hw_type = (hw_version / 1000000) % 100
    x.append('type %d (%s)' % (hw_type, JLink.hw_type[hw_type]))
    x.append('major %d' % ((hw_version / 10000) % 100))
    x.append('minor %d' % ((hw_version / 100) % 100))
    x.append('revision %d' % (hw_version % 100))
    s.append(' '.join(x))
    s.append('max mem block %d bytes' % self.get_max_mem_block())
    s = ['jlink: %s' % x for x in s]
    return '\n'.join(s)

#Info : Vref = 0.0 TCK = 1 TDI = 1 TDO = 1 TMS = 1 SRST = 1 TRST = 1
#Error: Vref too low. Check Target Power
#Info : J-Link JTAG Interface ready
#Info : clock speed 6000 kHz

  # --- Private implementation -------------------------------------------

  def _wrap_api(self):
      """Deal with PyUSB API breaks"""
      import inspect
      args, varargs, varkw, defaults = \
          inspect.getargspec(usb.core.Device.read)
      if (len(args) > 2) and (args[3] == 'interface'):
          usb_api = 1  # Require "interface" parameter
      else :
          usb_api = 2
      for m in ('write', 'read'):
          setattr(self, '_%s' % m, getattr(self, '_%s_v%d' % (m, usb_api)))

  def _set_interface(self, config, ifnum):
    """Select the interface to use on the J-Link device"""
    if ifnum == 0:
      ifnum = 1
    if ifnum-1 not in xrange(config.bNumInterfaces):
      raise ValueError("No such interface for this device")
    self.index = ifnum
    self.interface = config[(ifnum-1, 0)]
    endpoints = sorted([ep.bEndpointAddress for ep in self.interface])
    self.in_ep, self.out_ep = endpoints[:2]

  def _write_v1(self, data):
    """Write using the deprecated API"""
    return self.usb_dev.write(self.in_ep, data, self.interface, self.usb_write_timeout)

  def _read_v1(self):
    """Read using the deprecated API"""
    return self.usb_dev.read(self.out_ep, self.readbuffer_chunksize, self.interface, self.usb_read_timeout)

  def _write_v2(self, data):
    """Write using the API introduced with pyusb 1.0.0b2"""
    return self.usb_dev.write(self.in_ep, data, self.usb_write_timeout)

  def _read_v2(self):
    """Read using the API introduced with pyusb 1.0.0b2"""
    return self.usb_dev.read(self.out_ep, self.readbuffer_chunksize, self.usb_read_timeout)

  def _get_max_packet_size(self):
    """Retrieve the maximum length of a data packet"""
    if not self.usb_dev:
      raise AssertionError("Device is not yet known")
    if not self.interface:
      raise AssertionError("Interface is not yet known")
    endpoint = self.interface[0]
    packet_size = endpoint.wMaxPacketSize
    return packet_size

#------------------------------------------------------------------------------

class jtag:

  def __init__(self, sn = None):
    devices = UsbTools.find_all(_jlink_vps)
    if sn is not None:
        # filter based on device serial number
        devices = [dev for dev in devices if dev[2] == sn]
    if len(devices) == 0:
        raise IOError("No such device")
    self.vid = devices[0][0]
    self.pid = devices[0][1]
    self.sn = devices[0][2]
    self.jlink = JLink()
    self.jlink.open(self.vid, self.pid, serial = self.sn)
    print self.jlink
    print self

  def __del__(self):
    if self.jlink:
      self.jlink.close()

  def scan_ir(self, tdi, tdo = None):
    """write (and possibly read) a bit stream through the IR in the JTAG chain"""
    #self.state_x('IRSHIFT')
    #self.shift_data(tdi, tdo, self.sir_end_state)

  def scan_dr(self, tdi, tdo = None):
    """write (and possibly read) a bit stream through the DR in the JTAG chain"""
    #self.state_x('DRSHIFT')
    #self.shift_data(tdi, tdo, self.sdr_end_state)

  def trst(self):
    """pulse the test reset line"""
    self.jlink.trst(0)
    time.sleep(_TRST_TIME)
    self.jlink.trst(1)
    #self.state_reset()

  def srst(self):
    """pulse the system reset line"""
    self.jlink.srst(0)
    time.sleep(_SRST_TIME)
    self.jlink.srst(1)

  def __str__(self):
      s = []
      s.append('Segger J-Link %04x:%04x serial %r' % (self.vid, self.pid, self.sn))
      return ', '.join(s)

#------------------------------------------------------------------------------

