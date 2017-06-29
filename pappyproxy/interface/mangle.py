import curses
import os
import subprocess
import tempfile
import threading
from ..macros import InterceptMacro
from ..proxy import MessageError, parse_request, parse_response
from ..colors import url_formatter

edit_queue = []

class InterceptorMacro(InterceptMacro):
    """
    A class representing a macro that modifies requests as they pass through the
    proxy
    """
    def __init__(self):
        InterceptMacro.__init__(self)
        self.name = "InterceptorMacro"

    def mangle_request(self, request):
        # This function gets called to mangle/edit requests passed through the proxy

        # Write original request to the temp file
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tfName = tf.name
            tf.write(request.full_message())

        mangled_req = request
        front = False
        while True:
            # Have the console edit the file
            event = edit_file(tfName, front=front)
            event.wait()
            if event.canceled:
                return request

            # Create new mangled request from edited file
            with open(tfName, 'rb') as f:
                text = f.read()

            os.remove(tfName)

            # Check if dropped
            if text == '':
                return None

            try:
                mangled_req = parse_request(text)
            except MessageError as e:
                print("could not parse request: %s" % str(e))
                front = True
                continue
            mangled_req.dest_host = request.dest_host
            mangled_req.dest_port = request.dest_port
            mangled_req.use_tls = request.use_tls
            break
        return mangled_req

    def mangle_response(self, request, response):
        # This function gets called to mangle/edit respones passed through the proxy

        # Write original response to the temp file
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tfName = tf.name
            tf.write(response.full_message())

        mangled_rsp = response
        while True:
            # Have the console edit the file
            event = edit_file(tfName, front=True)
            event.wait()
            if event.canceled:
                return response

            # Create new mangled response from edited file
            with open(tfName, 'rb') as f:
                text = f.read()

            os.remove(tfName)

            # Check if dropped
            if text == '':
                return None

            try:
                mangled_rsp = parse_response(text)
            except MessageError as e:
                print("could not parse response: %s" % str(e))
                front = True
                continue
            break
        return mangled_rsp

    def mangle_websocket(self, request, response, message):
        # This function gets called to mangle/edit respones passed through the proxy

        # Write original response to the temp file
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tfName = tf.name
            tf.write(b"# ")
            if message.to_server:
                tf.write(b"OUTGOING to")
            else:
                tf.write(b"INCOMING from")
            desturl = 'ws' + url_formatter(request)[4:] # replace http:// with ws://
            tf.write(b' ' + desturl.encode())
            tf.write(b" -- Note that this line is ignored\n")
            tf.write(message.message)

        mangled_msg = message
        while True:
            # Have the console edit the file
            event = edit_file(tfName, front=True)
            event.wait()
            if event.canceled:
                return message

            # Create new mangled response from edited file
            with open(tfName, 'rb') as f:
                text = f.read()
            _, text = text.split(b'\n', 1)

            os.remove(tfName)

            # Check if dropped
            if text == '':
                return None

            mangled_msg.message = text
            # if messages can be invalid, check for it here and continue if invalid
            break
        return mangled_msg

    
class EditEvent:
    
    def __init__(self):
        self.e = threading.Event()
        self.canceled = False
        
    def wait(self):
        self.e.wait()
        
    def set(self):
        self.e.set()
        
    def cancel(self):
        self.canceled = True
        self.set()

###############
## Helper funcs

def edit_file(fname, front=False):
    global edit_queue
    # Adds the filename to the edit queue. Returns an event that is set once
    # the file is edited and the editor is closed
    #e = threading.Event()
    e = EditEvent()
    if front:
        edit_queue = [(fname, e, threading.current_thread())] + edit_queue
    else:
        edit_queue.append((fname, e, threading.current_thread()))
    return e

def execute_repeater(client, reqid):
    #script_loc = os.path.join(pappy.session.config.pappy_dir, "plugins", "vim_repeater", "repeater.vim")
    maddr = client.maddr
    if maddr is None:
        print("Client has no message address, cannot run repeater")
        return
    storage, reqid = client.parse_reqid(reqid)
    script_loc = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                              "repeater", "repeater.vim")
    args = (["vim", "-S", script_loc, "-c", "RepeaterSetup %s %s %s"%(reqid, storage.storage_id, client.maddr)])
    subprocess.call(args)

class CloudToButt(InterceptMacro):
    
    def __init__(self):
        InterceptMacro.__init__(self)
        self.name = 'cloudtobutt'
        self.intercept_requests = True
        self.intercept_responses = True
        self.intercept_ws = True

    def mangle_response(self, request, response):
        response.body = response.body.replace(b"cloud", b"butt")
        response.body = response.body.replace(b"Cloud", b"Butt")
        return response
    
    def mangle_request(self, request):
        request.body = request.body.replace(b"foo", b"bar")
        request.body = request.body.replace(b"Foo", b"Bar")
        return request

    def mangle_websocket(self, request, response, wsm):
        wsm.message = wsm.message.replace(b"world", b"zawarudo")
        wsm.message = wsm.message.replace(b"zawarudo", b"ZAWARUDO")
        return wsm

def repeater(client, args):
    """
    Open a request in the repeater
    Usage: repeater <reqid>
    """
    # This is not async on purpose. start_editor acts up if this is called
    # with inline callbacks. As a result, check_reqid and get_unmangled
    # cannot be async
    reqid = args[0]
    req = client.req_by_id(reqid)
    execute_repeater(client, reqid)

def intercept(client, args):
    """
    Intercept requests and/or responses and edit them with before passing them along
    Usage: intercept <reqid>
    """
    global edit_queue

    req_names = ('req', 'request', 'requests')
    rsp_names = ('rsp', 'response', 'responses')
    ws_names = ('ws', 'websocket')

    mangle_macro = InterceptorMacro()
    if any(a in req_names for a in args):
        mangle_macro.intercept_requests = True
    if any(a in rsp_names for a in args):
        mangle_macro.intercept_responses = True
    if any(a in ws_names for a in args):
        mangle_macro.intercept_ws = True
    if not args:
        mangle_macro.intercept_requests = True

    intercepting = []
    if mangle_macro.intercept_requests:
        intercepting.append('Requests')
    if mangle_macro.intercept_responses:
        intercepting.append('Responses')
    if mangle_macro.intercept_ws:
        intercepting.append('Websocket Messages')
    if not mangle_macro.intercept_requests and not mangle_macro.intercept_responses and not mangle_macro.intercept_ws:
        intercept_str = 'NOTHING WHY ARE YOU DOING THIS' # WHYYYYYYYY
    else:
        intercept_str = ', '.join(intercepting)

        ## Interceptor loop
        stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        stdscr.nodelay(True)

        conn = client.new_conn()
        try:
            conn.intercept(mangle_macro)
            editnext = False
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
                    return
                elif c == ord('n'):
                    editnext = True
                elif c == ord('b'):
                    editnext = False

                if editnext and edit_queue:
                    editnext = False
                    (to_edit, event, t) = edit_queue.pop(0)
                    editor = 'vi'
                    if 'EDITOR' in os.environ:
                        editor = os.environ['EDITOR']
                    additional_args = []
                    if editor == 'vim':
                        # prevent adding additional newline
                        additional_args.append('-b')
                    subprocess.call([editor, to_edit] + additional_args)
                    stdscr.clear()
                    event.set()
                    t.join()
        finally:
            conn.close()
            # Now that the connection is closed, make sure the rest of the threads finish/error out
            while len(edit_queue) > 0:
                (fname, event, t) = edit_queue.pop(0)
                event.cancel()
                t.join()
            curses.nocbreak()
            stdscr.keypad(0)
            curses.echo()
            curses.endwin()

###############
## Plugin hooks

def test_macro(client, args):
    c2b = CloudToButt()
    conn = client.new_conn()
    with client.new_conn() as conn:
        conn.intercept(c2b)
        print("intercept started")
        input("Press enter to quit...")
        print("past raw input")

def load_cmds(cmd):
    cmd.set_cmds({
        'intercept': (intercept, None),
        'c2b': (test_macro, None),
        'repeater': (repeater, None),
    })
    cmd.add_aliases([
        ('intercept', 'ic'),
        ('repeater', 'rp'),
    ])

