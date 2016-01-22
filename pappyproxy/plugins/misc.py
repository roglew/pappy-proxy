import crochet
import pappyproxy
import shlex

from pappyproxy.console import confirm, load_reqlist
from pappyproxy.util import PappyException
from pappyproxy.http import Request
from twisted.internet import defer

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def clrmem(line):
    """
    Delete all in-memory only requests
    Usage: clrmem
    """
    to_delete = list(pappyproxy.requestcache.RequestCache.inmem_reqs)
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

def load_cmds(cmd):
    cmd.set_cmds({
        'clrmem': (clrmem, None),
        'gencerts': (gencerts, None),
        'sv': (save, None),
        'export': (export, None),
        'log': (log, None),
    })
    cmd.add_aliases([
        #('rpy', ''),
    ])
