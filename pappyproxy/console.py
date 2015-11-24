import cmd2
import crochet
import curses
import datetime
import os
import pappyproxy
import pygments
import shlex
import string
import subprocess
import sys
import termios
import time

from twisted.internet import defer, reactor
from pappyproxy.util import PappyException
from pygments.lexers import get_lexer_for_mimetype
from pygments.formatters import TerminalFormatter

"""
console.py

Functions and classes involved with interacting with console input and output
"""

# http://www.termsys.demon.co.uk/vtansi.htm#cursor
SAVE_CURSOR = '\x1b[7'
UNSAVE_CURSOR = '\x1b[8'
LINE_UP = '\x1b[1A'
LINE_ERASE = '\x1b[2K'
PRINT_LINE = '\x1b[1i'

edit_queue = []

def print_pappy_errors(func):
    def catch(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except PappyException as e:
            print str(e)
    return catch

class ProxyCmd(cmd2.Cmd):

    def __init__(self, *args, **kwargs):
        self.alerts = []
        self.prompt = 'itsPappyTime> '
        self.debug = True
        cmd2.Cmd.__init__(self, *args, **kwargs)
        
    def add_alert(self, alert):
        self.alerts.append(alert)

    def postcmd(self, stop, line):
        for l in self.alerts:
            print '[!] ', l
        self.alerts = []
        return stop

    def help_view_request_headers(self):
        print ("View information about request\n"
               "Usage: view_request_info <reqid> [u]"
               "If 'u' is given as an additional argument, the unmangled version "
               "of the request will be displayed.")

    @print_pappy_errors
    @crochet.wait_for(timeout=30.0)
    @defer.inlineCallbacks
    def do_view_request_info(self, line):
        args = shlex.split(line)
        try:
            reqid = int(args[0])
            showid = reqid
        except:
            raise PappyException("Enter a valid number for the request id")

        req = yield pappyproxy.http.Request.load_request(reqid)
        showreq = req

        show_unmangled = False
        if len(args) > 1 and args[1][0].lower() == 'u':
            if not req.unmangled:
                raise PappyException("Request was not mangled")
            show_unmangled = True
            showreq = req.unmangled

        print ''
        print_request_extended(showreq)
        print ''

    def help_view_request_headers(self):
        print ("View the headers of the request\n"
               "Usage: view_request_headers <reqid> [u]"
               "If 'u' is given as an additional argument, the unmangled version "
               "of the request will be displayed.")

    @print_pappy_errors
    @crochet.wait_for(timeout=30.0)
    @defer.inlineCallbacks
    def do_view_request_headers(self, line):
        args = shlex.split(line)
        try:
            reqid = int(args[0])
            showid = reqid
        except:
            raise PappyException("Enter a valid number for the request id")

        req = yield pappyproxy.http.Request.load_request(reqid)
        showreq = req

        show_unmangled = False
        if len(args) > 1 and args[1][0].lower() == 'u':
            if not req.unmangled:
                raise PappyException("Request was not mangled")
            show_unmangled = True
            showreq = req.unmangled

        if show_unmangled:
            print 'UNMANGLED --------------------'
        print ''
        view_full_request(showreq, True)

    def help_view_full_request(self):
        print ("View the full data of the request\n"
               "Usage: view_full_request <reqid> [u]\n"
               "If 'u' is given as an additional argument, the unmangled version "
               "of the request will be displayed.")

    @print_pappy_errors
    @crochet.wait_for(timeout=30.0)
    @defer.inlineCallbacks
    def do_view_full_request(self, line):
        args = shlex.split(line)
        try:
            reqid = int(args[0])
            showid = reqid
        except:
            raise PappyException("Enter a valid number for the request id")

        req = yield pappyproxy.http.Request.load_request(reqid)
        showreq = req

        show_unmangled = False
        if len(args) > 1 and args[1][0].lower() == 'u':
            if not req.unmangled:
                raise PappyException("Request was not mangled")
            show_unmangled = True
            showreq = req.unmangled

        if show_unmangled:
            print 'UNMANGLED --------------------'
        print ''
        view_full_request(showreq)

    def help_view_response_headers(self):
        print ("View the headers of the response\n"
               "Usage: view_response_headers <reqid>")

    @print_pappy_errors
    @crochet.wait_for(timeout=30.0)
    @defer.inlineCallbacks
    def do_view_response_headers(self, line):
        args = shlex.split(line)
        try:
            reqid = int(args[0])
            showid = reqid
        except:
            raise PappyException("Enter a valid number for the request id")

        req = yield pappyproxy.http.Request.load_request(reqid)
        showrsp = req.response

        show_unmangled = False
        if len(args) > 1 and args[1][0].lower() == 'u':
            if not req.response.unmangled:
                raise PappyException("Response was not mangled")
            show_unmangled = True
            showrsp = req.response.unmangled

        if show_unmangled:
            print ''
            print 'UNMANGLED --------------------'
        print ''
        view_full_response(showrsp, True)

    def help_view_full_response(self):
        print ("View the full data of the response associated with a request\n"
               "Usage: view_full_response <reqid>")

    @print_pappy_errors
    @crochet.wait_for(timeout=30.0)
    @defer.inlineCallbacks
    def do_view_full_response(self, line):
        args = shlex.split(line)
        try:
            reqid = int(args[0])
            showid = reqid
        except:
            raise PappyException("Enter a valid number for the request id")

        req = yield pappyproxy.http.Request.load_request(reqid)
        showrsp = req.response

        show_unmangled = False
        if len(args) > 1 and args[1][0].lower() == 'u':
            if not req.response.unmangled:
                raise PappyException("Response was not mangled")
            show_unmangled = True
            showrsp = req.response.unmangled

        if show_unmangled:
            print ''
            print 'UNMANGLED --------------------'
        print ''
        view_full_response(showrsp)

    def help_list(self):
        print ("List request/response pairs in the current context\n"
               "Usage: list")

    @print_pappy_errors
    def do_list(self, line):
        args = shlex.split(line)
        if len(args) > 0:
            if args[0][0].lower() == 'a':
                print_count = -1
            else:
                try:
                    print_count = int(args[0])
                except:
                    print "Please enter a valid argument for list"
                    return
        else:
            print_count = 25
        
        pappyproxy.context.sort()
        if print_count > 0:
            to_print = pappyproxy.context.active_requests[:]
            to_print = sorted(to_print, key=lambda x: x.reqid, reverse=True)
            to_print = to_print[:print_count]
            print_requests(to_print)
        else:
            print_requests(pappyproxy.context.active_requests)

    def help_filter(self):
        print ("Apply a filter to the current context\n"
               "Usage: filter <filter string>\n"
               "See README.md for information on filter strings")

    @print_pappy_errors
    def do_filter(self, line):
        if not line:
            raise PappyException("Filter string required")
        
        filter_to_add = pappyproxy.context.Filter(line)
        pappyproxy.context.add_filter(filter_to_add)

    def help_filter_clear(self):
        print ("Reset the context so that it contains no filters (ignores scope)\n"
               "Usage: filter_clear")

    @print_pappy_errors
    @crochet.wait_for(timeout=30.0)
    @defer.inlineCallbacks
    def do_filter_clear(self, line):
        pappyproxy.context.active_filters = []
        yield pappyproxy.context.reload_from_storage()

    def help_filter_list(self):
        print ("Print the filters that make up the current context\n"
               "Usage: filter_list")

    @print_pappy_errors
    def do_filter_list(self, line):
        for f in pappyproxy.context.active_filters:
            print f.filter_string


    def help_scope_save(self):
        print ("Set the scope to be the current context. Saved between launches\n"
               "Usage: scope_save")

    @print_pappy_errors
    @crochet.wait_for(timeout=30.0)
    @defer.inlineCallbacks
    def do_scope_save(self, line):
        pappyproxy.context.save_scope()
        yield pappyproxy.context.store_scope(pappyproxy.http.dbpool)

    def help_scope_reset(self):
        print ("Set the context to be the scope (view in-scope items)\n"
               "Usage: scope_reset")

    @print_pappy_errors
    @crochet.wait_for(timeout=30.0)
    @defer.inlineCallbacks
    def do_scope_reset(self, line):
        yield pappyproxy.context.reset_to_scope()

    def help_scope_delete(self):
        print ("Delete the scope so that it contains all request/response pairs\n"
               "Usage: scope_delete")        

    @print_pappy_errors
    @crochet.wait_for(timeout=30.0)
    @defer.inlineCallbacks
    def do_scope_delete(self, line):
        pappyproxy.context.set_scope([])
        yield pappyproxy.context.store_scope(pappyproxy.http.dbpool)

    def help_scope_list(self):
        print ("Print the filters that make up the scope\n"
               "Usage: scope_list")

    @print_pappy_errors
    def do_scope_list(self, line):
        pappyproxy.context.print_scope()

    def help_repeater(self):
        print ("Open a request in the repeater\n"
               "Usage: repeater <reqid>")

    @print_pappy_errors
    def do_repeater(self, line):
        args = shlex.split(line)
        try:
            reqid = int(args[0])
        except:
            raise PappyException("Enter a valid number for the request id")

        repid = reqid
        if len(args) > 1 and args[1][0].lower() == 'u':
            umid = get_unmangled(reqid)
            if umid is not None:
                repid = umid
        pappyproxy.repeater.start_editor(repid)

    def help_submit(self):
        print "Submit a request again (NOT IMPLEMENTED)"

    @print_pappy_errors
    @crochet.wait_for(timeout=30.0)
    @defer.inlineCallbacks
    def do_submit(self, line):
        pass
        # reqid = int(line)
        # req = yield http.Request.load_request(reqid)
        # rsp = yield req.submit()
        # print printable_data(rsp.full_response)

    def help_intercept(self):
        print ("Intercept requests and/or responses and edit them with before passing them along\n"
               "Usage: intercept <reqid>")

    @print_pappy_errors
    def do_intercept(self, line):
        global edit_queue
        args = shlex.split(line)
        intercept_requests = False
        intercept_responses = False

        req_names = ('req', 'request', 'requests')
        rsp_names = ('rsp', 'response', 'responses')

        if any(a in req_names for a in args):
            intercept_requests = True
        if any(a in rsp_names for a in args):
            intercept_responses = True

        if intercept_requests and intercept_responses:
            intercept_str = 'Requests and responses'
        elif intercept_requests:
            intercept_str = 'Requests'
        elif intercept_responses:
            intercept_str = 'Responses'
        else:
            intercept_str = 'NOTHING'

        pappyproxy.mangle.set_intercept_requests(intercept_requests)
        pappyproxy.mangle.set_intercept_responses(intercept_responses)

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
                    subprocess.call([editor, to_edit])
                    stdscr.clear()
                    deferred.callback(None)
        finally:
            curses.nocbreak()
            stdscr.keypad(0)
            curses.echo()
            curses.endwin()
            pappyproxy.mangle.set_intercept_requests(False)
            pappyproxy.mangle.set_intercept_responses(False)
            # Send remaining requests along
            while len(edit_queue) > 0:
                (fname, deferred) = edit_queue.pop(0)
                deferred.callback(None)

    def help_gencerts(self):
        print ("Generate CA cert and private CA file\n"
               "Usage: gencerts [/path/to/put/certs/in]")

    @print_pappy_errors
    def do_gencerts(self, line):
        dest_dir = line or pappyproxy.config.CERT_DIR
        print "This will overwrite any existing certs in %s. Are you sure?" % dest_dir
        print "(y/N)",
        answer = raw_input()
        if not answer or answer[0].lower() != 'y':
            return False
        print "Generating certs to %s" % dest_dir
        pappyproxy.proxy.generate_ca_certs(dest_dir)

    def help_log(self):
        print ("View the log\n"
               "Usage: log [verbosity (default is 1)]\n"
               "verbosity=1: Show connections as they're made/lost, some additional info\n"
               "verbosity=3: Show full requests/responses as they are processed by the proxy")

    @print_pappy_errors
    def do_log(self, line):
        try:
            verbosity = int(line.strip())
        except:
            verbosity = 1
        pappyproxy.config.DEBUG_VERBOSITY = verbosity
        raw_input()
        pappyproxy.config.DEBUG_VERBOSITY = 0

    @print_pappy_errors
    def do_testerror(self, line):
        raise PappyException("Test error")

    @print_pappy_errors
    def do_EOF(self):
        print "EOF"
        return True

    ### ABBREVIATIONS
    def help_ls(self):
        self.help_list()

    @print_pappy_errors
    def do_ls(self, line):
        self.onecmd('list %s' % line)

    def help_sr(self):
        self.help_scope_reset()

    @print_pappy_errors
    def do_sr(self, line):
        self.onecmd('scope_reset %s' % line)

    def help_sls(self):
        self.help_scope_list()

    @print_pappy_errors
    def do_sls(self, line):
        self.onecmd('scope_list %s' % line)

    def help_viq(self):
        self.help_view_request_info()

    @print_pappy_errors
    def do_viq(self, line):
        self.onecmd('view_request_info %s' % line)

    def help_vhq(self):
        self.help_view_request_headers()

    @print_pappy_errors
    def do_vhq(self, line):
        self.onecmd('view_request_headers %s' % line)

    def help_vfq(self):
        self.help_view_full_request()

    @print_pappy_errors
    def do_vfq(self, line):
        self.onecmd('view_full_request %s' % line)

    def help_vhs(self):
        self.help_view_response_headers()

    @print_pappy_errors
    def do_vhs(self, line):
        self.onecmd('view_response_headers %s' % line)

    def help_vfs(self):
        self.help_view_full_response()

    @print_pappy_errors
    def do_vfs(self, line):
        self.onecmd('view_full_response %s' % line)

    def help_fl(self):
        self.help_filter()

    @print_pappy_errors
    def do_fl(self, line):
        self.onecmd('filter %s' % line)

    def help_f(self):
        self.help_filter()

    @print_pappy_errors
    def do_f(self, line):
        self.onecmd('filter %s' % line)

    def help_fls(self):
        self.help_filter_list()

    @print_pappy_errors
    def do_fls(self, line):
        self.onecmd('filter_list %s' % line)

    def help_fc(self):
        self.help_filter_clear()

    @print_pappy_errors
    def do_fc(self, line):
        self.onecmd('filter_clear %s' % line)

    def help_rp(self):
        self.help_repeater()

    @print_pappy_errors
    def do_rp(self, line):
        self.onecmd('repeater %s' % line)

    def help_ic(self):
        self.help_intercept()

    @print_pappy_errors
    def do_ic(self, line):
        self.onecmd('intercept %s' % line)


    
def cmd_failure(cmd):
    print "FAILURE"

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
    
def print_table(coldata, rows):
    # Coldata: List of dicts with info on how to print the columns.
    #  name: heading to give column
    #  width: (optional) maximum width before truncating. 0 for unlimited
    # Rows: List of tuples with the data to print

    # Get the width of each column
    widths = []
    headers = []
    for data in coldata:
        if 'name' in data:
            headers.append(data['name'])
        else:
            headers.append('')
    empty_headers = True
    for h in headers:
        if h != '':
            empty_headers = False
    if not empty_headers:
        rows = [headers] + rows

    for i in range(len(coldata)):
        col = coldata[i]
        if 'width' in col and col['width'] > 0:
            maxwidth = col['width']
        else:
            maxwidth = 0
        colwidth = 0
        for row in rows:
            printstr = str(row[i])
            if len(printstr) > colwidth:
                colwidth = len(printstr)
        if maxwidth > 0 and colwidth > maxwidth:
            widths.append(maxwidth)
        else:
            widths.append(colwidth)

    # Print rows
    padding = 2
    for row in rows:
        for (col, width) in zip(row, widths):
            printstr = str(col)
            if len(printstr) > width:
                for i in range(len(printstr)-4, len(printstr)-1):
                    printstr=printstr[:width]
                    printstr=printstr[:-3]+'...'
            sys.stdout.write(printstr)
            sys.stdout.write(' '*(width-len(printstr)))
            sys.stdout.write(' '*padding)
        sys.stdout.write('\n')
        sys.stdout.flush()


def printable_data(data):
    chars = []
    for c in data:
        if c in string.printable:
            chars += c
        else:
            chars += '.'
    return ''.join(chars)

@crochet.wait_for(timeout=30.0)
@defer.inlineCallbacks
def get_unmangled(reqid):
    req = yield pappyproxy.http.Request.load_request(reqid)
    if req.unmangled:
        defer.returnValue(req.unmangled.reqid)
    else:
        defer.returnValue(None)

    
def view_full_request(request, headers_only=False):
    if headers_only:
        print printable_data(request.raw_headers)
    else:
        print printable_data(request.full_request)

def view_full_response(response, headers_only=False):
    def check_type(response, against):
        if 'Content-Type' in response.headers and against in response.headers['Content-Type']:
            return True
        return False

    if headers_only:
        print printable_data(response.raw_headers)
    else:
        print response.raw_headers,
        to_print = printable_data(response.raw_data)
        if 'content-type' in response.headers:
            try:
                lexer = get_lexer_for_mimetype(response.headers['content-type'].split(';')[0])
                to_print = pygments.highlight(to_print, lexer, TerminalFormatter())
            except ClassNotFound:
                pass

        print to_print

def print_requests(requests):
    # Print a table with info on all the requests in the list
    cols = [
        {'name':'ID'},
        {'name':'Verb'},
        {'name': 'Host'},
        {'name':'Path', 'width':40},
        {'name':'S-Code'},
        {'name':'Req Len'},
        {'name':'Rsp Len'},
        {'name':'Time'},
        {'name':'Mngl'},
    ]
    rows = []
    for request in requests:
        rid = request.reqid
        method = request.verb
        host = request.headers['host']
        path = request.full_path
        reqlen = len(request.raw_data)
        rsplen = 'N/A'
        mangle_str = '--'

        if request.unmangled:
            mangle_str = 'q'
            
        if request.response:
            response_code = str(request.response.response_code) + \
                ' ' + request.response.response_text
            rsplen = len(request.response.raw_data)
            if request.response.unmangled:
                if mangle_str == '--':
                    mangle_str = 's'
                else:
                    mangle_str += '/s'
        else:
            response_code = ''

        time_str = '--'
        if request.time_start and request.time_end:
            time_delt = request.time_end - request.time_start
            time_str = "%.2f" % time_delt.total_seconds()

        port = request.port
        if request.is_ssl:
            is_ssl = 'YES'
        else:
            is_ssl = 'NO'
            
        rows.append([rid, method, host, path, response_code,
                     reqlen, rsplen, time_str, mangle_str])
    print_table(cols, rows)
    
def print_request_extended(request):
    # Prints extended info for the request
    title = "Request Info (reqid=%d)" % request.reqid
    print title
    print '-'*len(title)
    reqlen = len(request.raw_data)
    reqlen = '%d bytes' % reqlen
    rsplen = 'No response'

    mangle_str = 'Nothing mangled'
    if request.unmangled:
        mangle_str = 'Request'

    if request.response:
        response_code = str(request.response.response_code) + \
            ' ' + request.response.response_text
        rsplen = len(request.response.raw_data)
        rsplen = '%d bytes' % rsplen

        if request.response.unmangled:
            if mangle_str == 'Nothing mangled':
                mangle_str = 'Response'
            else:
                mangle_str += ' and Response'
    else:
        response_code = ''

    time_str = '--'
    if request.time_start and request.time_end:
        time_delt = request.time_end - request.time_start
        time_str = "%.2f sec" % time_delt.total_seconds()

    port = request.port
    if request.is_ssl:
        is_ssl = 'YES'
    else:
        is_ssl = 'NO'

    if request.time_start:
        time_made_str = request.time_start.strftime('%a, %b %d, %Y, %I:%M:%S %p')
    else:
        time_made_str = '--'
    
    print 'Made on %s' % time_made_str
    print 'ID: %d' % request.reqid
    print 'Verb: %s' % request.verb
    print 'Host: %s' % request.host
    print 'Path: %s' % request.full_path
    print 'Status Code: %s' % response_code
    print 'Request Length: %s' % reqlen
    print 'Response Length: %s' % rsplen
    if request.response.unmangled:
        print 'Unmangled Response Length: %s bytes' % len(request.response.unmangled.full_response)
    print 'Time: %s' % time_str
    print 'Port: %s' % request.port
    print 'SSL: %s' % is_ssl
    print 'Mangled: %s' % mangle_str
