from itertools import groupby

from ..proxy import InvalidQuery, time_to_nsecs
from ..colors import Colors, Styles

# class BuiltinFilters(object):
#     _filters = {
#         'not_image': (
#             ['path nctr "(\.png$|\.jpg$|\.gif$)"'],
#             'Filter out image requests',
#         ),
#         'not_jscss': (
#             ['path nctr "(\.js$|\.css$)"'],
#             'Filter out javascript and css files',
#         ),
#     }
    
#     @staticmethod
#     @defer.inlineCallbacks
#     def get(name):
#         if name not in BuiltinFilters._filters:
#             raise PappyException('%s not a bult in filter' % name)
#         if name in BuiltinFilters._filters:
#             filters = [pappyproxy.context.Filter(f) for f in BuiltinFilters._filters[name][0]]
#             for f in filters:
#                 yield f.generate()
#             defer.returnValue(filters)
#         raise PappyException('"%s" is not a built-in filter' % name)

#     @staticmethod
#     def list():
#         return [k for k, v in BuiltinFilters._filters.iteritems()]

#     @staticmethod
#     def help(name):
#         if name not in BuiltinFilters._filters:
#             raise PappyException('"%s" is not a built-in filter' % name)
#         return pappyproxy.context.Filter(BuiltinFilters._filters[name][1])


# def complete_filtercmd(text, line, begidx, endidx):
#     strs = [k for k, v in pappyproxy.context.Filter._filter_functions.iteritems()]
#     strs += [k for k, v in pappyproxy.context.Filter._async_filter_functions.iteritems()]
#     return autocomplete_startswith(text, strs)
    
# def complete_builtin_filter(text, line, begidx, endidx):
#     all_names = BuiltinFilters.list()
#     if not text:
#         ret = all_names[:]
#     else:
#         ret = [n for n in all_names if n.startswith(text)]
#     return ret
    
# @crochet.wait_for(timeout=None)
# @defer.inlineCallbacks
# def builtin_filter(line):
#     if not line:
#         raise PappyException("Filter name required")
    
#     filters_to_add = yield BuiltinFilters.get(line)
#     for f in filters_to_add:
#         print f.filter_string
#         yield pappyproxy.pappy.main_context.add_filter(f)
#     defer.returnValue(None)

def filtercmd(client, args):
    """
    Apply a filter to the current context
    Usage: filter <filter string>
    See README.md for information on filter strings
    """
    try:
        phrases = [list(group) for k, group in groupby(args, lambda x: x == "OR") if not k]
        for phrase in phrases:
            # we do before/after by id not by timestamp
            if phrase[0] in ('before', 'b4', 'after', 'af') and len(phrase) > 1:
                r = client.req_by_id(phrase[1], headers_only=True)
                phrase[1] = str(time_to_nsecs(r.time_start))
        client.context.apply_phrase(phrases)
    except InvalidQuery as e:
        print(e)

def filter_up(client, args):
    """
    Remove the last applied filter
    Usage: filter_up
    """
    client.context.pop_phrase()

def filter_clear(client, args):
    """
    Reset the context so that it contains no filters (ignores scope)
    Usage: filter_clear
    """
    client.context.set_query([])

def filter_list(client, args):
    """
    Print the filters that make up the current context
    Usage: filter_list
    """
    from ..util import print_query
    print_query(client.context.query)

def scope_save(client, args):
    """
    Set the scope to be the current context. Saved between launches
    Usage: scope_save
    """
    client.set_scope(client.context.query)

def scope_reset(client, args):
    """
    Set the context to be the scope (view in-scope items)
    Usage: scope_reset
    """
    result = client.get_scope()
    if result.is_custom:
        print("Proxy is using a custom function to check scope. Cannot set context to scope.")
        return
    client.context.set_query(result.filter)

def scope_delete(client, args):
    """
    Delete the scope so that it contains all request/response pairs
    Usage: scope_delete
    """
    client.set_scope([])

def scope_list(client, args):
    """
    Print the filters that make up the scope
    Usage: scope_list
    """
    from ..util import print_query
    result = client.get_scope()
    if result.is_custom:
        print("Proxy is using a custom function to check scope")
        return
    print_query(result.filter)

def list_saved_queries(client, args):
    from ..util import print_query
    queries = client.all_saved_queries()
    print('')
    for q in queries:
        print(Styles.TABLE_HEADER + q.name + Colors.ENDC)
        print_query(q.query)
        print('')

def save_query(client, args):
    from ..util import print_query
    if len(args) != 1:
        print("Must give name to save filters as")
        return
    client.save_query(args[0], client.context.query)
    print('')
    print(Styles.TABLE_HEADER + args[0] + Colors.ENDC)
    print_query(client.context.query)
    print('')

def load_query(client, args):
    from ..util import print_query
    if len(args) != 1:
        print("Must give name of query to load")
        return
    new_query = client.load_query(args[0])
    client.context.set_query(new_query)
    print('')
    print(Styles.TABLE_HEADER + args[0] + Colors.ENDC)
    print_query(new_query)
    print('')

def delete_query(client, args):
    if len(args) != 1:
        print("Must give name of filter")
        return
    client.delete_query(args[0])

# @crochet.wait_for(timeout=None)
# @defer.inlineCallbacks
# def filter_prune(line):
#     """
#     Delete all out of context requests from the data file. 
#     CANNOT BE UNDONE!! Be careful!
#     Usage: filter_prune
#     """
#     # Delete filtered items from datafile
#     print ''
#     print 'Currently active filters:'
#     for f in pappyproxy.pappy.main_context.active_filters:
#         print '> %s' % f.filter_string

#     # We copy so that we're not removing items from a set we're iterating over
#     act_reqs = yield pappyproxy.pappy.main_context.get_reqs()
#     inact_reqs = set(Request.cache.req_ids()).difference(set(act_reqs))
#     message = 'This will delete %d/%d requests. You can NOT undo this!! Continue?' % (len(inact_reqs), (len(inact_reqs) + len(act_reqs)))
#     #print message
#     if not confirm(message, 'n'):
#         defer.returnValue(None)
    
#     for reqid in inact_reqs:
#         try:
#             req = yield pappyproxy.http.Request.load_request(reqid)
#             yield req.deep_delete()
#         except PappyException as e:
#             print e
#     print 'Deleted %d requests' % len(inact_reqs)
#     defer.returnValue(None)

###############
## Plugin hooks

def load_cmds(cmd):
    cmd.set_cmds({
        #'filter': (filtercmd, complete_filtercmd),
        'filter': (filtercmd, None),
        'filter_up': (filter_up, None),
        'filter_list': (filter_list, None),
        'filter_clear': (filter_clear, None),
        'scope_list': (scope_list, None),
        'scope_delete': (scope_delete, None),
        'scope_reset': (scope_reset, None),
        'scope_save': (scope_save, None),
        'list_saved_queries': (list_saved_queries, None),
        # 'filter_prune': (filter_prune, None),
        # 'builtin_filter': (builtin_filter, complete_builtin_filter),
        'save_query': (save_query, None),
        'load_query': (load_query, None),
        'delete_query': (delete_query, None),
    })
    cmd.add_aliases([
        ('filter', 'f'),
        ('filter', 'fl'),
        ('filter_up', 'fu'),
        ('filter_list', 'fls'),
        ('filter_clear', 'fc'),
        ('scope_list', 'sls'),
        ('scope_reset', 'sr'),
        ('list_saved_queries', 'sqls'),
        # ('builtin_filter', 'fbi'),
        ('save_query', 'sq'),
        ('load_query', 'lq'),
        ('delete_query', 'dq'),
    ])
