import crochet
import pappyproxy

from pappyproxy.console import confirm
from pappyproxy.util import PappyException
from pappyproxy.http import Request
from twisted.internet import defer

class BuiltinFilters(object):
    _filters = {
        'not_image': (
            ['path nctr "(\.png$|\.jpg$|\.gif$)"'],
            'Filter out image requests',
        ),
        'not_jscss': (
            ['path nctr "(\.js$|\.css$)"'],
            'Filter out javascript and css files',
        ),
    }
    
    @staticmethod
    @defer.inlineCallbacks
    def get(name):
        if name not in BuiltinFilters._filters:
            raise PappyException('%s not a bult in filter' % name)
        if name in BuiltinFilters._filters:
            filters = [pappyproxy.context.Filter(f) for f in BuiltinFilters._filters[name][0]]
            for f in filters:
                yield f.generate()
            defer.returnValue(filters)
        raise PappyException('"%s" is not a built-in filter' % name)

    @staticmethod
    def list():
        return [k for k, v in BuiltinFilters._filters.iteritems()]

    @staticmethod
    def help(name):
        if name not in BuiltinFilters._filters:
            raise PappyException('"%s" is not a built-in filter' % name)
        return pappyproxy.context.Filter(BuiltinFilters._filters[name][1])


@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def filtercmd(line):
    """
    Apply a filter to the current context
    Usage: filter <filter string>
    See README.md for information on filter strings
    """
    if not line:
        raise PappyException("Filter string required")
    
    filter_to_add = pappyproxy.context.Filter(line)
    yield filter_to_add.generate()
    pappyproxy.pappy.main_context.add_filter(filter_to_add)

def complete_builtin_filter(text, line, begidx, endidx):
    all_names = BuiltinFilters.list()
    if not text:
        ret = all_names[:]
    else:
        ret = [n for n in all_names if n.startswith(text)]
    return ret
    
@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def builtin_filter(line):
    if not line:
        raise PappyException("Filter name required")
    
    filters_to_add = yield BuiltinFilters.get(line)
    for f in filters_to_add:
        print f.filter_string
        yield pappyproxy.pappy.main_context.add_filter(f)
    defer.returnValue(None)

def filter_up(line):
    """
    Remove the last applied filter
    Usage: filter_up
    """
    pappyproxy.pappy.main_context.filter_up()

def filter_clear(line):
    """
    Reset the context so that it contains no filters (ignores scope)
    Usage: filter_clear
    """
    pappyproxy.pappy.main_context.set_filters([])

def filter_list(line):
    """
    Print the filters that make up the current context
    Usage: filter_list
    """
    for f in pappyproxy.pappy.main_context.active_filters:
        print f.filter_string


@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def scope_save(line):
    """
    Set the scope to be the current context. Saved between launches
    Usage: scope_save
    """
    pappyproxy.context.save_scope(pappyproxy.pappy.main_context)
    yield pappyproxy.context.store_scope(pappyproxy.http.dbpool)

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def scope_reset(line):
    """
    Set the context to be the scope (view in-scope items)
    Usage: scope_reset
    """
    yield pappyproxy.context.reset_to_scope(pappyproxy.pappy.main_context)

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def scope_delete(line):
    """
    Delete the scope so that it contains all request/response pairs
    Usage: scope_delete
    """
    pappyproxy.context.set_scope([])
    yield pappyproxy.context.store_scope(pappyproxy.http.dbpool)

def scope_list(line):
    """
    Print the filters that make up the scope
    Usage: scope_list
    """
    pappyproxy.context.print_scope()

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def filter_prune(line):
    """
    Delete all out of context requests from the data file. 
    CANNOT BE UNDONE!! Be careful!
    Usage: filter_prune
    """
    # Delete filtered items from datafile
    print ''
    print 'Currently active filters:'
    for f in pappyproxy.pappy.main_context.active_filters:
        print '> %s' % f.filter_string

    # We copy so that we're not removing items from a set we're iterating over
    act_reqs = yield pappyproxy.pappy.main_context.get_reqs()
    inact_reqs = Request.cache.all_ids.difference(set(act_reqs))
    inact_reqs = inact_reqs.difference(set(Request.cache.unmangled_ids))
    message = 'This will delete %d/%d requests. You can NOT undo this!! Continue?' % (len(inact_reqs), (len(inact_reqs) + len(act_reqs)))
    if not confirm(message, 'n'):
        defer.returnValue(None)
    
    for reqid in inact_reqs:
        try:
            req = yield pappyproxy.http.Request.load_request(reqid)
            yield req.deep_delete()
        except PappyException as e:
            print e
    print 'Deleted %d requests' % len(inact_reqs)
    defer.returnValue(None)

###############
## Plugin hooks

def load_cmds(cmd):
    cmd.set_cmds({
        'filter_prune': (filter_prune, None),
        'scope_list': (scope_list, None),
        'scope_delete': (scope_delete, None),
        'scope_reset': (scope_reset, None),
        'scope_save': (scope_save, None),
        'filter_list': (filter_list, None),
        'filter_clear': (filter_clear, None),
        'filter_up': (filter_up, None),
        'builtin_filter': (builtin_filter, complete_builtin_filter),
        'filter': (filtercmd, None),
    })
    cmd.add_aliases([
        #('filter_prune', ''),
        ('scope_list', 'sls'),
        #('scope_delete', ''),
        ('scope_reset', 'sr'),
        #('scope_save', ''),
        ('filter_list', 'fls'),
        ('filter_clear', 'fc'),
        ('filter_up', 'fu'),
        ('builtin_filter', 'fbi'),
        ('filter', 'f'),
        ('filter', 'fl'),
    ])
