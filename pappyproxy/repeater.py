import subprocess
import os

from pappyproxy import comm

def start_editor(reqid):
    script_loc = os.path.join(os.path.dirname(__file__), "vim_repeater", "repeater.vim")
    #print "RepeaterSetup %d %d"%(reqid, comm_port)
    subprocess.call(["vim", "-S", script_loc, "-c", "RepeaterSetup %s %d"%(reqid, comm.comm_port)])
