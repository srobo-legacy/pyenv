
import json
import os
import subprocess
from subprocess import Popen
import tempfile
import time

class Squidge(object):
    "Object for managing the squidge GUI"

    def __init__(self, log_fname):
        
        self.mode_file = tempfile.mktemp()

        self.proc = Popen( ["squidge", log_fname, self.mode_file],
                           stdin=subprocess.PIPE)

    def signal_start(self):
        "Signal to squidge that code is to be run"
        self.proc.stdin.write("\n")

        return self._get_mode()

    def _get_mode(self):
        "Get the match mode information from the GUI"

        while not os.path.exists( self.mode_file ):
            time.sleep(0.1)

        info = json.load( open( self.mode_file, "r" ) )
        return info
