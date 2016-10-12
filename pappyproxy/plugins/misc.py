import argparse
import crochet
import pappyproxy
import shlex
import sys

from pappyproxy.colors import Colors, Styles, path_formatter, host_color, scode_color, verb_color
from pappyproxy.util import PappyException, remove_color, confirm, load_reqlist, Capturing
from pappyproxy.macros import InterceptMacro
from pappyproxy.requestcache import RequestCache
from pappyproxy.session import Session
from pappyproxy.pappy import session
from pappyproxy.plugin import add_intercepting_macro, remove_intercepting_macro, add_to_history
from pappyproxy.http import async_submit_requests, Request
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
        sys.stdout.flush()

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
        sys.stdout.flush()

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
        try:
            yield r.deep_delete()
        except PappyException as e:
            print str(e)

def gencerts(line):
    """
    Generate CA cert and private CA file
    Usage: gencerts [/path/to/put/certs/in]
    """
    dest_dir = line or pappyproxy.pappy.session.config.cert_dir
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
    pappyproxy.pappy.session.config.debug_verbosity = verbosity
    raw_input()
    pappyproxy.pappy.session.config.debug_verbosity = 0

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
       session.cons.onecmd(line.strip())
    print remove_color(output.val)
    
def version(line):
    import pappyproxy
    print pappyproxy.__version__
    
@crochet.wait_for(timeout=180.0)
@defer.inlineCallbacks
def submit(line):
    """
    Resubmit some requests, optionally with modified headers and cookies.

    Usage: submit reqids [-h] [-m] [-u] [-p] [-o REQID] [-c [COOKIES [COOKIES ...]]] [-d [HEADERS [HEADERS ...]]]
    """
    
    parser = argparse.ArgumentParser(prog="submit", usage=submit.__doc__)
    parser.add_argument('reqids')
    parser.add_argument('-m', '--inmem', action='store_true', help='Store resubmitted requests in memory without storing them in the data file')
    parser.add_argument('-u', '--unique', action='store_true', help='Only resubmit one request per endpoint (different URL parameters are different endpoints)')
    parser.add_argument('-p', '--uniquepath', action='store_true', help='Only resubmit one request per endpoint (ignoring URL parameters)')
    parser.add_argument('-c', '--cookies', nargs='*', help='Apply a cookie to requests before submitting')
    parser.add_argument('-d', '--headers', nargs='*', help='Apply a header to requests before submitting')
    parser.add_argument('-o', '--copycookies', help='Copy the cookies used in another request')
    args = parser.parse_args(shlex.split(line))

    headers = {}
    cookies = {}
    clear_cookies = False

    if args.headers:
        for h in args.headers:
            k, v = h.split('=', 1)
            headers[k] = v

    if args.copycookies:
        reqid = args.copycookies
        req = yield Request.load_request(reqid)
        clear_cookies = True
        for k, v in req.cookies.all_pairs():
            cookies[k] = v

    if args.cookies:
        for c in args.cookies:
            k, v = c.split('=', 1)
            cookies[k] = v

    if args.unique and args.uniquepath:
        raise PappyException('Both -u and -p cannot be given as arguments')

    newsession = Session(cookie_vals=cookies, header_vals=headers)
    
    reqs = yield load_reqlist(args.reqids)

    for req in reqs:
        if clear_cookies:
            req.cookies.clear()
        newsession.apply_req(req)

    conf_message = "You're about to submit %d requests, continue?" % len(reqs)
    if not confirm(conf_message):
        defer.returnValue(None)

    for r in reqs:
        r.tags.add('resubmitted')

    save = not args.inmem
    yield async_submit_requests(reqs, save=save, save_in_mem=args.inmem,
        unique_paths=args.uniquepath, unique_path_and_args=args.unique)
        
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
        'version': (version, None),
        'submit': (submit, None)
    })
    cmd.add_aliases([
        #('rpy', ''),
    ])
