import StringIO
import datetime
import re
import string
import sys
import time

from .colors import Styles, Colors, verb_color, scode_color, path_formatter, host_color
from twisted.internet import defer
from twisted.test.proto_helpers import StringTransport

class PappyException(Exception):
    """
    The exception class for Pappy. If a plugin command raises one of these, the
    message will be printed to the console rather than displaying a traceback.
    """
    pass

class PappyStringTransport(StringTransport):
    
    def __init__(self):
        StringTransport.__init__(self)
        self.complete_deferred = defer.Deferred()
        
    def finish(self):
        # Called when a finishable producer finishes
        self.producerState = 'stopped'
        
    def registerProducer(self, producer, streaming):
        StringTransport.registerProducer(self, producer, streaming)
        
    def waitForProducers(self):
        while self.producer and self.producerState == 'producing':
            self.producer.resumeProducing()

    def loseConnection(self):
        StringTransport.loseconnection(self)
        self.complete_deferred.callback(None)

    def startTLS(self, context, factory):
        pass

def printable_data(data):
    """
    Return ``data``, but replaces unprintable characters with periods.

    :param data: The data to make printable
    :type data: String
    :rtype: String
    """
    chars = []
    colored = False
    for c in data:
        if c in string.printable:
            if colored:
                chars.append(Colors.ENDC)
                colored = False
            chars.append(c)
        else:
            if not colored:
                chars.append(Styles.UNPRINTABLE_DATA)
                colored = True
            chars.append('.')
    return ''.join(chars)

def remove_color(s):
    ansi_escape = re.compile(r'\x1b[^m]*m')
    return ansi_escape.sub('', s)

# Taken from http://stackoverflow.com/questions/4770297/python-convert-utc-datetime-string-to-local-datetime
def utc2local(utc):
    epoch = time.mktime(utc.timetuple())
    offset = datetime.datetime.fromtimestamp(epoch) - datetime.datetime.utcfromtimestamp(epoch)
    return utc + offset

# Taken from https://gist.github.com/sbz/1080258
def hexdump(src, length=16):
    FILTER = ''.join([(len(repr(chr(x))) == 3) and chr(x) or '.' for x in range(256)])
    lines = []
    for c in xrange(0, len(src), length):
        chars = src[c:c+length]
        hex = ' '.join(["%02x" % ord(x) for x in chars])
        printable = ''.join(["%s" % ((ord(x) <= 127 and FILTER[ord(x)]) or Styles.UNPRINTABLE_DATA+'.'+Colors.ENDC) for x in chars])
        lines.append("%04x  %-*s  %s\n" % (c, length*3, hex, printable))
    return ''.join(lines)

# Taken from http://stackoverflow.com/questions/16571150/how-to-capture-stdout-output-from-a-python-function-call
# then modified
class Capturing():
    def __enter__(self):
        self._stdout = sys.stdout
        sys.stdout = self._stringio = StringIO.StringIO()
        return self

    def __exit__(self, *args):
        self.val = self._stringio.getvalue()
        sys.stdout = self._stdout

@defer.inlineCallbacks
def load_reqlist(line, allow_special=True, ids_only=False):
    """
    load_reqlist(line, allow_special=True)
    A helper function for parsing a list of requests that are passed as an
    argument. If ``allow_special`` is True, then it will parse IDs such as
    ``u123`` or ``s123``. Even if allow_special is false, it will still parse
    ``m##`` IDs. Will print any errors with loading any of the requests and
    will return a list of all the requests which were successfully loaded.
    Returns a deferred.

    :Returns: Twisted deferred
    """
    from .http import Request
    # Parses a comma separated list of ids and returns a list of those requests
    # prints any errors
    if not line:
        raise PappyException('Request id(s) required')
    ids = re.split(',\s*', line)
    reqs = []
    if not ids_only:
        for reqid in ids:
            try:
                req = yield Request.load_request(reqid, allow_special)
                reqs.append(req)
            except PappyException as e:
                print e
        defer.returnValue(reqs)
    else:
        defer.returnValue(ids)

def print_table(coldata, rows):
    """
    Print a table.
    Coldata: List of dicts with info on how to print the columns.
    ``name`` is the heading to give column,
    ``width (optional)`` maximum width before truncating. 0 for unlimited.

    Rows: List of tuples with the data to print
    """

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
            printdata = row[i]
            if isinstance(printdata, dict):
                collen = len(str(printdata['data']))
            else:
                collen = len(str(printdata))
            if collen > colwidth:
                colwidth = collen
        if maxwidth > 0 and colwidth > maxwidth:
            widths.append(maxwidth)
        else:
            widths.append(colwidth)

    # Print rows
    padding = 2
    is_heading = not empty_headers
    for row in rows:
        if is_heading:
            sys.stdout.write(Styles.TABLE_HEADER)
        for (col, width) in zip(row, widths):
            if isinstance(col, dict):
                printstr = str(col['data'])
                if 'color' in col:
                    colors = col['color']
                    formatter = None
                elif 'formatter' in col:
                    colors = None
                    formatter = col['formatter']
                else:
                    colors = None
                    formatter = None
            else:
                printstr = str(col)
                colors = None
                formatter = None
            if len(printstr) > width:
                trunc_printstr=printstr[:width]
                trunc_printstr=trunc_printstr[:-3]+'...'
            else:
                trunc_printstr=printstr
            if colors is not None:
                sys.stdout.write(colors)
                sys.stdout.write(trunc_printstr)
                sys.stdout.write(Colors.ENDC)
            elif formatter is not None:
                toprint = formatter(printstr, width)
                sys.stdout.write(toprint)
            else:
                sys.stdout.write(trunc_printstr)
            sys.stdout.write(' '*(width-len(printstr)))
            sys.stdout.write(' '*padding)
        if is_heading:
            sys.stdout.write(Colors.ENDC)
            is_heading = False
        sys.stdout.write('\n')
        sys.stdout.flush()

def print_requests(requests):
    """
    Takes in a list of requests and prints a table with data on each of the
    requests. It's the same table that's used by ``ls``.
    """
    rows = []
    for req in requests:
        rows.append(get_req_data_row(req))
    print_request_rows(rows)
    
def print_request_rows(request_rows):
    """
    Takes in a list of request rows generated from :func:`pappyproxy.console.get_req_data_row`
    and prints a table with data on each of the
    requests. Used instead of :func:`pappyproxy.console.print_requests` if you
    can't count on storing all the requests in memory at once.
    """
    # Print a table with info on all the requests in the list
    cols = [
        {'name':'ID'},
        {'name':'Verb'},
        {'name': 'Host'},
        {'name':'Path', 'width':40},
        {'name':'S-Code', 'width':16},
        {'name':'Req Len'},
        {'name':'Rsp Len'},
        {'name':'Time'},
        {'name':'Mngl'},
    ]
    print_rows = []
    for row in request_rows:
        (reqid, verb, host, path, scode, qlen, slen, time, mngl) = row

        verb =  {'data':verb, 'color':verb_color(verb)}
        scode = {'data':scode, 'color':scode_color(scode)}
        host = {'data':host, 'color':host_color(host)}
        path = {'data':path, 'formatter':path_formatter}

        print_rows.append((reqid, verb, host, path, scode, qlen, slen, time, mngl))
    print_table(cols, print_rows)
    
def get_req_data_row(request):
    """
    Get the row data for a request to be printed.
    """
    rid = request.reqid
    method = request.verb
    if 'host' in request.headers:
        host = request.headers['host']
    else:
        host = '??'
    path = request.full_path
    reqlen = len(request.body)
    rsplen = 'N/A'
    mangle_str = '--'

    if request.unmangled:
        mangle_str = 'q'

    if request.response:
        response_code = str(request.response.response_code) + \
            ' ' + request.response.response_text
        rsplen = len(request.response.body)
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

    return [rid, method, host, path, response_code,
            reqlen, rsplen, time_str, mangle_str]
    
def confirm(message, default='n'):
    """
    A helper function to get confirmation from the user. It prints ``message``
    then asks the user to answer yes or no. Returns True if the user answers
    yes, otherwise returns False.
    """
    if 'n' in default.lower():
        default = False
    else:
        default = True

    print message
    if default:
        answer = raw_input('(Y/n) ')
    else:
        answer = raw_input('(y/N) ')


    if not answer:
        return default

    if answer[0].lower() == 'y':
        return True
    else:
        return False
