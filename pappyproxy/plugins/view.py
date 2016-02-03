import crochet
import datetime
import json
import pappyproxy
import pygments
import pprint
import shlex

from pappyproxy.console import load_reqlist, print_table, print_request_rows, get_req_data_row
from pappyproxy.util import PappyException, utc2local
from pappyproxy.http import Request
from twisted.internet import defer
from pappyproxy.plugin import main_context_ids
from pappyproxy.colors import Colors, Styles, verb_color, scode_color, path_formatter, host_color
from pygments.formatters import TerminalFormatter
from pygments.lexers.data import JsonLexer

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
    print Styles.TABLE_HEADER + title + Colors.ENDC
    reqlen = len(request.body)
    reqlen = '%d bytes' % reqlen
    rsplen = 'No response'

    mangle_str = 'Nothing mangled'
    if request.unmangled:
        mangle_str = 'Request'

    if request.response:
        response_code = str(request.response.response_code) + \
            ' ' + request.response.response_text
        response_code = scode_color(response_code) + response_code + Colors.ENDC
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
        dtobj = utc2local(request.time_start)
        time_made_str = dtobj.strftime('%a, %b %d, %Y, %I:%M:%S %p')
    else:
        time_made_str = '--'

    verb = verb_color(request.verb) + request.verb + Colors.ENDC
    host = host_color(request.host) + request.host + Colors.ENDC
    
    print_pairs = []
    print_pairs.append(('Made on', time_made_str))
    print_pairs.append(('ID', request.reqid))
    print_pairs.append(('Verb', verb))
    print_pairs.append(('Host', host))
    print_pairs.append(('Path', path_formatter(request.full_path)))
    print_pairs.append(('Status Code', response_code))
    print_pairs.append(('Request Length', reqlen))
    print_pairs.append(('Response Length', rsplen))
    if request.response and request.response.unmangled:
        print_pairs.append(('Unmangled Response Length', len(request.response.unmangled.full_response)))
    print_pairs.append(('Time', time_str))
    print_pairs.append(('Port', request.port))
    print_pairs.append(('SSL', is_ssl))
    print_pairs.append(('Mangled', mangle_str))
    print_pairs.append(('Tags', ', '.join(request.tags)))
    if request.plugin_data:
        print_pairs.append(('Plugin Data', request.plugin_data))

    for k, v in print_pairs:
        print Styles.KV_KEY+str(k)+': '+Styles.KV_VAL+str(v)

def print_tree(tree):
    # Prints a tree. Takes in a sorted list of path tuples
    _print_tree_helper(tree, 0, [])
    
def pretty_print_body(fmt, body):
    if fmt.lower() == 'json':
        try:
            d = json.loads(body.strip())
        except:
            raise PappyException('Body could not be parsed as JSON')
        s = json.dumps(d, indent=4, sort_keys=True)
        print pygments.highlight(s, JsonLexer(), TerminalFormatter())
    else:
        raise PappyException('%s is not a valid format' % fmt)
    
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
    
@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
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

    rows = []
    ids = yield main_context_ids(print_count)
    for i in ids:
        req = yield Request.load_request(i)
        rows.append(get_req_data_row(req))
    print_request_rows(rows)

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def view_request_info(line):
    """
    View information about request
    Usage: view_request_info <reqid(s)>
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
    Usage: view_request_headers <reqid(s)>
    """
    args = shlex.split(line)
    reqid = args[0]

    reqs = yield load_reqlist(reqid)
    for req in reqs:
        if len(reqs) > 1:
            print 'Request %s:' % req.reqid
        view_full_message(req, True)
        if len(reqs) > 1:
            print '-'*30
            print ''


@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def view_full_request(line):
    """
    View the full data of the request
    Usage: view_full_request <reqid(s)>
    """
    args = shlex.split(line)
    reqid = args[0]

    reqs = yield load_reqlist(reqid)
    for req in reqs:
        if len(reqs) > 1:
            print 'Request %s:' % req.reqid
        view_full_message(req)
        if len(reqs) > 1:
            print '-'*30
            print ''

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def view_request_bytes(line):
    """
    View the raw bytes of the request. Use this if you want to redirect output to a file.
    Usage: view_request_bytes <reqid(s)>
    """
    args = shlex.split(line)
    reqid = args[0]

    reqs = yield load_reqlist(reqid)
    for req in reqs:
        if len(reqs) > 1:
            print 'Request %s:' % req.reqid
        print req.full_message
        if len(reqs) > 1:
            print '-'*30
            print ''
            
@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def pretty_print_request(line):
    """
    Print the body of the request pretty printed.
    Usage: pretty_print_request <format> <reqid(s)>
    """
    args = shlex.split(line)
    if len(args) < 2:
        raise PappyException("Usage: pretty_print_request <format> <reqid(s)>")
    reqids = args[1]

    reqs = yield load_reqlist(reqids)
    for req in reqs:
        pretty_print_body(args[0], req.body)

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def view_response_headers(line):
    """
    View the headers of the response
    Usage: view_response_headers <reqid(s)>
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
def view_response_bytes(line):
    """
    View the full data of the response associated with a request
    Usage: view_request_bytes <reqid(s)>
    """
    reqs = yield load_reqlist(line)
    for req in reqs:
        if req.response:
            if len(reqs) > 1:
                print '-'*15 + (' %s ' % req.reqid)  + '-'*15
            print req.response.full_message
        else:
            print "Request %s does not have a response" % req.reqid
            
@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def pretty_print_response(line):
    """
    Print the body of the request pretty printed.
    Usage: pretty_print_request <format> <reqid(s)>
    """
    args = shlex.split(line)
    if len(args) < 2:
        raise PappyException("Usage: pretty_print_request <format> <reqid(s)>")
    reqids = args[1]

    reqs = yield load_reqlist(reqids)
    for req in reqs:
        if req.response:
            pretty_print_body(args[0], req.response.body)
        else:
            print 'No response associated with request %s' % req.reqid

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

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def site_map(line):
    """
    Print the site map. Only includes requests in the current context.
    Usage: site_map
    """
    ids = yield main_context_ids()
    paths_set = set()
    for reqid in ids:
        req = yield Request.load_request(reqid)
        if req.response and req.response.response_code != 404:
            paths_set.add(req.path_tuple)
    tree = sorted(list(paths_set))
    print_tree(tree)

    
###############
## Plugin hooks

def load_cmds(cmd):
    cmd.set_cmds({
        'list': (list_reqs, None),
        'view_request_info': (view_request_info, None),
        'view_request_headers': (view_request_headers, None),
        'view_full_request': (view_full_request, None),
        'view_request_bytes': (view_request_bytes, None),
        'pretty_print_request': (pretty_print_request, None),
        'view_response_headers': (view_response_headers, None),
        'view_full_response': (view_full_response, None),
        'view_response_bytes': (view_response_bytes, None),
        'pretty_print_response': (pretty_print_response, None),
        'site_map': (site_map, None),
        'dump_response': (dump_response, None),
    })
    cmd.add_aliases([
        ('list', 'ls'),
        ('view_request_info', 'viq'),
        ('view_request_headers', 'vhq'),
        ('view_full_request', 'vfq'),
        ('view_request_bytes', 'vbq'),
        ('pretty_print_request', 'ppq'),
        ('view_response_headers', 'vhs'),
        ('view_full_response', 'vfs'),
        ('view_response_bytes', 'vbs'),
        ('pretty_print_response', 'pps'),
        ('site_map', 'sm'),
        #('dump_response', 'dr'),
    ])
