import cmd2
import config
import context
import crochet
import mangle
import proxy
import repeater
import select
import shlex
import string
import subprocess
import sys
import termios
import time

import http
from twisted.internet import defer, reactor
from util import PappyException

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
        print ("View the headers of the request\n"
               "Usage: view_request_headers <reqid> [u]"
               "If 'u' is given as an additional argument, the unmangled version "
               "of the request will be displayed.")

    @print_pappy_errors
    @crochet.wait_for(timeout=5.0)
    @defer.inlineCallbacks
    def do_view_request_headers(self, line):
        args = shlex.split(line)
        try:
            reqid = int(args[0])
            showid = reqid
        except:
            raise PappyException("Enter a valid number for the request id")

        req = yield http.Request.load_request(reqid)
        showreq = req

        show_unmangled = False
        if len(args) > 1 and args[1][0].lower() == 'u':
            if not req.unmangled:
                raise PappyException("Request was not mangled")
            show_unmangled = True
            showreq = req.unmangled

        print ''
        print_requests([showreq])
        if show_unmangled:
            print ''
            print 'UNMANGLED --------------------'
        print ''
        view_full_request(showreq, True)

    def help_view_full_request(self):
        print ("View the full data of the request\n"
               "Usage: view_full_request <reqid> [u]\n"
               "If 'u' is given as an additional argument, the unmangled version "
               "of the request will be displayed.")

    @print_pappy_errors
    @crochet.wait_for(timeout=5.0)
    @defer.inlineCallbacks
    def do_view_full_request(self, line):
        args = shlex.split(line)
        try:
            reqid = int(args[0])
            showid = reqid
        except:
            raise PappyException("Enter a valid number for the request id")

        req = yield http.Request.load_request(reqid)
        showreq = req

        show_unmangled = False
        if len(args) > 1 and args[1][0].lower() == 'u':
            if not req.unmangled:
                raise PappyException("Request was not mangled")
            show_unmangled = True
            showreq = req.unmangled

        print ''
        print_requests([showreq])
        if show_unmangled:
            print ''
            print 'UNMANGLED --------------------'
        print ''
        view_full_request(showreq)

    def help_view_response_headers(self):
        print ("View the headers of the response\n"
               "Usage: view_response_headers <reqid>")

    @print_pappy_errors
    @crochet.wait_for(timeout=5.0)
    @defer.inlineCallbacks
    def do_view_response_headers(self, line):
        args = shlex.split(line)
        try:
            reqid = int(args[0])
            showid = reqid
        except:
            raise PappyException("Enter a valid number for the request id")

        req = yield http.Request.load_request(reqid)
        showrsp = req.response

        show_unmangled = False
        if len(args) > 1 and args[1][0].lower() == 'u':
            if not req.response.unmangled:
                raise PappyException("Response was not mangled")
            show_unmangled = True
            showrsp = req.response.unmangled

        print ''
        print_requests([req])
        if show_unmangled:
            print ''
            print 'UNMANGLED --------------------'
        print ''
        view_full_response(showrsp, True)

    def help_view_full_response(self):
        print ("View the full data of the response associated with a request\n"
               "Usage: view_full_response <reqid>")

    @print_pappy_errors
    @crochet.wait_for(timeout=5.0)
    @defer.inlineCallbacks
    def do_view_full_response(self, line):
        args = shlex.split(line)
        try:
            reqid = int(args[0])
            showid = reqid
        except:
            raise PappyException("Enter a valid number for the request id")

        req = yield http.Request.load_request(reqid)
        showrsp = req.response

        show_unmangled = False
        if len(args) > 1 and args[1][0].lower() == 'u':
            if not req.response.unmangled:
                raise PappyException("Response was not mangled")
            show_unmangled = True
            showrsp = req.response.unmangled

        print ''
        print_requests([req])
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
            print_count = 50
        
        context.sort()
        if print_count > 0:
            to_print = context.active_requests[:]
            to_print = sorted(to_print, key=lambda x: x.reqid, reverse=True)
            to_print = to_print[:print_count]
            print_requests(to_print)
        else:
            print_requests(context.active_requests)

    def help_filter(self):
        print ("Apply a filter to the current context\n"
               "Usage: filter <filter string>\n"
               "See README.md for information on filter strings")

    @print_pappy_errors
    def do_filter(self, line):
        if not line:
            raise PappyException("Filter string required")
        
        filter_to_add = context.Filter(line)
        context.add_filter(filter_to_add)

    def help_filter_clear(self):
        print ("Reset the context so that it contains no filters (ignores scope)\n"
               "Usage: filter_clear")

    @print_pappy_errors
    @crochet.wait_for(timeout=5.0)
    @defer.inlineCallbacks
    def do_filter_clear(self, line):
        context.active_filters = []
        yield context.reload_from_storage()

    def help_filter_list(self):
        print ("Print the filters that make up the current context\n"
               "Usage: filter_list")

    @print_pappy_errors
    def do_filter_list(self, line):
        for f in context.active_filters:
            print f.filter_string


    def help_scope_save(self):
        print ("Set the scope to be the current context. Saved between launches\n"
               "Usage: scope_save")

    @print_pappy_errors
    @crochet.wait_for(timeout=5.0)
    @defer.inlineCallbacks
    def do_scope_save(self, line):
        context.save_scope()
        yield context.store_scope(http.dbpool)

    def help_scope_reset(self):
        print ("Set the context to be the scope (view in-scope items)\n"
               "Usage: scope_reset")

    @print_pappy_errors
    @crochet.wait_for(timeout=5.0)
    @defer.inlineCallbacks
    def do_scope_reset(self, line):
        yield context.reset_to_scope()

    def help_scope_delete(self):
        print ("Delete the scope so that it contains all request/response pairs\n"
               "Usage: scope_delete")        

    @print_pappy_errors
    @crochet.wait_for(timeout=5.0)
    @defer.inlineCallbacks
    def do_scope_delete(self, line):
        context.set_scope([])
        yield context.store_scope(http.dbpool)

    def help_scope_list(self):
        print ("Print the filters that make up the scope\n"
               "Usage: scope_list")

    @print_pappy_errors
    def do_scope_list(self, line):
        context.print_scope()

    def help_repeater(self):
        print ("Open a request in the repeater\n"
               "Usage: repeater <reqid>")

    @print_pappy_errors
    def do_repeater(self, line):
        repeater.start_editor(int(line))

    def help_submit(self):
        print "Submit a request again (NOT IMPLEMENTED)"

    @print_pappy_errors
    @crochet.wait_for(timeout=5.0)
    @defer.inlineCallbacks
    def do_submit(self, line):
        pass
        # reqid = int(line)
        # req = yield http.Request.load_request(reqid)
        # rsp = yield req.submit()
        # print printable_data(rsp.full_response)

    def help_intercept(self):
        print ("Intercept requests and/or responses and edit them with vim before passing them along\n"
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

        if intercept_requests:
            print "Intercepting reqeusts"
        if intercept_responses:
            print "Intercepting responses"

        mangle.set_intercept_requests(intercept_requests)
        mangle.set_intercept_responses(intercept_responses)
        while 1:
            if select.select([sys.stdin,],[],[],0.0)[0]:
                break;
            else:
                if len(edit_queue) > 0:
                    (to_edit, deferred) = edit_queue.pop(0)
                    # Edit the file
                    subprocess.call(['vim', to_edit])
                    # Fire the callback
                    deferred.callback(None)
            time.sleep(0.2)

        # Send remaining requests along
        while len(edit_queue) > 0:
            (fname, deferred) = edit_queue.pop(0)
            deferred.callback(None)

        # Flush stdin so that anything we typed doesn't go into the prompt
        termios.tcflush(sys.stdin, termios.TCIOFLUSH)
        mangle.set_intercept_requests(False)
        mangle.set_intercept_responses(False)

    def help_gencerts(self):
        print ("Generate CA cert and private CA file\n"
               "Usage: gencerts [/path/to/put/certs/in]")

    @print_pappy_errors
    def do_gencerts(self, line):
        dest_dir = line or config.CERT_DIR
        print "This will overwrite any existing certs in %s. Are you sure?" % dest_dir
        print "(y/N)",
        answer = raw_input()
        if not answer or answer[0].lower() != 'y':
            return False
        print "Generating certs to %s" % dest_dir
        proxy.generate_ca_certs(dest_dir)

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
        config.DEBUG_VERBOSITY = verbosity
        raw_input()
        config.DEBUG_VERBOSITY = 0

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

def edit_file(fname):
    global edit_queue
    # Adds the filename to the edit queue. Returns a deferred that is fired once
    # the file is edited and the editor is closed
    d = defer.Deferred()
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

    
def view_full_request(request, headers_only=False):
    if headers_only:
        print printable_data(request.raw_headers)
    else:
        print printable_data(request.full_request)

def view_full_response(response, headers_only=False):
    if headers_only:
        print printable_data(response.raw_headers)
    else:
        print printable_data(response.full_response)

def print_requests(requests):
    # Print a table with info on all the requests in the list
    cols = [
        {'name':'ID'},
        {'name':'Method'},
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
        path = request.path
        reqlen = len(request.raw_data)
        rsplen = 'None'
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
            
        rows.append([rid, method, host, path, response_code,
                     reqlen, rsplen, time_str, mangle_str])
    print_table(cols, rows)
    
