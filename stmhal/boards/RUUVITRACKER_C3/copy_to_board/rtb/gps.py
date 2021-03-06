# TODO: shamelessly steal all the good ideas from https://gist.github.com/nvbn/80c7b434ee21c99f013d
# Like passing the valid GPS coordinates via yielding from queue 
import pyb
import rtb
import uartparser
from uasyncio.core import get_event_loop, sleep
import nmea
from nmea import FIX_TYPE_NONE, FIX_TYPE_2D, FIX_TYPE_3D
from nmea import MSG_GPRMC, MSG_GPGSA, MSG_GPGGA


# The handler class
class GPS:
    uart_lld = None # Low-Level UART
    uart = None # This is the parser
    last_fix = None

    def __init__(self):
        pass

    def start(self):
        # We might call start/stop multiple times and in stop we do not release VBACKUP by default
        if not rtb.pwr.GPS_VBACKUP.status():
            rtb.pwr.GPS_VBACKUP.request()
        rtb.pwr.GPS_VCC.request()
        rtb.pwr.GPS_ANT.request()
        self.uart_lld = pyb.UART(rtb.GPS_UART_N, 115200, timeout=0, read_buf_len=256)
        self.uart = uartparser.UARTParser(self.uart_lld)
        
        # TODO: Add NMEA parsing callbacks here
        self.uart.add_line_callback(r'all', r'startswith', r'$', self.print_line)

        self.uart.add_re_callback(r'RMC', r'^\$G[PLN]RMC,.*', self.gprmc_received)
        self.uart.add_re_callback(r'GGA', r'^\$G[PLN]GGA,.*', self.gpgga_received)
        self.uart.add_re_callback(r'GSA', r'^\$G[PLN]GSA,.*', self.gpgsa_received)
        
        # The parsers start method is a generator so it's called like this
        get_event_loop().create_task(self.uart.start())

    # TODO: Add GPS command methods (like setting the interval, putting the module to various sleep modes etc)

    def gprmc_received(self, match):
        line = match.group(0)
        # Skip checksum failures
        if not nmea.checksum(line):
            return
        # Reset the last_fix
        # TODO: Actually I think we get GGA/GSA first and RMC after them so this might not be the correct order (OTOH without RMC we can't do much...)
        self.last_fix = nmea.Fix()
        nmea.parse_gprmc(line, self.last_fix)
        self.last_fix.last_update = pyb.millis()
        # TODO: Check if anyone wants to see the fix yet
        print("===\r\nRMC lat=%s lon=%s\r\n==" % (self.last_fix.lat, self.last_fix.lon))

    def gpgga_received(self, match):
        line = match.group(0)
        # Skip checksum failures
        if not nmea.checksum(line):
            return
        nmea.parse_gpgga(line, self.last_fix)
        # TODO: Check if anyone wants to see the fix yet
        print("===\r\nGGA lat=%s lon=%s altitude=%s\r\n==" % (self.last_fix.lat, self.last_fix.lon, self.last_fix.altitude))

    def gpgsa_received(self, match):
        line = match.group(0)
        # Skip checksum failures
        if not nmea.checksum(line):
            return
        nmea.parse_gpgsa(line, self.last_fix)
        # TODO: Check if anyone wants to see the fix yet
        print("===\r\nGSA lat=%s lon=%s altitude=%s fix_type=%s\r\n==" % (self.last_fix.lat, self.last_fix.lon, self.last_fix.altitude, self.last_fix.fix_type))

    def set_interval(self, ms):
        """Set update interval in milliseconds"""
        self.uart_lld.write(nmea.checksum("$PMTK300,%d,0,0,0,0\r\n" % ms))
        # TODO: Check the response somehow ?

    def set_standby(self, state):
        """Set or exit the standby mode, set to True or False"""
        self.uart_lld.write(nmea.checksum("$PMTK161,%d\r\n" % ms))
        # TODO: Check the response somehow ?

    def print_line(self, line):
        print(line)

    def stop(self):
        self.uart.del_re_callback('RMC')
        self.uart.del_re_callback('GGA')
        self.uart.del_re_callback('GSA')
        self.uart.del_line_callback('all')
        self.uart.stop()
        self.uart_lld.deinit()
        rtb.pwr.GPS_VCC.release()
        rtb.pwr.GPS_ANT.release()
        # GPS_VBACKUP is left ureleased on purpose to allow for warm starts

instance = GPS()
