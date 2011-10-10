# Copyright Robert Spanton 2011
import json, sys, optparse, time, os
import pysric, threading

class SricCtxMan(object):
    """Class for storing/managing one sric context per thread"""
    def __init__(self):
        self.store = threading.local()

    def get(self):
        "Return a pysric context for use in this thread"
        if "ctx" not in self.store.__dict__:
            self.store.ctx = pysric.PySric()

        return self.store.ctx

    def get_addr(self, addr):
        "Return the SricDevice instance for the given address for this thread"

        if "addr" not in self.store.__dict__:
            "Construct a dictionary of the available addresses"
            self.store.addr = {}
            ps = self.get()

            for devs in ps.devices.values():
                for dev in devs:
                    assert dev.address not in dev
                    self.store.addr[dev.address] = dev

        return self.store.addr[addr]

class Robot(object):
    """Class for initialising and accessing robot hardware"""

    def __init__(self):
        self.sricman = SricCtxMan()

        self._dump_bus()
        self._parse_cmdline()
        self._wait_start()

    def _dump_bus(self):
        "Write the contents of the SRIC bus out to stdout"
        print "Found the following devices:"
        ps = self.sricman.get()
        for devclass in ps.devices:
            if devclass in [ pysric.SRIC_CLASS_POWER, pysric.SRIC_CLASS_MOTOR,
                             pysric.SRIC_CLASS_JOINTIO, pysric.SRIC_CLASS_SERVO ]:
                for dev in ps.devices[devclass]:
                    print dev

    def _parse_cmdline(self):
        "Parse the command line arguments"
        parser = optparse.OptionParser()

        parser.add_option( "--usbkey", type="string", dest="usbkey",
                           help="The path of the (non-volatile) user USB key" )

        parser.add_option( "--startfifo", type="string", dest="startfifo",
                           help="The path of the fifo which start information will be received through" )
        (options, args) = parser.parse_args()

        self.usbkey = options.usbkey
        self.startfifo = options.startfifo

    def _wait_start(self):
        "Wait for the start signal to happen"

        os.mkfifo( self.startfifo )
        f = open( self.startfifo, "r" )
        d = f.read()
        f.close()

        j = json.loads(d)

        if "zone" not in j or "mode" not in j:
            raise Exception( "'zone' and 'mode' must be in startup info" )

        self.mode = j["mode"]
        self.zone = j["zone"]

        if self.mode not in ["comp", "dev"]:
            raise Exception( "mode of '%s' is not supported -- must be 'comp' or 'dev'" % self.mode )
        if self.zone < 0 or self.zone > 3:
            raise Exception( "zone must be in range 0-3 inclusive -- value of %i is invalid" % self.zone )

