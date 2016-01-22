import crochet
import pappyproxy
import re
import shlex

from .http import Request, RepeatableDict
from .requestcache import RequestCache
from twisted.internet import defer
from util import PappyException

"""
context.py

Functions and classes involved with managing the current context and filters
"""

scope = []
_BARE_COMPARERS = ('ex','nex')

class Context(object):
    """
    A class representing a set of requests that pass a set of filters

    :ivar active_filters: Filters that are currently applied to the context
    :vartype active_filters: List of functions that takes one :class:`pappyproxy.http.Request` and returns either true or false.
    :ivar active_requests: Requests which pass all the filters applied to the context
    :type active_requests: Request
    :ivar inactive_requests: Requests which do not pass all the filters applied to the context
    :type inactive_requests: Request
    """

    def __init__(self):
        self.active_filters = []
        self.complete = True
        self.active_requests = []

    @staticmethod
    def get_memid():
        i = 'm%d' % Context._next_in_mem_id
        Context._next_in_mem_id += 1
        return i

    def cache_reset(self):
        self.active_requests = []
        self.complete = False
        
    def add_filter(self, filt):
        """
        Add a filter to the context. This will remove any requests that do not pass
        the filter from the ``active_requests`` set.

        :param filt: The filter to add
        :type filt: Function that takes one :class:`pappyproxy.http.Request` and returns either true or false. (or a :class:`pappyproxy.context.Filter`)
        """
        self.active_filters.append(filt)
        self.cache_reset()

    def filter_up(self):
        """
        Removes the last filter that was applied to the context.
        """
        # Deletes the last filter of the context
        if self.active_filters:
            self.active_filters = self.active_filters[:-1]
        self.cache_reset()

    def set_filters(self, filters):
        """
        Set the list of filters for the context.
        """
        self.active_filters = filters[:]
        self.cache_reset()

    @defer.inlineCallbacks
    def get_reqs(self, n=-1):
        # This is inefficient but I want it to work for now, and as long as we
        # don't put the full requests in memory I don't care.
        ids = self.active_requests
        if (len(ids) >= n and n != -1) or self.complete == True:
            if n == -1:
                defer.returnValue(ids)
            else:
                defer.returnValue(ids[:n])
        ids = []
        for req_d in Request.cache.req_it():
            r = yield req_d
            passed = True
            for filt in self.active_filters:
                if not filt(r):
                    passed = False
                    break
            if passed:
                self.active_requests.append(r.reqid)
                ids.append(r.reqid)
            if len(ids) >= n and n != -1:
                defer.returnValue(ids[:n])
        self.complete = True
        defer.returnValue(ids)

class FilterParseError(PappyException):
    pass

class Filter(object):
    """
    A class representing a filter. Its claim to fame is that you can use
    :func:`pappyproxy.context.Filter.from_filter_string` to generate a
    filter from a filter string.
    """

    def __init__(self, filter_string):
        self.filter_string = filter_string

    def __call__(self, *args, **kwargs):
        return self.filter_func(*args, **kwargs)

    def __repr__(self):
        return '<Filter "%s">' % self.filter_string

    @defer.inlineCallbacks
    def generate(self):
        self.filter_func = yield self.from_filter_string(self.filter_string)

    @staticmethod
    @defer.inlineCallbacks
    def from_filter_string(filter_string):
        """
        from_filter_string(filter_string)

        Create a filter from a filter string.

        :rtype: Deferred that returns a :class:`pappyproxy.context.Filter`
        """
        args = shlex.split(filter_string)
        if len(args) == 0:
            raise PappyException('Field is required')
        field = args[0]
        new_filter = None

        field_args = args[1:]
        if field in ("all",):
            new_filter = gen_filter_by_all(field_args)
        elif field in ("host", "domain", "hs", "dm"):
            new_filter = gen_filter_by_host(field_args)
        elif field in ("path", "pt"):
            new_filter = gen_filter_by_path(field_args)
        elif field in ("body", "bd", "data", "dt"):
            new_filter = gen_filter_by_body(field_args)
        elif field in ("verb", "vb"):
            new_filter = gen_filter_by_verb(field_args)
        elif field in ("param", "pm"):
            new_filter = gen_filter_by_params(field_args)
        elif field in ("header", "hd"):
            new_filter = gen_filter_by_headers(field_args)
        elif field in ("rawheaders", "rh"):
            new_filter = gen_filter_by_raw_headers(field_args)
        elif field in ("sentcookie", "sck"):
            new_filter = gen_filter_by_submitted_cookies(field_args)
        elif field in ("setcookie", "stck"):
            new_filter = gen_filter_by_set_cookies(field_args)
        elif field in ("statuscode", "sc", "responsecode"):
            new_filter = gen_filter_by_response_code(field_args)
        elif field in ("responsetime", "rt"):
            raise PappyException('Not implemented yet, sorry!')
        elif field in ("tag", "tg"):
            new_filter = gen_filter_by_tag(field_args)
        elif field in ("saved", "svd"):
            new_filter = gen_filter_by_saved(field_args)
        elif field in ("before", "b4", "bf"):
            new_filter = yield gen_filter_by_before(field_args)
        elif field in ("after", "af"):
            new_filter = yield gen_filter_by_after(field_args)
        else:
            raise FilterParseError("%s is not a valid field" % field)

        if new_filter is None:
            raise FilterParseError("Error creating filter")
        # dirty hack to get it to work if we don't generate any deferreds
        # d = defer.Deferred()
        # d.callback(None)
        # yield d
        defer.returnValue(new_filter)

def cmp_is(a, b):
    return str(a) == str(b)

def cmp_contains(a, b):
    return (b.lower() in a.lower())

def cmp_exists(a, b=None):
    return (a is not None and a != [])

def cmp_len_eq(a, b):
    return (len(a) == int(b))

def cmp_len_gt(a, b):
    return (len(a) > int(b))

def cmp_len_lt(a, b):
    return (len(a) < int(b))

def cmp_eq(a, b):
    return (int(a) == int(b))

def cmp_gt(a, b):
    return (int(a) > int(b))

def cmp_lt(a, b):
    return (int(a) < int(b))

def cmp_containsr(a, b):
    try:
        if re.search(b, a):
            return True
        return False
    except re.error as e:
        raise PappyException('Invalid regexp: %s' % e)

def relation_from_text(s, val=''):
    # Gets the relation function associated with the string
    # Returns none if not found

    def negate_func(func):
        def f(*args, **kwargs):
            return not func(*args, **kwargs)
        return f

    negate = False
    if s[0] == 'n':
        negate = True
        s = s[1:]

    if s in ("is",):
        retfunc = cmp_is
    elif s in ("contains", "ct"):
        retfunc = cmp_contains
    elif s in ("containsr", "ctr"):
        validate_regexp(val)
        retfunc = cmp_containsr
    elif s in ("exists", "ex"):
        retfunc = cmp_exists
    elif s in ("Leq",):
        retfunc = cmp_len_eq
    elif s in ("Lgt",):
        retfunc = cmp_len_gt
    elif s in ("Llt",):
        retfunc = cmp_len_lt
    elif s in ("eq",):
        retfunc = cmp_eq
    elif s in ("gt",):
        retfunc = cmp_gt
    elif s in ("lt",):
        retfunc = cmp_lt
    else:
        raise FilterParseError("Invalid relation: %s" % s)

    if negate:
        return negate_func(retfunc)
    else:
        return retfunc
    
def compval_from_args(args):
    """
    NOINDEX
    returns a function that compares to a value from text.
    ie compval_from_text('ct foo') will return a function that returns true
    if the passed in string contains foo.
    """
    if len(args) == 0:
        raise PappyException('Invalid number of arguments')
    if args[0] in _BARE_COMPARERS:
        if len(args) != 1:
            raise PappyException('Invalid number of arguments')
        comparer = relation_from_text(args[0], None)
        value = None
    else:
        if len(args) != 2:
            raise PappyException('Invalid number of arguments')
        comparer = relation_from_text(args[0], args[1])
        value = args[1]

    def retfunc(s):
        return comparer(s, value)

    return retfunc

def compval_from_args_repdict(args):
    """
    NOINDEX
    Similar to compval_from_args but checks a repeatable dict with up to 2
    comparers and values.
    """
    if len(args) == 0:
        raise PappyException('Invalid number of arguments')
    nextargs = args[:]
    value = None
    if args[0] in _BARE_COMPARERS:
        comparer = relation_from_text(args[0], None)
        if len(args) > 1:
            nextargs = args[1:]
    else:
        if len(args) == 1:
            raise PappyException('Invalid number of arguments')
        comparer = relation_from_text(args[0], args[1])
        value = args[1]
        nextargs = args[2:]

    comparer2 = None
    value2 = None
    if nextargs:
        if nextargs[0] in _BARE_COMPARERS:
            comparer2 = relation_from_text(nextargs[0], None)
        else:
            if len(nextargs) == 1:
                raise PappyException('Invalid number of arguments')
            comparer2 = relation_from_text(nextargs[0], nextargs[1])
            value2 = nextargs[1]

    def retfunc(d):
        for k, v in d.all_pairs():
            if comparer2 is None:
                if comparer(k, value) or comparer(v, value):
                    return True
            else:
                if comparer(k, value) and comparer2(v, value2):
                    return True
        return False

    return retfunc

def gen_filter_by_all(args):
    compval_from_args(args) # try and throw an error
    def f(req):
        compval = compval_from_args(args)
        if args[0][0] == 'n':
            return compval(req.full_message) and (not req.response or compval(req.response.full_message))
        else:
            return compval(req.full_message) or (req.response and compval(req.response.full_message))
    return f

def gen_filter_by_host(args):
    compval_from_args(args) # try and throw an error
    def f(req):
        compval = compval_from_args(args)
        return compval(req.host)
    return f

def gen_filter_by_body(args):
    compval_from_args(args) # try and throw an error
    def f(req):
        compval = compval_from_args(args)
        if args[0][0] == 'n':
            return compval(req.body) and (not req.response or compval(req.response.body))
        else:
            return compval(req.body) or (req.response and compval(req.response.body))
    return f

def gen_filter_by_raw_headers(args):
    compval_from_args(args) # try and throw an error
    def f(req):
        compval = compval_from_args(args)
        if args[0][0] == 'n':
            return compval(req.headers_section) and (not req.response or compval(req.response.headers_section))
        else:
            return compval(req.headers_section) or (req.response and compval(req.response.headers_section))
    return f

def gen_filter_by_response_code(args):
    compval_from_args(args) # try and throw an error
    def f(req):
        if not req.response:
            return False
        compval = compval_from_args(args)
        return compval(req.response.response_code)
    return f
        
def gen_filter_by_path(args):
    compval_from_args(args)
    def f(req):
        compval = compval_from_args(args)
        return compval(req.path)
    return f

def gen_filter_by_responsetime(args):
    compval_from_args(args)
    def f(req):
        compval = compval_from_args(args)
        return compval(req.rsptime)
    return f

def gen_filter_by_verb(args):
    compval_from_args(args)
    def f(req):
        compval = compval_from_args(args)
        return compval(req.verb)
    return f

def gen_filter_by_tag(args):
    compval_from_args(args)
    def f(req):
        compval = compval_from_args(args)
        for tag in req.tags:
            if compval(tag):
                return True
        return False
    return f

def gen_filter_by_saved(args):
    if len(args) != 0:
        raise PappyException('Invalid number of arguments')
    def f(req):
        if req.saved:
            return True
        else:
            return False
    return f
                
@defer.inlineCallbacks
def gen_filter_by_before(args):
    if len(args) != 1:
        raise PappyException('Invalid number of arguments')
    r = yield http.Request.load_request(args[0])
    def f(req):
        if req.time_start is None:
            return False
        if r.time_start is None:
            return False
        return req.time_start <= r.time_start
    defer.returnValue(f)

@defer.inlineCallbacks
def gen_filter_by_after(reqid, negate=False):
    if len(args) != 1:
        raise PappyException('Invalid number of arguments')
    r = yield http.Request.load_request(args[0])
    def f(req):
        if req.time_start is None:
            return False
        if r.time_start is None:
            return False
        return req.time_start >= r.time_start
    defer.returnValue(f)

def gen_filter_by_headers(args):
    comparer = compval_from_args_repdict(args)
    def f(req):
        if args[0][0] == 'n':
            return comparer(req.headers) and (not req.response or comparer(req.response.headers))
        else:
            return comparer(req.headers) and (req.response and comparer(req.response.headers))
    return f

def gen_filter_by_submitted_cookies(args):
    comparer = compval_from_args_repdict(args)
    def f(req):
        return comparer(req.cookies)
    return f
    
def gen_filter_by_set_cookies(args):
    comparer = compval_from_args_repdict(args)
    def f(req):
        if not req.response:
            return False
        checkdict = RepeatableDict()
        for k, v in req.response.cookies.all_pairs():
            checkdict[k] = v.cookie_str
        return comparer(checkdict)
    return f

def gen_filter_by_url_params(args):
    comparer = compval_from_args_repdict(args)
    def f(req):
        return comparer(req.url_params)
    return f

def gen_filter_by_post_params(args):
    comparer = compval_from_args_repdict(args)
    def f(req):
        return comparer(req.post_params)
    return f

def gen_filter_by_params(args):
    comparer = compval_from_args_repdict(args)
    def f(req):
        return comparer(req.url_params) or comparer(req.post_params)
    return f

@defer.inlineCallbacks
def filter_reqs(reqids, filters):
    to_delete = set()
    # Could definitely be more efficient, but it stays like this until
    # it impacts performance
    requests = []
    for reqid in reqids:
        r = yield Request.load_request(reqid)
        requests.append(r)
    for req in requests:
        for filt in filters:
            if not filt(req):
                to_delete.add(req)
    retreqs = []
    retdel = []
    for r in requests:
        if r in to_delete:
            retdel.append(r.reqid)
        else:
            retreqs.append(r.reqid)
    defer.returnValue((retreqs, retdel))

def passes_filters(request, filters):
    for filt in filters:
        if not filt(request):
            return False
    return True

def in_scope(request):
    global scope
    passes = passes_filters(request, scope)
    return passes
    
def set_scope(filters):
    global scope
    scope = filters
    
def save_scope(context):
    global scope
    scope = context.active_filters[:]

def reset_to_scope(context):
    global scope
    context.active_filters = scope[:]
    context.cache_reset()
    
def print_scope():
    global scope
    for f in scope:
        print f.filter_string

@defer.inlineCallbacks
def store_scope(dbpool):
    # Delete the old scope
    yield dbpool.runQuery(
        """
        DELETE FROM scope
        """
    );

    # Insert the new scope
    i = 0
    for f in scope:
        yield dbpool.runQuery(
            """
            INSERT INTO scope (filter_order, filter_string) VALUES (?, ?);
            """,
            (i, f.filter_string)
        );
        i += 1
        
@defer.inlineCallbacks
def load_scope(dbpool):
    global scope
    rows = yield dbpool.runQuery(
            """
            SELECT filter_order, filter_string FROM scope;
            """,
        )
    rows = sorted(rows, key=lambda r: int(r[0]))
    new_scope = []
    for row in rows:
        new_filter = Filter(row[1])
        yield new_filter.generate()
        new_scope.append(new_filter)
    scope = new_scope

@defer.inlineCallbacks
def clear_tag(tag):
    # Remove a tag from every request
    reqs = yield Request.cache.load_by_tag(tag)
    for req in reqs:
        req.tags.remove(tag)
        if req.saved:
            yield req.async_save()
    reset_context_caches()

@defer.inlineCallbacks
def async_set_tag(tag, reqs):
    """
    async_set_tag(tag, reqs)
    Remove the tag from every request then add the given requests to memory and
    give them the tag. The async version.

    :param tag: The tag to set
    :type tag: String
    :param reqs: The requests to assign to the tag
    :type reqs: List of Requests
    """
    yield clear_tag(tag)
    for req in reqs:
        req.tags.append(tag)
        Request.cache.add(req)
    reset_context_caches()

@crochet.wait_for(timeout=180.0)
@defer.inlineCallbacks
def set_tag(tag, reqs):
    """
    set_tag(tag, reqs)
    Remove the tag from every request then add the given requests to memory and
    give them the tag. The non-async version.

    :param tag: The tag to set
    :type tag: String
    :param reqs: The requests to assign to the tag
    :type reqs: List of Requests
    """
    yield async_set_tag(tag, reqs)

def validate_regexp(r):
    try:
        re.compile(r)
    except re.error as e:
        raise PappyException('Invalid regexp: %s' % e)

def reset_context_caches():
    import pappyproxy.pappy
    for c in pappyproxy.pappy.all_contexts:
        c.cache_reset()
