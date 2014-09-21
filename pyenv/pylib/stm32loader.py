#!/usr/bin/env python

# -*- coding: utf-8 -*-
# vim: sw=4:ts=4:si:et:enc=utf-8

# Author: Ivan A-R <ivan@tuxotronic.org>
# Project page: http://tuxotronic.org/wiki/projects/stm32loader
#
# This file is part of stm32loader.
#
# stm32loader is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 3, or (at your option) any later
# version.
#
# stm32loader is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with stm32loader; see the file COPYING3.  If not see
# <http://www.gnu.org/licenses/>.

import sys, getopt
import serial
import time

# Verbose level
QUIET = -1

def mdebug(level, message):
    if(QUIET >= level):
        print >> sys.stderr , message


class CmdException(Exception):
    pass

class CommandInterface:
    def __init__(self, port='/dev/ttyUSB1', baudrate=115200, prog_cb = None):

        def null_prog_cb(mode, prog):
            pass

        if prog_cb is None:
            self.prog_cb = null_prog_cb
        else:
            self.prog_cb = prog_cb
        self.sp = serial.Serial(
            port=port,
            baudrate=baudrate,     # baudrate
            bytesize=8,             # number of databits
            parity=serial.PARITY_EVEN,
            stopbits=1,
            xonxoff=0,              # enable software flow control
            rtscts=0,               # disable RTS/CTS flow control
            timeout=5               # set a timeout value, None for waiting forever
        )


    def _wait_for_ask(self, info = ""):
        # wait for ask
        try:
            ask = ord(self.sp.read())
        except:
            raise CmdException("Can't read port or timeout")
        else:
            if ask == 0x79:
                # ACK
                return 1
            else:
                if ask == 0x1F:
                    # NACK
                    raise CmdException("NACK "+info)
                else:
                    # Unknow responce
                    raise CmdException("Unknow response. "+info+": "+hex(ask))


    def reset(self):
        self.sp.setDTR(0)
        time.sleep(0.1)
        self.sp.setDTR(1)
        time.sleep(0.5)

    def initChip(self):
        # Set boot
        self.sp.setRTS(0)
        self.reset()

        self.sp.write("\x7F")       # Syncro
        return self._wait_for_ask("Syncro")

    def releaseChip(self):
        self.sp.setRTS(1)
        self.reset()

    def cmdGeneric(self, cmd):
        self.sp.write(chr(cmd))
        self.sp.write(chr(cmd ^ 0xFF)) # Control byte
        return self._wait_for_ask(hex(cmd))

    def cmdGet(self):
        if self.cmdGeneric(0x00):
            mdebug(10, "*** Get command");
            len = ord(self.sp.read())
            version = ord(self.sp.read())
            mdebug(10, "    Bootloader version: "+hex(version))
            dat = map(lambda c: hex(ord(c)), self.sp.read(len))
            mdebug(10, "    Available commands: "+str(dat))
            self._wait_for_ask("0x00 end")
            return version
        else:
            raise CmdException("Get (0x00) failed")

    def cmdGetVersion(self):
        if self.cmdGeneric(0x01):
            mdebug(10, "*** GetVersion command")
            version = ord(self.sp.read())
            self.sp.read(2)
            self._wait_for_ask("0x01 end")
            mdebug(10, "    Bootloader version: "+hex(version))
            return version
        else:
            raise CmdException("GetVersion (0x01) failed")

    def cmdGetID(self):
        if self.cmdGeneric(0x02):
            mdebug(10, "*** GetID command")
            len = ord(self.sp.read())
            id = self.sp.read(len+1)
            self._wait_for_ask("0x02 end")
            return id
        else:
            raise CmdException("GetID (0x02) failed")


    def _encode_addr(self, addr):
        byte3 = (addr >> 0) & 0xFF
        byte2 = (addr >> 8) & 0xFF
        byte1 = (addr >> 16) & 0xFF
        byte0 = (addr >> 24) & 0xFF
        crc = byte0 ^ byte1 ^ byte2 ^ byte3
        return (chr(byte0) + chr(byte1) + chr(byte2) + chr(byte3) + chr(crc))


    def cmdReadMemory(self, addr, lng):
        assert(lng <= 256)
        if self.cmdGeneric(0x11):
            mdebug(10, "*** ReadMemory command")
            self.sp.write(self._encode_addr(addr))
            self._wait_for_ask("0x11 address failed")
            N = (lng - 1) & 0xFF
            crc = N ^ 0xFF
            self.sp.write(chr(N) + chr(crc))
            self._wait_for_ask("0x11 length failed")
            return map(lambda c: ord(c), self.sp.read(lng))
        else:
            raise CmdException("ReadMemory (0x11) failed")


    def cmdGo(self, addr):
        if self.cmdGeneric(0x21):
            mdebug(10, "*** Go command")
            self.sp.write(self._encode_addr(addr))
            self._wait_for_ask("0x21 go failed")
        else:
            raise CmdException("Go (0x21) failed")


    def cmdWriteMemory(self, addr, data):
        assert(len(data) <= 256)
        if self.cmdGeneric(0x31):
            mdebug(10, "*** Write memory command")
            self.sp.write(self._encode_addr(addr))
            self._wait_for_ask("0x31 address failed")
            #map(lambda c: hex(ord(c)), data)
            lng = (len(data)-1) & 0xFF
            mdebug(10, "    %s bytes to write" % [lng+1]);
            self.sp.write(chr(lng)) # len really
            crc = lng
            for c in data:
                crc = crc ^ c
                self.sp.write(chr(c))
            self.sp.write(chr(crc))
            self._wait_for_ask("0x31 programming failed")
            mdebug(10, "    Write memory done")
        else:
            raise CmdException("Write memory (0x31) failed")


    def cmdEraseMemory(self, sectors = None):
        if self.cmdGeneric(0x43):
            mdebug(10, "*** Erase memory command")
            if sectors is None:
                # Global erase
                self.sp.write(chr(0xFF))
                self.sp.write(chr(0x00))
            else:
                # Sectors erase
                self.sp.write(chr((len(sectors)-1) & 0xFF))
                crc = 0xFF
                for c in sectors:
                    crc = crc ^ c
                    self.sp.write(chr(c))
                self.sp.write(chr(crc))
            self._wait_for_ask("0x43 erasing failed")
            mdebug(10, "    Erase memory done")
        else:
            raise CmdException("Erase memory (0x43) failed")

    def cmdWriteProtect(self, sectors):
        if self.cmdGeneric(0x63):
            mdebug(10, "*** Write protect command")
            self.sp.write(chr((len(sectors)-1) & 0xFF))
            crc = 0xFF
            for c in sectors:
                crc = crc ^ c
                self.sp.write(chr(c))
            self.sp.write(chr(crc))
            self._wait_for_ask("0x63 write protect failed")
            mdebug(10, "    Write protect done")
        else:
            raise CmdException("Write Protect memory (0x63) failed")

    def cmdWriteUnprotect(self):
        if self.cmdGeneric(0x73):
            mdebug(10, "*** Write Unprotect command")
            self._wait_for_ask("0x73 write unprotect failed")
            self._wait_for_ask("0x73 write unprotect 2 failed")
            mdebug(10, "    Write Unprotect done")
        else:
            raise CmdException("Write Unprotect (0x73) failed")

    def cmdReadoutProtect(self):
        if self.cmdGeneric(0x82):
            mdebug(10, "*** Readout protect command")
            self._wait_for_ask("0x82 readout protect failed")
            self._wait_for_ask("0x82 readout protect 2 failed")
            mdebug(10, "    Read protect done")
        else:
            raise CmdException("Readout protect (0x82) failed")

    def cmdReadoutUnprotect(self):
        if self.cmdGeneric(0x92):
            mdebug(10, "*** Readout Unprotect command")
            self._wait_for_ask("0x92 readout unprotect failed")
            self._wait_for_ask("0x92 readout unprotect 2 failed")
            mdebug(10, "    Read Unprotect done")
        else:
            raise CmdException("Readout unprotect (0x92) failed")


# Complex commands section

    def readMemory(self, addr, lng):
        data = []
        dlen = lng

        while lng > 256:
            self.prog_cb( "READ", (dlen - lng)/float(dlen) )

            mdebug(5, "Read %(len)d bytes at 0x%(addr)X" % {'addr': addr, 'len': 256})
            data = data + self.cmdReadMemory(addr, 256)
            addr = addr + 256
            lng = lng - 256

        mdebug(5, "Read %(len)d bytes at 0x%(addr)X" % {'addr': addr, 'len': 256})
        data = data + self.cmdReadMemory(addr, lng)
        self.prog_cb( "READ", 1.0 )
        return data

    def writeMemory(self, addr, data, padding = True):
        lng = len(data)
        offs = 0
        while lng > 256:
            mdebug(5, "Write %(len)d bytes at 0x%(addr)X" % {'addr': addr, 'len': 256})
            self.prog_cb( "WRITE", offs/float(len(data)))
            self.cmdWriteMemory(addr, data[offs:offs+256])
            offs = offs + 256
            addr = addr + 256
            lng = lng - 256
        mdebug(5, "Write %(len)d bytes at 0x%(addr)X" % {'addr': addr, 'len': 256})

        if padding:
            self.cmdWriteMemory(addr, data[offs:offs+lng] + ([0xFF] * (256-lng)) )
        else:
            self.cmdWriteMemory(addr, data[offs:offs+lng])

def usage():
    print """Usage: %s [-hqVewvr] [-l length] [-p port] [-b baud] [-a addr] [file.bin]
    -h          This help
    -q          Quiet
    -V          Verbose
    -e          Erase
    -w          Write
    -v          Verify
    -r          Read
    -l length   Length of read
    -p port     Serial port (default: /dev/tty.usbserial-ftCYPMYJ)
    -b baud     Baud speed (default: 115200)
    -a addr     Target address

    ./stm32loader.py -e -w -v example/main.bin

    """ % sys.argv[0]

def prog_cb(mode, prog):
    print mode, prog

if __name__ == "__main__":

    # Import Psyco if available
    try:
        import psyco
        psyco.full()
        print "Using Psyco..."
    except ImportError:
        pass

    conf = {
            'port': '/dev/tty.usbserial-ftCYPMYJ',
            'baud': 115200,
            'address': 0x08000000,
            'erase': 0,
            'write': 0,
            'verify': 0,
            'read': 0,
        }

# http://www.python.org/doc/2.5.2/lib/module-getopt.html

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hqVewvrp:b:a:l:")
    except getopt.GetoptError, err:
        # print help information and exit:
        print str(err) # will print something like "option -a not recognized"
        usage()
        sys.exit(2)

    QUIET = 5

    for o, a in opts:
        if o == '-V':
            QUIET = 10
        elif o == '-q':
            QUIET = 0
        elif o == '-h':
            usage()
            sys.exit(0)
        elif o == '-e':
            conf['erase'] = 1
        elif o == '-w':
            conf['write'] = 1
        elif o == '-v':
            conf['verify'] = 1
        elif o == '-r':
            conf['read'] = 1
        elif o == '-p':
            conf['port'] = a
        elif o == '-b':
            conf['baud'] = eval(a)
        elif o == '-a':
            conf['address'] = eval(a)
        elif o == '-l':
            conf['len'] = eval(a)
        else:
            assert False, "unhandled option"

    cmd = CommandInterface(conf['port'], conf['baud'], prog_cb = prog_cb)
    mdebug(10, "Open port %(port)s, baud %(baud)d" % {'port':conf['port'], 'baud':conf['baud']})
    try:
        try:
            cmd.initChip()
        except:
            print "Can't init. Ensure that BOOT0 is enabled and reset device"


        bootversion = cmd.cmdGet()
        mdebug(0, "Bootloader version %X" % bootversion)
        mdebug(0, "Chip id `%s'" % str(map(lambda c: hex(ord(c)), cmd.cmdGetID())))
#    cmd.cmdGetVersion()
#    cmd.cmdGetID()
#    cmd.cmdReadoutUnprotect()
#    cmd.cmdWriteUnprotect()
#    cmd.cmdWriteProtect([0, 1])

        if (conf['write'] or conf['verify']):
            data = map(lambda c: ord(c), file(args[0], 'rb').read())

        if conf['erase']:
            cmd.cmdEraseMemory()

        if conf['write']:
            cmd.writeMemory(conf['address'], data)

        if conf['verify']:
            verify = cmd.readMemory(conf['address'], len(data))
            if(data == verify):
                print "Verification OK"
            else:
                print "Verification FAILED"
                print str(len(data)) + ' vs ' + str(len(verify))
                for i in xrange(0, len(data)):
                    if data[i] != verify[i]:
                        print hex(i) + ': ' + hex(data[i]) + ' vs ' + hex(verify[i])

        if not conf['write'] and conf['read']:
            rdata = cmd.readMemory(conf['address'], conf['len'])
            file(args[0], 'wb').write(''.join(map(chr,rdata)))

#    cmd.cmdGo(addr + 0x04)
    finally:
        cmd.releaseChip()

