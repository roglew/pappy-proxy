import re
import itertools

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

def host_color(host):
    # Give each unique host a different color (ish)
    if not host:
        return Colors.RED
    hostcols = [Colors.RED,
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
    return hostcols[hash(host)%(len(hostcols)-1)]
