import datetime
import json
import pygments
import pprint
import re
import shlex
import urllib

from ..util import print_table, print_request_rows, get_req_data_row, datetime_string, maybe_hexdump, load_reqlist
from ..colors import Colors, Styles, verb_color, scode_color, path_formatter, color_string, url_formatter, pretty_msg, pretty_headers
from ..console import CommandError
from pygments.formatters import TerminalFormatter
from pygments.lexers.data import JsonLexer
from pygments.lexers.html import XmlLexer
from urllib.parse import parse_qs, unquote

###################
## Helper functions

def view_full_message(request, headers_only=False, try_ws=False):
    def _print_message(mes):
        print_str = ''
        if mes.to_server == False:
            print_str += Colors.BLUE
            print_str += '< Incoming'
        else:
            print_str += Colors.GREEN
            print_str += '> Outgoing'
        print_str += Colors.ENDC
        if mes.unmangled:
            print_str += ', ' + Colors.UNDERLINE + 'mangled' + Colors.ENDC
        t_plus = "??"
        if request.time_start:
            t_plus = mes.timestamp - request.time_start
        print_str += ', binary = %s, T+%ss\n' % (mes.is_binary, t_plus.total_seconds())

        print_str += Colors.ENDC
        print_str += maybe_hexdump(mes.message).decode()
        print_str += '\n'
        return print_str

    if headers_only:
        print(pretty_headers(request))
    else:
        if try_ws and request.ws_messages:
            print_str = ''
            print_str += Styles.TABLE_HEADER
            print_str += "Websocket session handshake\n"
            print_str += Colors.ENDC
            print_str += pretty_msg(request)
            print_str += '\n'
            print_str += Styles.TABLE_HEADER
            print_str += "Websocket session \n"
            print_str += Colors.ENDC
            for wsm in request.ws_messages:
                print_str += _print_message(wsm)
                if wsm.unmangled:
                    print_str += Colors.YELLOW
                    print_str += '-'*10
                    print_str += Colors.ENDC
                    print_str += ' vv UNMANGLED vv '
                    print_str += Colors.YELLOW
                    print_str += '-'*10
                    print_str += Colors.ENDC
                    print_str += '\n'
                    print_str += _print_message(wsm.unmangled)
                print_str += Colors.YELLOW
                print_str += '-'*20 + '-'*len(' ^^ UNMANGLED ^^ ')
                print_str += '\n'
                print_str += Colors.ENDC
            print(print_str)
        else:
            print(pretty_msg(request))

def print_request_extended(client, request):
    # Prints extended info for the request
    title = "Request Info (reqid=%s)" % client.get_reqid(request)
    print(Styles.TABLE_HEADER + title + Colors.ENDC)
    reqlen = len(request.body)
    reqlen = '%d bytes' % reqlen
    rsplen = 'No response'

    mangle_str = 'Nothing mangled'
    if request.unmangled:
        mangle_str = 'Request'

    if request.response:
        response_code = str(request.response.status_code) + \
            ' ' + request.response.reason
        response_code = scode_color(response_code) + response_code + Colors.ENDC
        rsplen = request.response.content_length
        rsplen = '%d bytes' % rsplen

        if request.response.unmangled:
            if mangle_str == 'Nothing mangled':
                mangle_str = 'Response'
            else:
                mangle_str += ' and Response'
    else:
        response_code = ''

    time_str = '--'
    if request.time_end is not None and request.time_start is not None:
        time_delt = request.time_end - request.time_start
        time_str = "%.2f sec" % time_delt.total_seconds()

    if request.use_tls:
        is_ssl = 'YES'
    else:
        is_ssl = Colors.RED + 'NO' + Colors.ENDC

    if request.time_start:
        time_made_str = datetime_string(request.time_start)
    else:
        time_made_str = '--'

    verb = verb_color(request.method) + request.method + Colors.ENDC
    host = color_string(request.dest_host)
    
    colored_tags = [color_string(t) for t in request.tags]
    
    print_pairs = []
    print_pairs.append(('Made on', time_made_str))
    print_pairs.append(('ID', client.get_reqid(request)))
    print_pairs.append(('URL', url_formatter(request, colored=True)))
    print_pairs.append(('Host', host))
    print_pairs.append(('Path', path_formatter(request.url.path)))
    print_pairs.append(('Verb', verb))
    print_pairs.append(('Status Code', response_code))
    print_pairs.append(('Request Length', reqlen))
    print_pairs.append(('Response Length', rsplen))
    if request.response and request.response.unmangled:
        print_pairs.append(('Unmangled Response Length', request.response.unmangled.content_length))
    print_pairs.append(('Time', time_str))
    print_pairs.append(('Port', request.dest_port))
    print_pairs.append(('SSL', is_ssl))
    print_pairs.append(('Mangled', mangle_str))
    print_pairs.append(('Tags', ', '.join(colored_tags)))

    for k, v in print_pairs:
        print(Styles.KV_KEY+str(k)+': '+Styles.KV_VAL+str(v))

def pretty_print_body(fmt, body):
    try:
        bstr = body.decode()
        if fmt.lower() == 'json':
            d = json.loads(bstr.strip())
            s = json.dumps(d, indent=4, sort_keys=True)
            print(pygments.highlight(s, JsonLexer(), TerminalFormatter()))
        elif fmt.lower() == 'form':
            qs = parse_qs(bstr, keep_blank_values=True)
            for k, vs in qs.items():
                for v in vs:
                    s = Colors.GREEN
                    s += '%s: ' % unquote(k)
                    s += Colors.ENDC
                    if v == '':
                        s += Colors.RED
                        s += 'EMPTY'
                        s += Colors.ENDC
                    else:
                        s += unquote(v)
                    print(s)
        elif fmt.lower() == 'text':
            print(bstr)
        elif fmt.lower() == 'xml':
            import xml.dom.minidom
            xml = xml.dom.minidom.parseString(bstr)
            print(pygments.highlight(xml.toprettyxml(), XmlLexer(), TerminalFormatter()))
        else:
            raise CommandError('"%s" is not a valid format' % fmt)
    except CommandError as e:
        raise e
    except Exception as e:
        raise CommandError('Body could not be parsed as "{}": {}'.format(fmt, e))

def print_params(client, req, params=None):
    if not req.url.parameters() and not req.body:
        print('Request %s has no url or data parameters' % client.get_reqid(req))
        print('')
    if req.url.parameters():
        print(Styles.TABLE_HEADER + "Url Params" + Colors.ENDC)
        for k, v in req.url.param_iter():
            if params is None or (params and k in params):
                print(Styles.KV_KEY+str(k)+': '+Styles.KV_VAL+str(v))
        print('')
    if req.body:
        print(Styles.TABLE_HEADER + "Body/POST Params" + Colors.ENDC)
        pretty_print_body(guess_pretty_print_fmt(req), req.body)
        print('')
    if 'cookie' in req.headers:
        print(Styles.TABLE_HEADER + "Cookies" + Colors.ENDC)
        for k, v in req.cookie_iter():
            if params is None or (params and k in params):
                print(Styles.KV_KEY+str(k)+': '+Styles.KV_VAL+str(v))
        print('')
    # multiform request when we support it

def guess_pretty_print_fmt(msg):
    if 'content-type' in msg.headers:
        if 'json' in msg.headers.get('content-type'):
            return 'json'
        elif 'www-form' in msg.headers.get('content-type'):
            return 'form'
        elif 'application/xml' in msg.headers.get('content-type'):
            return 'xml'
    return 'text'
    
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
                ret += u'\u2502  '
            else:
                ret += u'   '
        if last:
            ret += u'\u2514\u2500 '
        else:
            ret += u'\u251c\u2500 '
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
        print(_get_tree_prefix(depth, print_bars + [False], True) + tree[0][0])
        return

    curkey = tree[0][0]
    subtree = []
    for row in tree:
        if row[0] != curkey:
            if curkey == '':
                curkey = '/'
            print(_get_tree_prefix(depth, print_bars, False) + curkey)
            if depth == 0:
                _print_tree_helper(subtree, depth+1, print_bars + [False])
            else:
                _print_tree_helper(subtree, depth+1, print_bars + [True])
            curkey = row[0]
            subtree = []
        subtree.append(row[1:])
    if curkey == '':
        curkey = '/'
    print(_get_tree_prefix(depth, print_bars, True) + curkey)
    _print_tree_helper(subtree, depth+1, print_bars + [False])


def add_param(found_params, kind: str, k: str, v: str, reqid: str):
    if type(k) is not str:
        raise Exception("BAD")
    if not k in found_params:
        found_params[k] = {}
    if kind in found_params[k]:
        found_params[k][kind].append((reqid, v))
    else:
        found_params[k][kind] = [(reqid, v)]
        
def print_param_info(param_info):
    for k, d in param_info.items():
        print(Styles.TABLE_HEADER + k + Colors.ENDC)
        for param_type, valpairs in d.items():
            print(param_type)
            value_ids = {}
            for reqid, val in valpairs:
                ids = value_ids.get(val, [])
                ids.append(reqid)
                value_ids[val] = ids
            for val, ids in value_ids.items():
                if len(ids) <= 15:
                    idstr = ', '.join(ids)
                else:
                    idstr = ', '.join(ids[:15]) + '...'
                if val == '':
                    printstr = (Colors.RED + 'BLANK' + Colors.ENDC + 'x%d (%s)') % (len(ids), idstr)
                else:
                    printstr = (Colors.GREEN + '%s' + Colors.ENDC + 'x%d (%s)') % (val, len(ids), idstr)
                print(printstr)
        print('')
        
def path_tuple(url):
    return tuple(url.path.split('/'))
    
####################
## Command functions
    
def list_reqs(client, args):
    """
    List the most recent in-context requests. By default shows the most recent 25
    Usage: list [a|num]

    If `a` is given, all the in-context requests are shown. If a number is given,
    that many requests will be shown.
    """
    if len(args) > 0:
        if args[0][0].lower() == 'a':
            print_count = 0
        else:
            try:
                print_count = int(args[0])
            except:
                print("Please enter a valid argument for list")
                return
    else:
        print_count = 25

    rows = []
    reqs = client.in_context_requests(headers_only=True, max_results=print_count)
    for req in reqs:
        rows.append(get_req_data_row(req, client=client))
    print_request_rows(rows)

def view_full_request(client, args):
    """
    View the full data of the request
    Usage: view_full_request <reqid(s)>
    """
    if not args:
        raise CommandError("Request id is required")
    reqs = load_reqlist(client, args[0])
    for req in reqs:
        print('-- Request id=%s --------------------' % req.db_id)
        view_full_message(req, try_ws=True)

def view_full_response(client, args):
    """
    View the full data of the response associated with a request
    Usage: view_full_response <reqid>
    """
    if not args:
        raise CommandError("Request id is required")
    reqs = load_reqlist(client, args[0])
    for req in reqs:
        if not req.response:
            print("-- Request {} does not have an associated response".format(reqid))
        else:
            print('-- Request id=%s --------------------' % req.db_id)
            view_full_message(req.response)

def view_request_headers(client, args):
    """
    View the headers of the request
    Usage: view_request_headers <reqid(s)>
    """
    if not args:
        raise CommandError("Request id is required")
    reqs = load_reqlist(client, args[0], headers_only=True)
    for req in reqs:
        print('-- Request id=%s --------------------' % req.db_id)
        view_full_message(req, headers_only=True)

def view_response_headers(client, args):
    """
    View the full data of the response associated with a request
    Usage: view_full_response <reqid>
    """
    if not args:
        raise CommandError("Request id is required")
    reqs = load_reqlist(client, args[0], headers_only=True)
    for req in reqs:
        if not req.response:
            print("-- Request {} does not have an associated response".format(reqid))
        else:
            print('-- Request id=%s --------------------' % req.db_id)
            view_full_message(req.response, headers_only=True)

def view_request_info(client, args):
    """
    View information about request
    Usage: view_request_info <reqid(s)>
    """
    if not args:
        raise CommandError("Request id is required")
    reqs = load_reqlist(client, args[0], headers_only=True)
    for req in reqs:
        print_request_extended(client, req)
        print('')
    if not args:
        raise CommandError("Request id is required")

def pretty_print_request(client, args):
    """
    Print the body of the request pretty printed.
    Usage: pretty_print_request <format> <reqid(s)>
    """
    if len(args) < 2:
        raise CommandError("Usage: pretty_print_request <format> <reqid(s)>")
    print_type = args[0]
    reqs = load_reqlist(client, args[1])
    for req in reqs:
        print('-- Request id=%s --------------------' % req.db_id)
        try:
            pretty_print_body(print_type, req.body)
        except Exception as e:
            print(str(e))

def pretty_print_response(client, args):
    """
    Print the body of the response pretty printed.
    Usage: pretty_print_response <format> <reqid(s)>
    """
    if len(args) < 2:
        raise CommandError("Usage: pretty_print_request <format> <reqid(s)>")
    print_type = args[0]
    reqs = load_reqlist(client, args[1])
    for req in reqs:
        print('-- Request id=%s --------------------' % req.db_id)
        if not req.response:
            print("request {} does not have an associated response".format(reqid))
            continue
        try:
            pretty_print_body(print_type, req.response.body)
        except Exception as e:
            print(str(e))

def print_params_cmd(client, args):
    """
    View the parameters of a request
    Usage: print_params <reqid(s)> [key 1] [key 2] ...
    """
    if not args:
        raise CommandError("Request id is required")
    if len(args) > 1:
        keys = args[1:]
    else:
        keys = None

    reqs = load_reqlist(client, args[0])
    for req in reqs:
        print('-- Request id=%s --------------------' % req.db_id)
        print_params(client, req, keys)
            
def get_param_info(client, args):
    if len(args) == 0:
        raise CommandError("Request ID(s) required")
    reqs = load_reqlist(client, args[0])
    args = args[1:]

    if args and args[0] == 'ct':
        contains = True
        args = args[1:]
    else:
        contains = False

    if args:
        params = tuple(args)
    else:
        params = None
        
    def check_key(k, params, contains):
        if contains:
            for p in params:
                if p.lower() in k.lower():
                    return True
        else:
            if params is None or k in params:
                return True
        return False

    found_params = {}

    for req in reqs:
        prefixed_id = client.get_reqid(req)
        for k, v in req.url.param_iter():
            if type(k) is not str:
                raise Exception("BAD")
            if check_key(k, params, contains):
                add_param(found_params, 'Url Parameter', k, v, prefixed_id)
        for k, v in req.param_iter():
            if check_key(k, params, contains):
                add_param(found_params, 'POST Parameter', k, v, prefixed_id)
        for k, v in req.cookie_iter():
            if check_key(k, params, contains):
                add_param(found_params, 'Cookie', k, v, prefixed_id)
    print_param_info(found_params)

def find_urls(client, args):
    if len(args) > 0:
        reqs = load_reqlist(client, args[0])
    else:
        reqs = client.in_context_requests_iter() # update to take reqlist

    url_regexp = b'((?:http|ftp|https)://(?:[\w_-]+(?:(?:\.[\w_-]+)+))(?:[\w.,@?^=%&:/~+#-]*[\w@?^=%&/~+#-])?)'
    urls = set()
    for req in reqs:
        urls |= set(re.findall(url_regexp, req.full_message()))
        if req.response:
            urls |= set(re.findall(url_regexp, req.response.full_message()))
    for url in sorted(urls):
        print(url.decode())

def site_map(client, args):
    """
    Print the site map. Only includes requests in the current context.
    Usage: site_map
    """
    if len(args) > 0 and args[0] == 'p':
        paths = True
    else:
        paths = False
    all_reqs = client.in_context_requests(headers_only=True)
    reqs_by_host = {}
    for req in all_reqs:
        reqs_by_host.setdefault(req.dest_host, []).append(req)
    for host, reqs in reqs_by_host.items():
        paths_set = set()
        for req in reqs:
            if req.response and req.response.status_code != 404:
                paths_set.add(path_tuple(req.url))
        tree = sorted(list(paths_set))
        print(host)
        if paths:
            for p in tree:
                print ('/'.join(list(p)))
        else:
            print_tree(tree)
        print("")
        
def save_request(client, args):
    if not args:
        raise CommandError("Request id is required")
    reqs = load_reqlist(client, args[0])
    for req in reqs:
        if len(args) >= 2:
            fname = args[1]
        else:
            fname = "req_%s" % client.get_reqid(req)

        with open(fname, 'wb') as f:
            f.write(req.full_message())
        print('Request written to {}'.format(fname))

def save_response(client, args):
    if not args:
        raise CommandError("Request id(s) is required")
    reqs = load_reqlist(client, args[0])
    for req in reqs:
        if req.response:
            rsp = req.response
            if len(args) >= 2:
                fname = args[1]
            else:
                fname = "rsp_%s" % client.get_reqid(req)

            with open(fname, 'wb') as f:
                f.write(rsp.full_message())
            print('Response written to {}'.format(fname))
        else:
            print('Request {} does not have a response'.format(req.reqid))

def dump_response(client, args):
    """
    Dump the data of the response to a file.
    Usage: dump_response <id> <filename>
    """
    # dump the data of a response
    if not args:
        raise CommandError("Request id(s) is required")
    reqs = load_reqlist(client, args[0])
    for req in reqs:
        if req.response:
            rsp = req.response
            if len(args) >= 2:
                fname = args[1]
            else:
                fname = req.url.path.split('/')[-1]

            with open(fname, 'wb') as f:
                f.write(rsp.body)
            print('Response body written to {}'.format(fname))
        else:
            print('Request {} does not have a response'.format(req.reqid))

def get_surrounding_lines(s, n, lines):
    left = n
    right = n
    lines_left = 0
    lines_right = 0

    # move left until we find enough lines or hit the edge
    while left > 0 and lines_left < lines:
        if s[left] == '\n':
            lines_left += 1
        left -= 1

    # move right until we find enough lines or hit the edge
    while right < len(s) and lines_right < lines:
        if s[right] == '\n':
            lines_right += 1
        right += 1

    return s[left:right]

def print_search_header(reqid, locstr):
    printstr = Styles.TABLE_HEADER
    printstr += "Result(s) for request {} ({})".format(reqid, locstr)
    printstr += Colors.ENDC
    print(printstr)

def highlight_str(s, substr):
    highlighted = Colors.BGYELLOW + Colors.BLACK + Colors.BOLD + substr + Colors.ENDC
    return s.replace(substr, highlighted)

def search_message(mes, substr, lines, reqid, locstr):
    header_printed = False
    for m in re.finditer(substr, mes):
        if not header_printed:
            print_search_header(reqid, locstr)
            header_printed = True
        n = m.start()
        linestr = get_surrounding_lines(mes, n, lines)
        linelist = linestr.split('\n')
        linestr = '\n'.join(line[:500] for line in linelist)
        toprint = highlight_str(linestr, substr)
        print(toprint)
        print('-'*50)

def search(client, args):
    search_str = args[0]
    lines = 2
    if len(args) > 1:
        lines = int(args[1])
    for req in client.in_context_requests_iter():
        reqid = client.get_reqid(req)
        reqheader_printed = False
        try:
            mes = req.full_message().decode()
            search_message(mes, search_str, lines, reqid, "Request")
        except UnicodeDecodeError:
            pass
        if req.response:
            try:
                mes = req.response.full_message().decode()
                search_message(mes, search_str, lines, reqid, "Response")
            except UnicodeDecodeError:
                pass

        wsheader_printed = False
        for wsm in req.ws_messages:
            if not wsheader_printed:
                print_search_header(client.get_reqid(req), reqid, "Websocket Messages")
                wsheader_printed = True
            if search_str in wsm.message:
                print(highlight_str(wsm.message, search_str))


# @crochet.wait_for(timeout=None)
# @defer.inlineCallbacks
# def view_request_bytes(line):
#     """
#     View the raw bytes of the request. Use this if you want to redirect output to a file.
#     Usage: view_request_bytes <reqid(s)>
#     """
#     args = shlex.split(line)
#     if not args:
#         raise CommandError("Request id is required")
#     reqid = args[0]

#     reqs = yield load_reqlist(reqid)
#     for req in reqs:
#         if len(reqs) > 1:
#             print 'Request %s:' % req.reqid
#         print req.full_message
#         if len(reqs) > 1:
#             print '-'*30
#             print ''

# @crochet.wait_for(timeout=None)
# @defer.inlineCallbacks
# def view_response_bytes(line):
#     """
#     View the full data of the response associated with a request
#     Usage: view_request_bytes <reqid(s)>
#     """
#     reqs = yield load_reqlist(line)
#     for req in reqs:
#         if req.response:
#             if len(reqs) > 1:
#                 print '-'*15 + (' %s ' % req.reqid)  + '-'*15
#             print req.response.full_message
#         else:
#             print "Request %s does not have a response" % req.reqid
            
    
###############
## Plugin hooks

def load_cmds(cmd):
    cmd.set_cmds({
        'list': (list_reqs, None),
        'view_full_request': (view_full_request, None),
        'view_full_response': (view_full_response, None),
        'view_request_headers': (view_request_headers, None),
        'view_response_headers': (view_response_headers, None),
        'view_request_info': (view_request_info, None),
        'pretty_print_request': (pretty_print_request, None),
        'pretty_print_response': (pretty_print_response, None),
        'print_params': (print_params_cmd, None),
        'param_info': (get_param_info, None),
        'urls': (find_urls, None),
        'site_map': (site_map, None),
        'dump_response': (dump_response, None),
        'save_request': (save_request, None),
        'save_response': (save_response, None),
        'search': (search, None),
        # 'view_request_bytes': (view_request_bytes, None),
        # 'view_response_bytes': (view_response_bytes, None),
    })
    cmd.add_aliases([
        ('list', 'ls'),
        ('view_full_request', 'vfq'),
        ('view_full_request', 'kjq'),
        ('view_request_headers', 'vhq'),
        ('view_response_headers', 'vhs'),
        ('view_full_response', 'vfs'),
        ('view_full_response', 'kjs'),
        ('view_request_info', 'viq'),
        ('pretty_print_request', 'ppq'),
        ('pretty_print_response', 'pps'),
        ('print_params', 'pprm'),
        ('param_info', 'pri'),
        ('site_map', 'sm'),
        ('save_request', 'savereq'),
        ('save_response', 'saversp'),
        # ('view_request_bytes', 'vbq'),
        # ('view_response_bytes', 'vbs'),
        # #('dump_response', 'dr'),
    ])
