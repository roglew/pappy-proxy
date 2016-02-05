import crochet
import pappyproxy
import shlex

from pappyproxy.colors import Colors, Styles, path_formatter, host_color, scode_color, verb_color
from pappyproxy.console import confirm, load_reqlist, Capturing
from pappyproxy.util import PappyException, remove_color
from pappyproxy.macros import InterceptMacro
from pappyproxy.requestcache import RequestCache
from pappyproxy.pappy import cons
from pappyproxy.plugin import add_intercepting_macro, remove_intercepting_macro
from twisted.internet import defer
from twisted.enterprise import adbapi

class PrintStreamInterceptMacro(InterceptMacro):
    """
    Intercepting macro that prints requests and responses as they go through
    the proxy
    """

    def __init__(self):
        InterceptMacro.__init__(self)
        self.name = 'Pappy Interceptor Macro'
        self.intercept_requests = False
        self.intercept_responses = False
        self.async_req = False
        self.async_rsp = False

    def __repr__(self):
        return "<PrintStreamInterceptingMacro>"

    @staticmethod
    def _print_request(req):
        s = verb_color(req.verb)+'> '+req.verb+' '+Colors.ENDC
        s += req.url_color
        s += ', len=' + str(len(req.body))
        print s

    @staticmethod
    def _print_response(req):
        response_code = str(req.response.response_code) + \
            ' ' + req.response.response_text
        s = scode_color(response_code)
        s += '< '
        s += response_code
        s += Colors.ENDC
        s += ' '
        s += req.url_color
        s += ', len=' + str(len(req.response.body))
        print s

    def mangle_request(self, request):
        PrintStreamInterceptMacro._print_request(request)
        return request

    def mangle_response(self, request):
        PrintStreamInterceptMacro._print_response(request)
        return request.response

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def clrmem(line):
    """
    Delete all in-memory only requests
    Usage: clrmem
    """
    to_delete = list(pappyproxy.http.Request.cache.inmem_reqs)
    for r in to_delete:
        yield r.deep_delete()

def gencerts(line):
    """
    Generate CA cert and private CA file
    Usage: gencerts [/path/to/put/certs/in]
    """
    dest_dir = line or pappyproxy.config.CERT_DIR
    message = "This will overwrite any existing certs in %s. Are you sure?" % dest_dir
    if not confirm(message, 'n'):
        return False
    print "Generating certs to %s" % dest_dir
    pappyproxy.proxy.generate_ca_certs(dest_dir)

def log(line):
    """
    Display the log in real time. Honestly it probably doesn't work.
    Usage: log [verbosity (default is 1)]
    verbosity=1: Show connections as they're made/lost, some additional info
    verbosity=3: Show full requests/responses as they are processed by the proxy
    """
    try:
        verbosity = int(line.strip())
    except:
        verbosity = 1
    pappyproxy.config.DEBUG_VERBOSITY = verbosity
    raw_input()
    pappyproxy.config.DEBUG_VERBOSITY = 0

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def save(line):
    args = shlex.split(line)
    reqids = args[0]
    reqs = yield load_reqlist(reqids)
    for req in reqs:
        yield req.async_deep_save()
    
@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def export(line):
    """
    Write the full request/response of a request/response to a file.
    Usage: export [req|rsp] <reqid(s)>
    """
    args = shlex.split(line)
    if len(args) < 2:
        print 'Requires req/rsp and and request id(s)'
        defer.returnValue(None)

    if args[0] not in ('req', 'rsp'):
        raise PappyException('Request or response not specified')

    reqs = yield load_reqlist(args[1])
    for req in reqs:
        try:
            if args[0] == 'req':
                fname = 'req_%s.txt'%req.reqid
                with open(fname, 'w') as f:
                    f.write(req.full_request)
                print 'Full request written to %s' % fname
            elif args[0] == 'rsp':
                fname = 'rsp_%s.txt'%req.reqid
                with open(fname, 'w') as f:
                    f.write(req.full_response)
                print 'Full response written to %s' % fname
        except PappyException as e:
            print 'Unable to export %s: %s' % (req.reqid, e)

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def merge_datafile(line):
    """
    Add all the requests/responses from another data file to the current one
    """

    def set_text_factory(conn):
        conn.text_factory = str

    line = line.strip()
    other_dbpool = adbapi.ConnectionPool("sqlite3", line,
                                         check_same_thread=False,
                                         cp_openfun=set_text_factory,
                                         cp_max=1)
    try:
        count = 0
        other_cache = RequestCache(cust_dbpool=other_dbpool)
        yield other_cache.load_ids()
        for req_d in other_cache.req_it():
            count += 1
            req = yield req_d
            r = req.copy()
            yield r.async_deep_save()
        print 'Added %d requests' % count
    finally:
        other_dbpool.close()
        
def watch_proxy(line):
    print 'Watching proxy... press ENTER to exit'
    macro = PrintStreamInterceptMacro()
    macro.intercept_requests = True
    macro.intercept_responses = True
    try:
        add_intercepting_macro('pappy_watch_proxy', macro)
        raw_input()
    finally:
        try:
            remove_intercepting_macro('pappy_watch_proxy')
        except PappyException:
            pass
        
def run_without_color(line):
    with Capturing() as output:
       cons.onecmd(line.strip())
    print remove_color(output.val)
        
def load_cmds(cmd):
    cmd.set_cmds({
        'clrmem': (clrmem, None),
        'gencerts': (gencerts, None),
        'sv': (save, None),
        'export': (export, None),
        'log': (log, None),
        'merge': (merge_datafile, None),
        'nocolor': (run_without_color, None),
        'watch': (watch_proxy, None),
    })
    cmd.add_aliases([
        #('rpy', ''),
    ])
