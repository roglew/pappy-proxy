import argparse
import sys
import tempfile
import subprocess
from ..util import copy_to_clipboard, confirm, printable_data, Capturing, load_reqlist
from ..console import CommandError
from ..proxy import InterceptMacro
from ..colors import url_formatter, verb_color, Colors, scode_color

class WatchMacro(InterceptMacro):

    def __init__(self, client):
        InterceptMacro.__init__(self)
        self.name = "WatchMacro"
        self.client = client
        
    def mangle_request(self, request):
        if self.client.is_in_context(request):
            printstr = "> "
            printstr += verb_color(request.method) + request.method + Colors.ENDC + " "
            printstr += url_formatter(request, colored=True)
            print(printstr)

        return request

    def mangle_response(self, request, response):
        if self.client.is_in_context(request):
            printstr = "< "
            printstr += verb_color(request.method) + request.method + Colors.ENDC + ' '
            printstr += url_formatter(request, colored=True)
            printstr += " \u2192 "
            response_code = str(response.status_code) + ' ' + response.reason
            response_code = scode_color(response_code) + response_code + Colors.ENDC
            printstr += response_code
            print(printstr)

        return response

    def mangle_websocket(self, request, response, message):
        if self.client.is_in_context(request):
            printstr = ""
            if message.to_server:
                printstr += ">"
            else:
                printstr += "<"
            printstr += "ws(b={}) ".format(message.is_binary)
            printstr += printable_data(message.message)
            print(printstr)

        return message

def message_address(client, args):
    msg_addr = client.maddr
    if msg_addr is None:
        print("Client has no message address")
        return
    print(msg_addr)
    if len(args) > 0 and args[0] == "-c":
        try:
            copy_to_clipboard(msg_addr.encode())
            print("Copied to clipboard!")
        except:
            print("Could not copy address to clipboard")
            
def ping(client, args):
    print(client.ping())
    
def watch(client, args):
    macro = WatchMacro(client)
    macro.intercept_requests = True
    macro.intercept_responses = True
    macro.intercept_ws = True
    
    with client.new_conn() as conn:
        conn.intercept(macro)
        print("Watching requests. Press <Enter> to quit...")
        input()

def submit(client, cargs):
    """
    Resubmit some requests, optionally with modified headers and cookies.

    Usage: submit <reqid(s)> [-h] [-m] [-u] [-p] [-o REQID] [-c [COOKIES [COOKIES ...]]] [-d [HEADERS [HEADERS ...]]]
    """
    #Usage: submit reqids [-h] [-m] [-u] [-p] [-o REQID] [-c [COOKIES [COOKIES ...]]] [-d [HEADERS [HEADERS ...]]]
    
    if len(cargs) == 0:
        raise CommandError("Missing request id(s)")
    
    parser = argparse.ArgumentParser(prog="submit", usage=submit.__doc__)
    #parser.add_argument('reqids')
    parser.add_argument('-m', '--inmem', action='store_true', help='Store resubmitted requests in memory without storing them in the data file')
    parser.add_argument('-u', '--unique', action='store_true', help='Only resubmit one request per endpoint (different URL parameters are different endpoints)')
    parser.add_argument('-p', '--uniquepath', action='store_true', help='Only resubmit one request per endpoint (ignoring URL parameters)')
    parser.add_argument('-c', '--cookies', nargs='*', help='Apply a cookie to requests before submitting')
    parser.add_argument('-d', '--headers', nargs='*', help='Apply a header to requests before submitting')
    parser.add_argument('-o', '--copycookies', help='Copy the cookies used in another request')

    reqids = cargs[0]
    args = parser.parse_args(cargs[1:])

    headers = {}
    cookies = {}
    clear_cookies = False

    if args.headers:
        for h in args.headers:
            k, v = h.split('=', 1)
            headers[k] = v

    if args.copycookies:
        reqid = args.copycookies
        req = client.req_by_id(reqid)
        clear_cookies = True
        for k, v in req.cookie_iter():
            cookies[k] = v

    if args.cookies:
        for c in args.cookies:
            k, v = c.split('=', 1)
            cookies[k] = v

    if args.unique and args.uniquepath:
        raise CommandError('Both -u and -p cannot be given as arguments')

    # Get requests to submit
    #reqs = [r.copy() for r in client.in_context_requests()]
    reqs = client.in_context_requests()

    # Apply cookies and headers
    for req in reqs:
        if clear_cookies:
            req.headers.delete("Cookie")
        for k, v in cookies.items():
            req.set_cookie(k, v)
        for k, v in headers.items():
            req.headers.set(k, v)

    conf_message = "You're about to submit %d requests, continue?" % len(reqs)
    if not confirm(conf_message):
        return

    # Filter unique paths
    if args.uniquepath or args.unique:
        endpoints = set()
        new_reqs = []
        for r in reqs:
            if unique_path_and_args:
                s = r.url.geturl()
            else:
                s = r.url.geturl(include_params=False)

            if not s in endpoints:
                new_reqs.append(r)
                endpoints.add(s)
        reqs = new_reqs

    # Tag and send them
    for req in reqs:
        req.tags.add('resubmitted')
        sys.stdout.write(client.get_reqid(req) + " ")
        sys.stdout.flush()
        
        storage = client.disk_storage.storage_id
        if args.inmem:
            storage = client.inmem_storage.storage_id
            
        client.submit(req, storage=storage)
    sys.stdout.write("\n")
    sys.stdout.flush()


def run_with_less(client, args):
    with Capturing() as output:
        client.console.run_args(args)
    with tempfile.NamedTemporaryFile() as tf:
        tf.write(output.val.encode())
        subprocess.call(['less', '-R', tf.name])

def load_cmds(cmd):
    cmd.set_cmds({
        'maddr': (message_address, None),
        'ping': (ping, None),
        'submit': (submit, None),
        'watch': (watch, None),
        'less': (run_with_less, None),
    })
