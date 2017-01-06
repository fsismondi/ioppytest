import json
import logging
import os
import struct
import threading
import time
import traceback
import uuid
from fcntl import ioctl
import sys

from kombu import Exchange

DEFAULT_IPV6_PREFIX = 'bbbb'

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

# ============================ defines =========================================

# insert 4 octedts ID tun for compatibility (it'll be discard)
VIRTUALTUNID = [0x00, 0x00, 0x86, 0xdd]

IFF_TUN = 0x0001
TUNSETIFF = 0x400454ca


def buf2int(buf):
    """
    Converts some consecutive bytes of a buffer into an integer.
    Big-endianness is assumed.

    :param buf:      [in] Byte array.
    """
    returnVal = 0
    for i in range(len(buf)):
        returnVal += buf[i] << (8 * (len(buf) - i - 1))
    return returnVal


# ===== formatting

def formatStringBuf(buf):
    return '({0:>2}B) {1}'.format(
        len(buf),
        '-'.join(["%02x" % ord(b) for b in buf]),
    )


def formatBuf(buf):
    """
    Format a bytelist into an easy-to-read string. For example:
    ``[0xab,0xcd,0xef,0x00] -> '(4B) ab-cd-ef-00'``
    """
    return '({0:>2}B) {1}'.format(
        len(buf),
        '-'.join(["%02x" % b for b in buf]),
    )


def formatIPv6Addr(addr):
    # group by 2 bytes
    addr = [buf2int(addr[2 * i:2 * i + 2]) for i in range(len(addr) / 2)]
    return ':'.join(["%x" % b for b in addr])


def formatAddr(addr):
    return '-'.join(["%02x" % b for b in addr])


def formatThreadList():
    return '\nActive threads ({0})\n   {1}'.format(
        threading.activeCount(),
        '\n   '.join([t.name for t in threading.enumerate()]),
    )


# ===== parsing

def hex2buf(s):
    """
    Convert a string of hex caracters into a byte list. For example:
    ``'abcdef00' -> [0xab,0xcd,0xef,0x00]``

    :param s: [in] The string to convert

    :returns: A list of integers, each element in [0x00..0xff].
    """
    assert type(s) == str
    assert len(s) % 2 == 0

    returnVal = []

    for i in range(len(s) / 2):
        realIdx = i * 2
        returnVal.append(int(s[realIdx:realIdx + 2], 16))

    return returnVal


# ===== CRC

def calculateCRC(payload):
    checksum = [0x00] * 2

    checksum = _oneComplementSum(payload, checksum)

    checksum[0] ^= 0xFF
    checksum[1] ^= 0xFF

    checksum[0] = int(checksum[0])
    checksum[1] = int(checksum[1])

    return checksum


def calculatePseudoHeaderCRC(src, dst, length, nh, payload):
    """
    See these references:

    * http://www-net.cs.umass.edu/kurose/transport/UDP.html
    * http://tools.ietf.org/html/rfc1071
    * http://en.wikipedia.org/wiki/User_Datagram_Protocol#IPv6_PSEUDO-HEADER
    """

    checksum = [0x00] * 2

    # compute pseudo header crc
    checksum = _oneComplementSum(src, checksum)
    checksum = _oneComplementSum(dst, checksum)
    checksum = _oneComplementSum(length, checksum)
    checksum = _oneComplementSum(nh, checksum)
    checksum = _oneComplementSum(payload, checksum)

    checksum[0] ^= 0xFF
    checksum[1] ^= 0xFF

    checksum[0] = int(checksum[0])
    checksum[1] = int(checksum[1])

    return checksum


def _oneComplementSum(field, checksum):
    sum = 0xFFFF & (checksum[0] << 8 | checksum[1])
    i = len(field)
    while i > 1:
        sum += 0xFFFF & (field[-i] << 8 | (field[-i + 1]))
        i -= 2
    if i:
        sum += (0xFF & field[-1]) << 8
    while sum >> 16:
        sum = (sum & 0xFFFF) + (sum >> 16)

    checksum[0] = (sum >> 8) & 0xFF
    checksum[1] = sum & 0xFF

    return checksum


def byteinverse(b):
    # TODO: speed up through lookup table
    rb = 0
    for pos in range(8):
        if b & (1 << pos) != 0:
            bitval = 1
        else:
            bitval = 0
        rb |= bitval << (7 - pos)
    return rb


def calculateFCS(rpayload):
    payload = []
    for b in rpayload:
        payload += [byteinverse(b)]

    FCS16TAB = (
        0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7,
        0x8108, 0x9129, 0xa14a, 0xb16b, 0xc18c, 0xd1ad, 0xe1ce, 0xf1ef,
        0x1231, 0x0210, 0x3273, 0x2252, 0x52b5, 0x4294, 0x72f7, 0x62d6,
        0x9339, 0x8318, 0xb37b, 0xa35a, 0xd3bd, 0xc39c, 0xf3ff, 0xe3de,
        0x2462, 0x3443, 0x0420, 0x1401, 0x64e6, 0x74c7, 0x44a4, 0x5485,
        0xa56a, 0xb54b, 0x8528, 0x9509, 0xe5ee, 0xf5cf, 0xc5ac, 0xd58d,
        0x3653, 0x2672, 0x1611, 0x0630, 0x76d7, 0x66f6, 0x5695, 0x46b4,
        0xb75b, 0xa77a, 0x9719, 0x8738, 0xf7df, 0xe7fe, 0xd79d, 0xc7bc,
        0x48c4, 0x58e5, 0x6886, 0x78a7, 0x0840, 0x1861, 0x2802, 0x3823,
        0xc9cc, 0xd9ed, 0xe98e, 0xf9af, 0x8948, 0x9969, 0xa90a, 0xb92b,
        0x5af5, 0x4ad4, 0x7ab7, 0x6a96, 0x1a71, 0x0a50, 0x3a33, 0x2a12,
        0xdbfd, 0xcbdc, 0xfbbf, 0xeb9e, 0x9b79, 0x8b58, 0xbb3b, 0xab1a,
        0x6ca6, 0x7c87, 0x4ce4, 0x5cc5, 0x2c22, 0x3c03, 0x0c60, 0x1c41,
        0xedae, 0xfd8f, 0xcdec, 0xddcd, 0xad2a, 0xbd0b, 0x8d68, 0x9d49,
        0x7e97, 0x6eb6, 0x5ed5, 0x4ef4, 0x3e13, 0x2e32, 0x1e51, 0x0e70,
        0xff9f, 0xefbe, 0xdfdd, 0xcffc, 0xbf1b, 0xaf3a, 0x9f59, 0x8f78,
        0x9188, 0x81a9, 0xb1ca, 0xa1eb, 0xd10c, 0xc12d, 0xf14e, 0xe16f,
        0x1080, 0x00a1, 0x30c2, 0x20e3, 0x5004, 0x4025, 0x7046, 0x6067,
        0x83b9, 0x9398, 0xa3fb, 0xb3da, 0xc33d, 0xd31c, 0xe37f, 0xf35e,
        0x02b1, 0x1290, 0x22f3, 0x32d2, 0x4235, 0x5214, 0x6277, 0x7256,
        0xb5ea, 0xa5cb, 0x95a8, 0x8589, 0xf56e, 0xe54f, 0xd52c, 0xc50d,
        0x34e2, 0x24c3, 0x14a0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
        0xa7db, 0xb7fa, 0x8799, 0x97b8, 0xe75f, 0xf77e, 0xc71d, 0xd73c,
        0x26d3, 0x36f2, 0x0691, 0x16b0, 0x6657, 0x7676, 0x4615, 0x5634,
        0xd94c, 0xc96d, 0xf90e, 0xe92f, 0x99c8, 0x89e9, 0xb98a, 0xa9ab,
        0x5844, 0x4865, 0x7806, 0x6827, 0x18c0, 0x08e1, 0x3882, 0x28a3,
        0xcb7d, 0xdb5c, 0xeb3f, 0xfb1e, 0x8bf9, 0x9bd8, 0xabbb, 0xbb9a,
        0x4a75, 0x5a54, 0x6a37, 0x7a16, 0x0af1, 0x1ad0, 0x2ab3, 0x3a92,
        0xfd2e, 0xed0f, 0xdd6c, 0xcd4d, 0xbdaa, 0xad8b, 0x9de8, 0x8dc9,
        0x7c26, 0x6c07, 0x5c64, 0x4c45, 0x3ca2, 0x2c83, 0x1ce0, 0x0cc1,
        0xef1f, 0xff3e, 0xcf5d, 0xdf7c, 0xaf9b, 0xbfba, 0x8fd9, 0x9ff8,
        0x6e17, 0x7e36, 0x4e55, 0x5e74, 0x2e93, 0x3eb2, 0x0ed1, 0x1ef0
    )
    crc = 0x0000
    for b in payload:
        crc = ((crc << 8) & 0xffff) ^ FCS16TAB[((crc >> 8) ^ b) & 0xff]

    returnVal = [
        byteinverse(crc >> 8),
        byteinverse(crc & 0xff)
    ]
    return returnVal


def formatCriticalMessage(error):
    returnVal = []
    returnVal += ['Error:']
    returnVal += [str(error)]
    returnVal += ['\ncall stack:\n']
    returnVal += [traceback.format_exc()]
    returnVal += ['\n']
    returnVal = '\n'.join(returnVal)
    return returnVal


def formatCrashMessage(threadName, error):
    returnVal = []
    returnVal += ['\n']
    returnVal += ['======= crash in {0} ======='.format(threadName)]
    returnVal += [formatCriticalMessage(error)]
    returnVal = '\n'.join(returnVal)
    return returnVal


class TunReadThread(threading.Thread):
    """
    Thread which continously reads input from a TUN interface.

    When data is received from the interface, it calls a callback configured
    during instantiation.
    """

    ETHERNET_MTU = 1500
    IPv6_HEADER_LENGTH = 40

    def __init__(self, tunIf, callback):

        # store params
        self.tunIf = tunIf
        self.callback = callback

        # local variables
        self.goOn = True

        # initialize parent
        threading.Thread.__init__(self)

        # give this thread a name
        self.name = 'TunReadThread'

        # start myself
        self.start()

    def run(self):
        try:
            p = []

            while self.goOn:

                # wait for data
                p = os.read(self.tunIf, self.ETHERNET_MTU)

                # convert input from a string to a byte list
                p = [ord(b) for b in p]

                # debug info
                log.debug('packet captured on tun interface: {0}'.format(formatBuf(p)))
                log.debug('packet captured on tun interface: {0}'.format(formatBuf(p)))

                # remove tun ID octets
                #p = p[4:]

                # make sure it's an IPv6 packet (i.e., starts with 0x6x)
                if (p[0] & 0xf0) != 0x60:
                    log.info('this is not an IPv6 packet')
                    continue

                # because of the nature of tun for Windows, p contains ETHERNET_MTU
                # bytes. Cut at length of IPv6 packet.
                p = p[:self.IPv6_HEADER_LENGTH + 256 * p[4] + p[5]]

                # call the callback
                self.callback(p)

        except Exception as err:
            errMsg = formatCrashMessage(self.name, err)
            log.critical(errMsg)
            sys.exit(1)

    # ======================== public ==========================================

    def close(self):
        self.goOn = False


class OpenTunLinux(object):
    """
    Class which interfaces between a TUN virtual interface and an EventBus.
    """

    def __init__(self, name, rmq_connection, exchange="default",
                 ipv6_prefix=None, ipv6_host=None,
                 ipv4_host=None, ipv4_network=None, ipv4_netmask=None):
        # log
        log.info("create instance")

        self.name = name

        if ipv6_prefix is None:
            # self.ipv6_prefix = [0xbb, 0xbb, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
            ipv6_prefix = DEFAULT_IPV6_PREFIX

        self.ipv6_prefix = ipv6_prefix

        if ipv6_host is None:
            # self.ipv6_host = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01]
            ipv6_host = ":1"

        self.ipv6_host = ipv6_host

        if ipv4_host is None:
            ipv4_host = "2.2.2.2"

        self.ipv4_host = ipv4_host

        if ipv4_network is None:
            ipv4_network = [10, 2, 0, 0]
        self.ipv4_network = ipv4_network

        if ipv4_netmask is None:
            ipv4_netmask = [255, 255, 0, 0]
        self.ipv4_netmask = ipv4_netmask

        log.debug("IP info")
        log.debug(self.ipv6_prefix)
        log.debug(self.ipv6_host)
        log.debug(self.ipv4_host)
        log.debug(self.ipv4_network)
        log.debug(self.ipv4_netmask)

        # local variables
        self.tunIf = self._createTunIf()
        if self.tunIf:
            self.tunReadThread = self._createTunReadThread()
        else:
            self.tunReadThread = None

        # f-interop related part

        self.connection = rmq_connection
        self.producer = self.connection.Producer(serializer='json')
        self.exchange = Exchange(exchange, type="topic", durable=False)

    # ======================== public ==========================================

    # def close(self):

    #     if self.tunReadThread:

    #         self.tunReadThread.close()

    #         # Send a packet to openTun interface to break out of blocking read.
    #         attempts = 0
    #         while self.tunReadThread.isAlive() and attempts < 3:
    #             attempts += 1
    #             try:
    #                 log.info('Sending UDP packet to close openTun')
    #                 sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    #                 # Destination must route through the TUN host, but not be the host itself.
    #                 # OK if host does not really exist.
    #                 dst = self.ipv6_prefix + self.ipv6_host
    #                 dst[15] += 1
    #                 # Payload and destination port are arbitrary
    #                 sock.sendto('stop', (formatIPv6Addr(dst),18004))
    #                 # Give thread some time to exit
    #                 time.sleep(0.05)
    #             except Exception as err:
    #                 log.error('Unable to send UDP to close tunReadThread: {0}'.join(err))


    # ======================== private =========================================

    def _getNetworkPrefix_notif(self, sender, signal, data):
        return self.ipv6_prefix

    def _v6ToInternet_notif(self, sender, signal, data):
        """
        Called when receiving data from the EventBus.

        This function forwards the data to the the TUN interface.
        Read from tun interface and forward to 6lowPAN
        """

        # abort if not tun interface
        if not self.tunIf:
            return

        # add tun header
        data = VIRTUALTUNID + data

        # convert data to string
        data = ''.join([chr(b) for b in data])

        try:
            # write over tuntap interface
            os.write(self.tunIf, data)
            if log.isEnabledFor(logging.DEBUG):
                log.debug("data dispatched to tun correctly {0}, {1}".format(signal, sender))
        except Exception as err:
            errMsg = formatCriticalMessage(err)
            log.critical(errMsg)

    def _createTunIf(self):
        """
        Open a TUN/TAP interface and switch it to TUN mode.

        :returns: The handler of the interface, which can be used for later
            read/write operations.
        """

        try:
            # =====
            log.info("opening tun interface")
            returnVal = os.open("/dev/net/tun", os.O_RDWR)
            ifs = ioctl(returnVal, TUNSETIFF, struct.pack("16sH", "tun%d", IFF_TUN))
            ifname = ifs[:16].strip("\x00")

            # =====
            log.info("configuring IPv6 address...")
            # ipv6_prefixStr = formatIPv6Addr(self.ipv6_prefix)
            # ipv6_hostStr = formatIPv6Addr(self.ipv6_host)

            v = os.system('ip tuntap add dev ' + ifname + ' mode tun user root')
            v = os.system('ip link set ' + ifname + ' up')
            v = os.system('ip -6 addr add ' + self.ipv6_prefix + ':' + self.ipv6_host + '/64 dev ' + ifname)
            v = os.system('ip -6 addr add fe80:' + self.ipv6_host + '/64 dev ' + ifname)

            # v = os.system("ip addr add " + self.ipv4_host + "/24 dev " + ifname)

            # =====
            log.info("adding static route route...")
            # added 'metric 1' for router-compatibility constraint
            # (show ping packet on wireshark but don't send to mote at all)

            # TODO: fix hard-coded value

            # os.system('ip -6 route add ' + ipv6_prefixStr + ':1415:9200::/96 dev ' + ifname + ' metric 1')
            os.system('ip -6 route add ' + self.ipv6_prefix + ':1415:9200::/96 dev ' + ifname + ' metric 1')
            # trying to set a gateway for this route
            # os.system('ip -6 route add ' + ipv6_prefixStr + '::/64 via ' + IPv6Prefix + ':' + ipv6_hostStr + '/64')

            # =====
            log.info("enabling IPv6 forwarding...")
            os.system('echo 1 > /proc/sys/net/ipv6/conf/all/forwarding')

            # =====
            log.info('\ncreated following virtual interface:')
            os.system('ip addr show ' + ifname)

            # =====start radvd
            # os.system('radvd start')

        except IOError as err:
            # happens when not root
            log.error('WARNING: could not created tun interface. Are you root? ({0})'.format(err))
            returnVal = None

        return returnVal

    def _createTunReadThread(self):
        """
        Creates and starts the thread to read messages arriving from the
        TUN interface.
        """
        return TunReadThread(
            self.tunIf,
            self._v6ToMesh_notif
        )

    def _v6ToMesh_notif(self, data):
        """
        Called when receiving data from the TUN interface.

        This function forwards the data to the the EventBus.
        Read from 6lowPAN and forward to tun interface
        """
        routing_key = "data.fromAgent.{name}".format(name=self.name)
        log.debug("This is my routing key: %s" % routing_key)
        # dispatch to EventBus
        msg = json.dumps({
            "msg_id": str(uuid.uuid1()),
            "timestamp": str(time.time()),
            "routing_key": routing_key,
            "data": data
        })
        log.debug(msg)
        self.producer.publish(msg,
                              exchange=self.exchange,
                              routing_key=routing_key)


class OpenTunMACOS(object):
    '''
    Class which interfaces between a TUN virtual interface and an EventBus.
    '''

    def __init__(self, name, rmq_connection, exchange="default",
                 ipv6_prefix=None, ipv6_host=None,
                 ipv4_host=None, ipv4_network=None, ipv4_netmask=None):
        # log
        log.info("create instance")

        self.name = name

        if ipv6_prefix is None:
            # self.ipv6_prefix = [0xbb, 0xbb, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
            ipv6_prefix = DEFAULT_IPV6_PREFIX

        self.ipv6_prefix = ipv6_prefix

        if ipv6_host is None:
            # self.ipv6_host = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01]
            ipv6_host = ":1"

        self.ipv6_host = ipv6_host

        if ipv4_host is None:
            ipv4_host = "2.2.2.2"

        self.ipv4_host = ipv4_host

        if ipv4_network is None:
            ipv4_network = [10, 2, 0, 0]
        self.ipv4_network = ipv4_network

        if ipv4_netmask is None:
            ipv4_netmask = [255, 255, 0, 0]
        self.ipv4_netmask = ipv4_netmask

        log.debug("IP info")
        log.debug(self.ipv6_prefix)
        log.debug(self.ipv6_host)
        log.debug(self.ipv4_host)
        log.debug(self.ipv4_network)
        log.debug(self.ipv4_netmask)

        # local variables
        self.tunIf = self._createTunIf()
        if self.tunIf:
            self.tunReadThread = self._createTunReadThread()
        else:
            self.tunReadThread = None

        # f-interop related part

        self.connection = rmq_connection
        self.producer = self.connection.Producer(serializer='json')
        self.exchange = Exchange(exchange, type="topic", durable=False)

    #======================== public ==========================================

    #======================== private =========================================

    def _getNetworkPrefix_notif(self, sender, signal, data):
        return self.ipv6_prefix

    def _v6ToInternet_notif(self, sender, signal, data):
        """
        Called when receiving data from the EventBus.

        This function forwards the data to the the TUN interface.
        """

        # abort if not tun interface
        if not self.tunIf:
            return

        # add tun header
        data = VIRTUALTUNID + data

        # convert data to string
        data = ''.join([chr(b) for b in data])

        try:
            # write over tuntap interface
            os.write(self.tunIf, data)
            if log.isEnabledFor(logging.DEBUG):
                log.debug("data dispatched to tun correctly {0}, {1}".format(signal, sender))
        except Exception as err:
            errMsg = formatCriticalMessage(err)
            log.critical(errMsg)

    def _createTunIf(self):
        '''
        Open a TUN/TAP interface and switch it to TUN mode.

        :returns: The handler of the interface, which can be used for later
            read/write operations.
        '''
        #=====
        log.info("opening tun interface")
        tun_counter=0
        while tun_counter<16:
            try:
                import os
                ifname='tun{0}'.format(tun_counter)
                f=os.open("/dev/{0}".format(ifname), os.O_RDWR)
                break
            except OSError:
                tun_counter+=1

        if tun_counter==16:
            raise OSError('TUN device not found: check if it exists or if it is busy. TunTap driver installed on MacOs?')
        else:
        #=====
            log.info("configuring IPv6 address...")
            # prefixStr = u.formatIPv6Addr(openTun.IPV6PREFIX)
            # hostStr   = u.formatIPv6Addr(openTun.IPV6HOST)

            # v=os.system('ifconfig {0} inet6 {1}:{2} prefixlen 64'.format(ifname, self.prefixStr, hostStr))
            # v=os.system('ifconfig {0} inet6 fe80::{1} prefixlen 64 add'.format(ifname, hostStr))

            v=os.system('ifconfig {0} inet6 {1}:{2} prefixlen 64'.format(ifname, self.ipv6_prefix, self.ipv6_host))
            v=os.system('ifconfig {0} inet6 fe80::{1} prefixlen 64 add'.format(ifname, self.ipv6_host))


        #=====
            log.info("adding static route route...")
            # added 'metric 1' for router-compatibility constraint
            # (show ping packet on wireshark but don't send to mote at all)
            # os.system('ip -6 route add ' + prefixStr + ':1415:9200::/96 dev ' + ifname + ' metric 1')
            os.system('route add -inet6 {0}:1415:9200::/96 -interface {1}'.format(self.ipv6_host, ifname))
            # trying to set a gateway for this route
            #os.system('ip -6 route add ' + prefixStr + '::/64 via ' + IPv6Prefix + ':' + hostStr + '/64')

        #=====
            log.info("enabling IPv6 forwarding...")
            # os.system('echo 1 > /proc/sys/net/ipv6/conf/all/forwarding')
            os.system('sysctl -w net.inet6.ip6.forwarding=1')

        #=====
            print('\ncreated following virtual interface:')
            os.system('ifconfig {0}'.format(ifname))

        #=====start radvd
            #os.system('radvd start')

            return f

    def _createTunReadThread(self):
        '''
        Creates and starts the thread to read messages arriving from the
        TUN interface.
        '''
        return TunReadThread(
            self.tunIf,
            self._v6ToMesh_notif
        )

    def _v6ToMesh_notif(self, data):
        """
        Called when receiving data from the TUN interface.

        This function forwards the data to the the EventBus.
        """
        routing_key = "data.fromAgent.{name}".format(name=self.name)
        log.debug("This is my routing key: %s" % routing_key)
        # dispatch to EventBus
        msg = json.dumps({
            "msg_id": str(uuid.uuid1()),
            "timestamp": str(time.time()),
            "routing_key": routing_key,
            "data": data
        })
        log.debug(msg)
        self.producer.publish(msg,
                              exchange=self.exchange,
                              routing_key=routing_key)

    #======================== helpers =========================================