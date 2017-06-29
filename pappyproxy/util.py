import re
import sys
import string
import time
import datetime
import base64
from pygments.formatters import TerminalFormatter
from pygments.lexers import get_lexer_for_mimetype, HttpLexer
from pygments import highlight
from io import StringIO
from .colors import Colors, Styles, verb_color, scode_color, path_formatter, color_string


def str_hash_code(s):
    h = 0
    n = len(s)-1
    for c in s.encode():
        h += c*31**n
        n -= 1
    return h

def printable_data(data, colors=True):
    """
    Return ``data``, but replaces unprintable characters with periods.

    :param data: The data to make printable
    :type data: String
    :rtype: String
    """
    chars = []
    colored = False
    for c in data:
        if chr(c) in string.printable:
            if colored and colors:
                chars.append(Colors.ENDC)
            colored = False
            chars.append(chr(c))
        else:
            if (not colored) and colors:
                chars.append(Styles.UNPRINTABLE_DATA)
            colored = True
            chars.append('.')
    if colors:
        chars.append(Colors.ENDC)
    return ''.join(chars)

def remove_color(s):
    ansi_escape = re.compile(r'\x1b[^m]*m')
    return ansi_escape.sub('', s)

def hexdump(src, length=16):
    FILTER = ''.join([(len(repr(chr(x))) == 3) and chr(x) or '.' for x in range(256)])
    lines = []
    for c in range(0, len(src), length):
        chars = src[c:c+length]
        hex = ' '.join(["%02x" % x for x in chars])
        printable = ''.join(["%s" % ((x <= 127 and FILTER[x]) or Styles.UNPRINTABLE_DATA+'.'+Colors.ENDC) for x in chars])
        lines.append("%04x  %-*s  %s\n" % (c, length*3, hex, printable))
    return ''.join(lines)

def maybe_hexdump(s):
    if any(chr(c) not in string.printable for c in s):
        return hexdump(s)
    return s

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

def print_requests(requests, client=None):
    """
    Takes in a list of requests and prints a table with data on each of the
    requests. It's the same table that's used by ``ls``.
    """
    rows = []
    for req in requests:
        rows.append(get_req_data_row(req, client=client))
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
        host = {'data':host, 'color':color_string(host, color_only=True)}
        path = {'data':path, 'formatter':path_formatter}

        print_rows.append((reqid, verb, host, path, scode, qlen, slen, time, mngl))
    print_table(cols, print_rows)
    
def get_req_data_row(request, client=None):
    """
    Get the row data for a request to be printed.
    """
    if client is not None:
        rid = client.prefixed_reqid(request)
    else:
        rid = request.db_id
    method = request.method
    host = request.dest_host
    if not request.use_tls and request.dest_port != 80:
        host = "%s:%d" % (request.dest_host, request.dest_port)
    if request.use_tls and request.dest_port != 443:
        host = "%s:%d" % (request.dest_host, request.dest_port)
    path = request.url.geturl()
    reqlen = request.content_length
    rsplen = 'N/A'
    mangle_str = '--'

    if request.unmangled:
        mangle_str = 'q'

    if request.response:
        response_code = str(request.response.status_code) + \
            ' ' + request.response.reason
        rsplen = request.response.content_length
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

    print(message)
    if default:
        answer = input('(Y/n) ')
    else:
        answer = input('(y/N) ')


    if not answer:
        return default

    if answer[0].lower() == 'y':
        return True
    else:
        return False

# Taken from http://stackoverflow.com/questions/4770297/python-convert-utc-datetime-string-to-local-datetime
def utc2local(utc):
    epoch = time.mktime(utc.timetuple())
    offset = datetime.datetime.fromtimestamp(epoch) - datetime.datetime.utcfromtimestamp(epoch)
    return utc + offset

def datetime_string(dt):
    dtobj = utc2local(dt)
    time_made_str = dtobj.strftime('%a, %b %d, %Y, %I:%M:%S.%f %p')
    return time_made_str

def copy_to_clipboard(text):
    from .clip import copy
    copy(text)
    
def clipboard_contents():
    from .clip import paste
    return paste()

def encode_basic_auth(username, password):
    decoded = '%s:%s' % (username, password)
    encoded = base64.b64encode(decoded.encode())
    header = 'Basic %s' % encoded.decode()
    return header

def parse_basic_auth(header):
    """
    Parse a raw basic auth header and return (username, password)
    """
    _, creds = header.split(' ', 1)
    decoded = base64.b64decode(creds)
    username, password = decoded.split(':', 1)
    return (username, password)

def print_query(query):
    for p in query:
        fstrs = []
        for f in p:
            fstrs.append(' '.join(f))

        print((Colors.BLUE+' OR '+Colors.ENDC).join(fstrs))

def log_error(msg):
    print(msg)

def autocomplete_startswith(text, lst, allow_spaces=False):
    ret = None
    if not text:
        ret = lst[:]
    else:
        ret = [n for n in lst if n.startswith(text)]
    if not allow_spaces:
        ret = [s for s in ret if ' ' not in s]
    return ret

def load_reqlist(client, reqids, headers_only=False):
    ids = re.compile(r",\s*").split(reqids)
    if '*' in ids:
        for req in client.in_context_requests_iter(headers_only=headers_only):
            yield req
    for i in ids:
        try:
            yield client.req_by_id(i, headers_only=headers_only)
        except Exception as e:
            print(e)

# Taken from http://stackoverflow.com/questions/16571150/how-to-capture-stdout-output-from-a-python-function-call
# then modified
class Capturing():
    def __enter__(self):
        self._stdout = sys.stdout
        sys.stdout = self._stringio = StringIO()
        return self

    def __exit__(self, *args):
        self.val = self._stringio.getvalue()
        sys.stdout = self._stdout
