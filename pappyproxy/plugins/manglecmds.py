import crochet
import curses
import os
import pappyproxy
import shlex
import subprocess
import tempfile

from pappyproxy.util import PappyException
from pappyproxy.macros import InterceptMacro
from pappyproxy.http import Request, Response
from pappyproxy.plugin import add_intercepting_macro, remove_intercepting_macro
from pappyproxy import pappy
from twisted.internet import defer

PLUGIN_ID="manglecmds"

edit_queue = []

class MangleInterceptMacro(InterceptMacro):
    """
    A class representing a macro that modifies requests as they pass through the
    proxy
    """
    def __init__(self):
        InterceptMacro.__init__(self)
        self.name = 'Pappy Interceptor Macro'
        self.intercept_requests = False
        self.intercept_responses = False
        self.intercept_ws = False
        self.async_req = True
        self.async_rsp = True
        self.async_ws = True

    def __repr__(self):
        return "<MangleInterceptingMacro>"

    @defer.inlineCallbacks
    def async_mangle_request(self, request):
        # This function gets called to mangle/edit requests passed through the proxy

        retreq = request
        # Write original request to the temp file
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tfName = tf.name
            tf.write(request.full_request)

        # Have the console edit the file
        yield edit_file(tfName)

        # Create new mangled request from edited file
        with open(tfName, 'r') as f:
            text = f.read()

        os.remove(tfName)

        # Check if dropped
        if text == '':
            pappyproxy.proxy.log('Request dropped!')
            defer.returnValue(None)

        mangled_req = Request(text, update_content_length=True)
        mangled_req._host = request.host
        mangled_req.port = request.port
        mangled_req.is_ssl = request.is_ssl

        # Check if it changed
        if mangled_req.full_request != request.full_request:
            retreq = mangled_req

        defer.returnValue(retreq)

    @defer.inlineCallbacks
    def async_mangle_response(self, request):
        # This function gets called to mangle/edit respones passed through the proxy

        retrsp = request.response
        # Write original response to the temp file
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tfName = tf.name
            tf.write(request.response.full_response)

        # Have the console edit the file
        yield edit_file(tfName, front=True)

        # Create new mangled response from edited file
        with open(tfName, 'r') as f:
            text = f.read()

        os.remove(tfName)

        # Check if dropped
        if text == '':
            pappyproxy.proxy.log('Response dropped!')
            defer.returnValue(None)

        mangled_rsp = Response(text, update_content_length=True)

        if mangled_rsp.full_response != request.response.full_response:
            mangled_rsp.unmangled = request.response
            retrsp = mangled_rsp

        defer.returnValue(retrsp)

    @defer.inlineCallbacks
    def async_mangle_ws(self, request, message):
        # This function gets called to mangle/edit respones passed through the proxy

        retmsg = message
        # Write original message to the temp file
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tfName = tf.name
            tf.write(retmsg.contents)

        # Have the console edit the file
        yield edit_file(tfName, front=True)

        # Create new mangled message from edited file
        with open(tfName, 'r') as f:
            text = f.read()

        os.remove(tfName)

        # Check if dropped
        if text == '':
            pappyproxy.proxy.log('Websocket message dropped!')
            defer.returnValue(None)

        mangled_message = message.copy()
        mangled_message.contents = text

        if mangled_message.contents != message.contents:
            retmsg = mangled_message

        defer.returnValue(retmsg)
            

###############
## Helper funcs

def edit_file(fname, front=False):
    global edit_queue
    # Adds the filename to the edit queue. Returns a deferred that is fired once
    # the file is edited and the editor is closed
    d = defer.Deferred()
    if front:
        edit_queue = [(fname, d)] + edit_queue
    else:
        edit_queue.append((fname, d))
    return d

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def check_reqid(reqid):
    # Used for the repeater command. Must not be async
    try:
        yield pappyproxy.http.Request.load_request(reqid)
    except:
        raise PappyException('"%s" is not a valid request id' % reqid)
    defer.returnValue(None)

def start_editor(reqid):
    script_loc = os.path.join(pappy.session.config.pappy_dir, "plugins", "vim_repeater", "repeater.vim")
    subprocess.call(["vim", "-S", script_loc, "-c", "RepeaterSetup %s %d"%(reqid, pappy.session.comm_port)])
    
####################
## Command functions

def repeater(line):
    """
    Open a request in the repeater
    Usage: repeater <reqid>
    """
    # This is not async on purpose. start_editor acts up if this is called
    # with inline callbacks. As a result, check_reqid and get_unmangled
    # cannot be async
    args = shlex.split(line)
    reqid = args[0]

    check_reqid(reqid)
    start_editor(reqid)

def intercept(line):
    """
    Intercept requests and/or responses and edit them with before passing them along
    Usage: intercept <reqid>
    """
    global edit_queue
    args = shlex.split(line)
    intercept_requests = False
    intercept_responses = False
    intercept_ws = True
    intercept_ws

    req_names = ('req', 'request', 'requests')
    rsp_names = ('rsp', 'response', 'responses')
    ws_names = ('ws', 'websocket')

    if any(a in req_names for a in args):
        intercept_requests = True
    if any(a in rsp_names for a in args):
        intercept_responses = True
    if any(a in req_names for a in args):
        intercept_ws = True
    if not args:
        intercept_requests = True

    intercepting = []
    if intercept_requests:
        intercepting.append('Requests')
    if intercept_responses:
        intercepting.append('Responses')
    if intercept_ws:
        intercepting.append('Websocket Messages')
    if not intercept_requests and not intercept_responses and not intercept_ws:
        intercept_str = 'NOTHING'
    else:
        intercept_str = ', '.join(intercepting)

    mangle_macro = MangleInterceptMacro()
    mangle_macro.intercept_requests = intercept_requests
    mangle_macro.intercept_responses = intercept_responses
    mangle_macro.intercept_ws = intercept_ws

    add_intercepting_macro('pappy_intercept', mangle_macro)

    ## Interceptor loop
    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()

    try:
        editnext = False
        stdscr.nodelay(True)
        while True:
            stdscr.addstr(0, 0, "Currently intercepting: %s" % intercept_str)
            stdscr.clrtoeol()
            stdscr.addstr(1, 0, "%d item(s) in queue." % len(edit_queue))
            stdscr.clrtoeol()
            if editnext:
                stdscr.addstr(2, 0, "Waiting for next item... Press 'q' to quit or 'b' to quit waiting")
            else:
                stdscr.addstr(2, 0, "Press 'n' to edit the next item or 'q' to quit interceptor.")
            stdscr.clrtoeol()

            c = stdscr.getch()
            if c == ord('q'):
                break
            elif c == ord('n'):
                editnext = True
            elif c == ord('b'):
                editnext = False

            if editnext and edit_queue:
                editnext = False
                (to_edit, deferred) = edit_queue.pop(0)
                editor = 'vi'
                if 'EDITOR' in os.environ:
                    editor = os.environ['EDITOR']
                additional_args = []
                if editor == 'vim':
                    # prevent adding additional newline
                    additional_args.append('-b')
                subprocess.call([editor, to_edit] + additional_args)
                stdscr.clear()
                deferred.callback(None)
    finally:
        curses.nocbreak()
        stdscr.keypad(0)
        curses.echo()
        curses.endwin()
        try:
            remove_intercepting_macro('pappy_intercept')
        except PappyException:
            pass
        # Send remaining requests along
        while len(edit_queue) > 0:
            (fname, deferred) = edit_queue.pop(0)
            deferred.callback(None)

###############
## Plugin hooks

def load_cmds(cmd):
    cmd.set_cmds({
        'intercept': (intercept, None),
        'repeater': (repeater, None),
    })
    cmd.add_aliases([
        ('intercept', 'ic'),
        ('repeater', 'rp'),
    ])
