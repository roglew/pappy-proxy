import comm
import subprocess
import os

def start_editor(reqid):
    script_loc = os.path.join(os.path.dirname(__file__), "vim_repeater", "repeater.vim")
    #print "RepeaterSetup %d %d"%(reqid, comm_port)
    subprocess.call(["vim", "-S", script_loc, "-c", "RepeaterSetup %d %d"%(reqid, comm.comm_port)])
