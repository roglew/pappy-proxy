import re
import itertools

from pygments import highlight
from pygments.lexers.data import JsonLexer
from pygments.lexers.html import XmlLexer
from pygments.lexers import get_lexer_for_mimetype, HttpLexer
from pygments.formatters import TerminalFormatter

def clen(s):
    ansi_escape = re.compile(r'\x1b[^m]*m')
    return len(ansi_escape.sub('', s))

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    # Effects
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    # Colors
    BLACK   = '\033[30m'
    RED     = '\033[31m'
    GREEN   = '\033[32m'
    YELLOW  = '\033[33m'
    BLUE    = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN    = '\033[36m'
    WHITE   = '\033[37m'

    # BG Colors
    BGBLACK   = '\033[40m'
    BGRED     = '\033[41m'
    BGGREEN   = '\033[42m'
    BGYELLOW  = '\033[43m'
    BGBLUE    = '\033[44m'
    BGMAGENTA = '\033[45m'
    BGCYAN    = '\033[46m'
    BGWHITE   = '\033[47m'

    # Light Colors
    LBLACK   = '\033[90m'
    LRED     = '\033[91m'
    LGREEN   = '\033[92m'
    LYELLOW  = '\033[93m'
    LBLUE    = '\033[94m'
    LMAGENTA = '\033[95m'
    LCYAN    = '\033[96m'
    LWHITE   = '\033[97m'

class Styles:

    ################
    # Request tables
    TABLE_HEADER = Colors.BOLD+Colors.UNDERLINE
    VERB_GET = Colors.CYAN
    VERB_POST = Colors.YELLOW
    VERB_OTHER = Colors.BLUE
    STATUS_200 = Colors.CYAN
    STATUS_300 = Colors.MAGENTA
    STATUS_400 = Colors.YELLOW
    STATUS_500 = Colors.RED
    PATH_COLORS = [Colors.CYAN, Colors.BLUE]

    KV_KEY = Colors.GREEN
    KV_VAL = Colors.ENDC

    UNPRINTABLE_DATA = Colors.CYAN

    
def verb_color(verb):
    if verb and verb == 'GET':
        return Styles.VERB_GET
    elif verb and verb == 'POST':
        return Styles.VERB_POST
    else:
        return Styles.VERB_OTHER
    
def scode_color(scode):
    if scode and scode[0] == '2':
        return Styles.STATUS_200
    elif scode and scode[0] == '3':
        return Styles.STATUS_300
    elif scode and scode[0] == '4':
        return Styles.STATUS_400
    elif scode and scode[0] == '5':
        return Styles.STATUS_500
    else:
        return Colors.ENDC

def path_formatter(path, width=-1):
    if len(path) > width and width != -1:
        path = path[:width]
        path = path[:-3]+'...'
    parts = path.split('/')
    colparts = []
    for p, c in zip(parts, itertools.cycle(Styles.PATH_COLORS)):
        colparts.append(c+p+Colors.ENDC)
    return '/'.join(colparts)

def color_string(s, color_only=False):
    """
    Return the string with a a color/ENDC. The same string will always be the same color.
    """
    from .util import str_hash_code
    # Give each unique host a different color (ish)
    if not s:
        return ""
    strcols = [Colors.RED,
               Colors.GREEN,
               Colors.YELLOW,
               Colors.BLUE,
               Colors.MAGENTA,
               Colors.CYAN,
               Colors.LRED,
               Colors.LGREEN,
               Colors.LYELLOW,
               Colors.LBLUE,
               Colors.LMAGENTA,
               Colors.LCYAN]
    col = strcols[str_hash_code(s)%(len(strcols)-1)]
    if color_only:
        return col
    else:
        return col + s + Colors.ENDC

def pretty_msg(msg):
    to_ret = pretty_headers(msg) + '\r\n' + pretty_body(msg)
    return to_ret

def pretty_headers(msg):
    to_ret = msg.headers_section()
    to_ret = highlight(to_ret, HttpLexer(), TerminalFormatter())
    return to_ret

def pretty_body(msg):
    from .util import printable_data
    to_ret = printable_data(msg.body, colors=False)
    if 'content-type' in msg.headers:
        try:
            lexer = get_lexer_for_mimetype(msg.headers.get('content-type').split(';')[0])
            to_ret = highlight(to_ret, lexer, TerminalFormatter())
        except:
            pass
    return to_ret

def url_formatter(req, colored=False, always_have_path=False, explicit_path=False, explicit_port=False):
    retstr = ''

    if not req.use_tls:
        if colored:
            retstr += Colors.RED
        retstr += 'http'
        if colored:
            retstr += Colors.ENDC
        retstr += '://'
    else:
        retstr += 'https://'

    if colored:
        retstr += color_string(req.dest_host)
    else:
        retstr += req.dest_host
    if not ((req.use_tls and req.dest_port == 443) or \
            (not req.use_tls and req.dest_port == 80) or \
            explicit_port):
        if colored:
            retstr += ':'
            retstr += Colors.MAGENTA
            retstr += str(req.dest_port)
            retstr += Colors.ENDC
        else:
            retstr += ':{}'.format(req.dest_port)
    if (req.url.path and req.url.path != '/') or always_have_path:
        if colored:
            retstr += path_formatter(req.url.path)
        else:
            retstr += req.url.path
    if req.url.params:
        retstr += '?'
        params = req.url.params.split("&")
        pairs = [tuple(param.split("=")) for param in params]
        paramstrs = []
        for k, v in pairs:
            if colored:
                paramstrs += (Colors.GREEN + '{}' + Colors.ENDC + '=' + Colors.LGREEN + '{}' + Colors.ENDC).format(k, v)
            else:
                paramstrs += '{}={}'.format(k, v)
        retstr += '&'.join(paramstrs)
    if req.url.fragment:
        retstr += '#%s' % req.url.fragment
    return retstr

