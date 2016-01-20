import crochet
import datetime
import pappyproxy
import shlex

from pappyproxy.console import load_reqlist, print_table, print_requests
from pappyproxy.util import PappyException
from pappyproxy.plugin import main_context
from pappyproxy.http import Request
from twisted.internet import defer

###################
## Helper functions

def view_full_message(request, headers_only=False):
    if headers_only:
        print request.headers_section_pretty
    else:
        print request.full_message_pretty

def print_request_extended(request):
    # Prints extended info for the request
    title = "Request Info (reqid=%s)" % request.reqid
    print title
    print '-'*len(title)
    reqlen = len(request.body)
    reqlen = '%d bytes' % reqlen
    rsplen = 'No response'

    mangle_str = 'Nothing mangled'
    if request.unmangled:
        mangle_str = 'Request'

    if request.response:
        response_code = str(request.response.response_code) + \
            ' ' + request.response.response_text
        rsplen = len(request.response.body)
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

    if request.is_ssl:
        is_ssl = 'YES'
    else:
        is_ssl = 'NO'

    if request.time_start:
        time_made_str = request.time_start.strftime('%a, %b %d, %Y, %I:%M:%S %p')
    else:
        time_made_str = '--'
    
    print 'Made on %s' % time_made_str
    print 'ID: %s' % request.reqid
    print 'Verb: %s' % request.verb
    print 'Host: %s' % request.host
    print 'Path: %s' % request.full_path
    print 'Status Code: %s' % response_code
    print 'Request Length: %s' % reqlen
    print 'Response Length: %s' % rsplen
    if request.response and request.response.unmangled:
        print 'Unmangled Response Length: %s bytes' % len(request.response.unmangled.full_response)
    print 'Time: %s' % time_str
    print 'Port: %s' % request.port
    print 'SSL: %s' % is_ssl
    print 'Mangled: %s' % mangle_str
    print 'Tags: %s' % (', '.join(request.tags))
    if request.plugin_data:
        print 'Plugin Data: %s' % (request.plugin_data)

def get_site_map(reqs):
    # Takes in a list of requests and returns a tree representing the site map
    paths_set = set()
    for req in reqs:
        paths_set.add(req.path_tuple)
    paths = sorted(list(paths_set))
    return paths

def print_tree(tree):
    # Prints a tree. Takes in a sorted list of path tuples
    _print_tree_helper(tree, 0, [])
    
def _get_tree_prefix(depth, print_bars, last):
    if depth == 0:
        return u''
    else:
        ret = u''
        pb = print_bars + [True]
        for i in range(depth):
            if pb[i]:
                ret += u'\u2502   '
            else:
                ret += u'    '
        if last:
            ret += u'\u2514\u2500\u2500 '
        else:
            ret += u'\u251c\u2500\u2500 '
        return ret
    
def _print_tree_helper(tree, depth, print_bars):
    # Takes in a tree and prints it at the given depth
    if tree == [] or tree == [()]:
        return
    while tree[0] == ():
        tree = tree[1:]
        if tree == [] or tree == [()]:
            return
    if len(tree) == 1 and len(tree[0]) == 1:
        print _get_tree_prefix(depth, print_bars + [False], True) + tree[0][0]
        return

    curkey = tree[0][0]
    subtree = []
    for row in tree:
        if row[0] != curkey:
            if curkey == '':
                curkey = '/'
            print _get_tree_prefix(depth, print_bars, False) + curkey
            if depth == 0:
                _print_tree_helper(subtree, depth+1, print_bars + [False])
            else:
                _print_tree_helper(subtree, depth+1, print_bars + [True])
            curkey = row[0]
            subtree = []
        subtree.append(row[1:])
    if curkey == '':
        curkey = '/'
    print _get_tree_prefix(depth, print_bars, True) + curkey
    _print_tree_helper(subtree, depth+1, print_bars + [False])
            

####################
## Command functions
    
def list_reqs(line):
    """
    List the most recent in-context requests. By default shows the most recent 25
    Usage: list [a|num]

    If `a` is given, all the in-context requests are shown. If a number is given,
    that many requests will be shown.
    """
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

    def key_reqtime(req):
        if req.time_start is None:
            return -1
        else:
            return (req.time_start-datetime.datetime(1970,1,1)).total_seconds()

    to_print = sorted(main_context().active_requests, key=key_reqtime, reverse=True)
    if print_count > 0:
        to_print = to_print[:print_count]
    print_requests(to_print)

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def view_request_info(line):
    """
    View information about request
    Usage: view_request_info <reqid> [u]
    If 'u' is given as an additional argument, the unmangled version 
    of the request will be displayed.
    """
    args = shlex.split(line)
    reqids = args[0]

    reqs = yield load_reqlist(reqids)

    for req in reqs:
        print ''
        print_request_extended(req)
    print ''

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def view_request_headers(line):
    """
    View the headers of the request
    Usage: view_request_headers <reqid> [u]
    If 'u' is given as an additional argument, the unmangled version 
    of the request will be displayed.
    """
    args = shlex.split(line)
    reqid = args[0]

    reqs = yield load_reqlist(reqid)
    for req in reqs:
        if len(reqs) > 1:
            print 'Request %s:' % req.reqid
        print ''
        view_full_message(req, True)
        if len(reqs) > 1:
            print '-'*30


@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def view_full_request(line):
    """
    View the full data of the request
    Usage: view_full_request <reqid> [u]
    If 'u' is given as an additional argument, the unmangled version 
    of the request will be displayed.
    """
    args = shlex.split(line)
    reqid = args[0]

    reqs = yield load_reqlist(reqid)
    for req in reqs:
        if len(reqs) > 1:
            print 'Request %s:' % req.reqid
        print ''
        view_full_message(req)
        if len(reqs) > 1:
            print '-'*30


@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def view_response_headers(line):
    """
    View the headers of the response
    Usage: view_response_headers <reqid>
    """
    reqs = yield load_reqlist(line)
    for req in reqs:
        if req.response:
            if len(reqs) > 1:
                print '-'*15 + (' %s ' % req.reqid)  + '-'*15
            view_full_message(req.response, True)
        else:
            print "Request %s does not have a response" % req.reqid


@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def view_full_response(line):
    """
    View the full data of the response associated with a request
    Usage: view_full_response <reqid>
    """
    reqs = yield load_reqlist(line)
    for req in reqs:
        if req.response:
            if len(reqs) > 1:
                print '-'*15 + (' %s ' % req.reqid)  + '-'*15
            view_full_message(req.response)
        else:
            print "Request %s does not have a response" % req.reqid

    
@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def dump_response(line):
    """
    Dump the data of the response to a file.
    Usage: dump_response <id> <filename>
    """
    # dump the data of a response
    args = shlex.split(line)
    reqid = args[0]
    req = yield Request.load_request(reqid)
    rsp = req.response
    if len(args) >= 2:
        fname = args[1]
    else:
        fname = req.path.split('/')[-1]

    with open(fname, 'w') as f:
        f.write(rsp.body)
    print 'Response data written to %s' % fname

def site_map(line):
    """
    Print the site map. Only includes requests in the current context.
    Usage: site_map
    """
    to_print = [r for r in main_context().active_requests if not r.response or r.response.response_code != 404]
    tree = get_site_map(to_print)
    print_tree(tree)

    
###############
## Plugin hooks

def load_cmds(cmd):
    cmd.set_cmds({
        'list': (list_reqs, None),
        'view_request_info': (view_request_info, None),
        'view_request_headers': (view_request_headers, None),
        'view_full_request': (view_full_request, None),
        'view_response_headers': (view_response_headers, None),
        'view_full_response': (view_full_response, None),
        'site_map': (site_map, None),
        'dump_response': (dump_response, None),
    })
    cmd.add_aliases([
        ('list', 'ls'),
        ('view_request_info', 'viq'),
        ('view_request_headers', 'vhq'),
        ('view_full_request', 'vfq'),
        ('view_response_headers', 'vhs'),
        ('site_map', 'sm'),
        ('view_full_response', 'vfs'),
        #('dump_response', 'dr'),
    ])
