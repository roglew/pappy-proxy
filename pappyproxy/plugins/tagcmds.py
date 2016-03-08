import crochet
import pappyproxy
import shlex

from pappyproxy.plugin import main_context_ids
from pappyproxy.util import PappyException, load_reqlist
from twisted.internet import defer
from pappyproxy.http import Request

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def tag(line):
    """
    Add a tag to requests.
    Usage: tag <tag> [request ids]
    You can tag as many requests as you want at the same time. If no
    ids are given, the tag will be applied to all in-context requests.
    """
    args = shlex.split(line)
    if len(args) == 0:
        raise PappyException('Tag name is required')
    tag = args[0]

    if len(args) > 1:
        reqids = yield load_reqlist(args[1], False, ids_only=True)
        print 'Tagging %s with %s' % (', '.join(reqids), tag)
    else:
        print "Tagging all in-context requests with %s" % tag
        reqids = yield main_context_ids()

    for reqid in reqids:
        req = yield Request.load_request(reqid)
        if tag not in req.tags:
            req.tags.add(tag)
            if req.saved:
                yield req.async_save()
        else:
            print 'Request %s already has tag %s' % (req.reqid, tag)

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def untag(line):
    """
    Remove a tag from requests
    Usage: untag <tag> <request ids>
    You can provide as many request ids as you want and the tag will
    be removed from all of them. If no ids are given, the tag will 
    be removed from all in-context requests.
    """
    args = shlex.split(line)
    if len(args) == 0:
        raise PappyException("Tag and request ids are required")
    tag = args[0]

    ids = []
    if len(args) > 1:
        reqids = yield load_reqlist(args[1], False, ids_only=True)
        print 'Removing tag %s from %s' % (tag, ', '.join(reqids))
    else:
        print "Removing tag %s from all in-context requests" % tag
        reqids = yield main_context_ids()

    for reqid in reqids:
        req = yield Request.load_request(reqid)
        if tag in req.tags:
            req.tags.discard(tag)
            if req.saved:
                yield req.async_save()
    if ids:
        print 'Tag %s removed from %s' % (tag, ', '.join(ids))
    
@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def clrtag(line):
    """
    Clear all the tags from requests
    Usage: clrtag <request ids>
    """
    args = shlex.split(line)
    if len(args) == 0:
        raise PappyException('No request IDs given')
    reqs = yield load_reqlist(args[0], False)

    for req in reqs:
        if req.tags:
            req.tags = set()
            print 'Tags cleared from request %s' % (req.reqid)
            if req.saved:
                yield req.async_save()

###############
## Plugin hooks

def load_cmds(cmd):
    cmd.set_cmds({
        'clrtag': (clrtag, None),
        'untag': (untag, None),
        'tag': (tag, None),
    })
    cmd.add_aliases([
        #('rpy', ''),
    ])
