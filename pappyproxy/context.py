from pappyproxy import http
from twisted.internet import defer
from util import PappyException
import crochet
import shlex
import datetime
import re


"""
context.py

Functions and classes involved with managing the current context and filters
"""

scope = []
base_filters = []
active_filters = []
active_requests = set()
inactive_requests = set()
all_reqs = set()
in_memory_requests = set()
next_in_mem_id = 1

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
    def get(name):
        if name not in BuiltinFilters._filters:
            raise PappyException('%s not a bult in filter' % name)
        if name in BuiltinFilters._filters:
            return [Filter(f) for f in BuiltinFilters._filters[name][0]]

    @staticmethod
    def list():
        return [k for k, v in BuiltinFilters._filters.iteritems()]

    @staticmethod
    def help(name):
        if name not in BuiltinFilters._filters:
            raise PappyException('%s not a bult in filter' % name)
        return Filter(BuiltinFilters._filters[name][1])

class FilterParseError(PappyException):
    pass

class Filter(object):

    def __init__(self, filter_string):
        self.filter_func = self.from_filter_string(filter_string)
        self.filter_string = filter_string

    def __call__(self, *args, **kwargs):
        return self.filter_func(*args, **kwargs)

    def __repr__(self):
        return '<Filter "%s">' % self.filter_string

    @staticmethod
    def from_filter_string(filter_string):
        args = shlex.split(filter_string)
        field = args[0]
        relation = args[1]
        new_filter = None

        negate = False
        if relation[0] == 'n' and len(relation) > 1:
            negate = True
            relation = relation[1:]

        if len(args) > 2:
            val1 = args[2]
        elif relation not in ('ex',):
            raise PappyException('%s requires a value' % relation)
        else:
            val1 = None
        if len(args) > 3:
            comp2 = args[3]
        else:
            comp2 = None
        if len(args) > 4:
            val2 = args[4]
        else:
            comp2 = None

        # Raises exception if invalid
        comparer = get_relation(relation, val1)

        if field in ("all",):
            new_filter = gen_filter_by_all(comparer, val1, negate)
        elif field in ("host", "domain", "hs", "dm"):
            new_filter = gen_filter_by_host(comparer, val1, negate)
        elif field in ("path", "pt"):
            new_filter = gen_filter_by_path(comparer, val1, negate)
        elif field in ("body", "bd", "data", "dt"):
            new_filter = gen_filter_by_body(comparer, val1, negate)
        elif field in ("verb", "vb"):
            new_filter = gen_filter_by_verb(comparer, val1, negate)
        elif field in ("param", "pm"):
            if len(args) > 4:
                comparer2 = get_relation(comp2, val2)
                new_filter = gen_filter_by_params(comparer, val1,
                                                  comparer2, val2, negate)
            else:
                new_filter = gen_filter_by_params(comparer, val1,
                                                  negate=negate)
        elif field in ("header", "hd"):
            if len(args) > 4:
                comparer2 = get_relation(comp2, val2)
                new_filter = gen_filter_by_headers(comparer, val1,
                                                   comparer2, val2, negate)
            else:
                new_filter = gen_filter_by_headers(comparer, val1,
                                                   negate=negate)
        elif field in ("rawheaders", "rh"):
            new_filter = gen_filter_by_raw_headers(comparer, val1, negate)
        elif field in ("sentcookie", "sck"):
            if len(args) > 4:
                comparer2 = get_relation(comp2, val2)
                new_filter = gen_filter_by_submitted_cookies(comparer, val1,
                                                             comparer2, val2, negate)
            else:
                new_filter = gen_filter_by_submitted_cookies(comparer, val1,
                                                             negate=negate)
        elif field in ("setcookie", "stck"):
            if len(args) > 4:
                comparer2 = get_relation(comp2, val2)
                new_filter = gen_filter_by_set_cookies(comparer, val1,
                                                       comparer2, val2, negate)
            else:
                new_filter = gen_filter_by_set_cookies(comparer, val1,
                                                       negate=negate)
        elif field in ("statuscode", "sc", "responsecode"):
            new_filter = gen_filter_by_response_code(comparer, val1, negate)
        elif field in ("responsetime", "rt"):
            pass
        elif field in ("tag", "tg"):
            new_filter = gen_filter_by_tag(comparer, val1, negate)
        elif field in ("saved", "svd"):
            new_filter = gen_filter_by_saved(comparer, val1, negate)
        else:
            raise FilterParseError("%s is not a valid field" % field)

        if new_filter is not None:
            return new_filter
        else:
            raise FilterParseError("Error creating filter")

def filter_reqs(requests, filters):
    to_delete = set()
    # Could definitely be more efficient, but it stays like this until
    # it impacts performance
    for req in requests:
        for filt in filters:
            if not filt(req):
                to_delete.add(req)
    requests = [r for r in requests if r not in to_delete]
    return (requests, list(to_delete))

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


def gen_filter_by_attr(comparer, val, attr, negate=False):
    """
    NOINDEX
    Filters by an attribute whose name is shared by the request and response
    objects
    """
    def f(req):
        req_match = comparer(getattr(req, attr), val)
        if req.response:
            rsp_match = comparer(getattr(req.response, attr), val)
        else:
            rsp_match = False

        result = req_match or rsp_match
        if negate:
            return not result
        else:
            return result

    return f

def gen_filter_by_all(comparer, val, negate=False):
    def f(req):
        req_match = comparer(req.full_request, val)
        if req.response:
            rsp_match = comparer(req.response.full_response, val)
        else:
            rsp_match = False

        result = req_match or rsp_match
        if negate:
            return not result
        else:
            return result

    return f

def gen_filter_by_host(comparer, val, negate=False):
    def f(req):
        result = comparer(req.host, val)
        if negate:
            return not result
        else:
            return result

    return f

def gen_filter_by_body(comparer, val, negate=False):
    return gen_filter_by_attr(comparer, val, 'raw_data', negate=negate)

def gen_filter_by_raw_headers(comparer, val, negate=False):
    return gen_filter_by_attr(comparer, val, 'raw_headers', negate=negate)

def gen_filter_by_response_code(comparer, val, negate=False):
    def f(req):
        if req.response:
            result = comparer(req.response.response_code, val)
        else:
            result = False
        if negate:
            return not result
        else:
            return result

    return f
        
def gen_filter_by_path(comparer, val, negate=False):
    def f(req):
        result = comparer(req.full_path, val)
        if negate:
            return not result
        else:
            return result

    return f

def gen_filter_by_responsetime(comparer, val, negate=False):
    def f(req):
        result = comparer(req.rsptime, val)
        if negate:
            return not result
        else:
            return result

    return f

def gen_filter_by_verb(comparer, val, negate=False):
    def f(req):
        result = comparer(req.verb, val)
        if negate:
            return not result
        else:
            return result

    return f

def gen_filter_by_tag(comparer, val, negate=False):
    def f(req):
        result = False
        for tag in req.tags:
            if comparer(tag, val):
                result = True
                break
        if negate:
            return not result
        else:
            return result

    return f

def gen_filter_by_saved(comparer, val, negate=False):
    def f(req):
        result = False
        if req.saved:
            result = comparer('true', val)
        else:
            result = comparer('false', val)
        if negate:
            return not result
        else:
            return result

    return f
                

def check_repeatable_dict(d, comparer1, val1, comparer2=None, val2=None, negate=False):
    result = False
    for k, v in d.all_pairs():
        if comparer2:
            key_matches = comparer1(k, val1)
            val_matches = comparer2(v, val2)
            if key_matches and val_matches:
                result = True
                break
        else:
            # We check if the first value matches either
            key_matches = comparer1(k, val1)
            val_matches = comparer1(v, val1)
            if key_matches or val_matches:
                result = True
                break
    if negate:
        return not result
    else:
        return result

def gen_filter_by_repeatable_dict_attr(attr, keycomparer, keyval, valcomparer=None,
                                       valval=None, negate=False, check_req=True,
                                       check_rsp=True):
    def f(req):
        matched = False
        d = getattr(req, attr)
        if check_req and check_repeatable_dict(d, keycomparer, keyval, valcomparer, valval):
            matched = True
        if check_rsp and req.response:
            d = getattr(req.response, attr)
            if check_repeatable_dict(d, keycomparer, keyval, valcomparer, valval):
                matched = True
        if negate:
            return not matched
        else:
            return matched

    return f

def gen_filter_by_headers(keycomparer, keyval, valcomparer=None, valval=None,
                          negate=False):
    return gen_filter_by_repeatable_dict_attr('headers', keycomparer, keyval,
                                              valcomparer, valval, negate=negate)

def gen_filter_by_submitted_cookies(keycomparer, keyval, valcomparer=None,
                                    valval=None, negate=False):
    return gen_filter_by_repeatable_dict_attr('cookies', keycomparer, keyval,
                                              valcomparer, valval, negate=negate,
                                              check_rsp=False)

def gen_filter_by_set_cookies(keycomparer, keyval, valcomparer=None,
                              valval=None, negate=False):
    def f(req):
        if not req.response:
            return False

        for k, c in req.response.cookies.all_pairs():
            if keycomparer(c.key, keyval):
                if not valcomparer:
                    return True
                else:
                    if valcomparer(c.val, valval):
                        return True
                
        return False

    return f

def gen_filter_by_url_params(keycomparer, keyval, valcomparer=None, valval=None,
                         negate=False):
    def f(req):
        matched = False
        for k, v in req.url_params.all_pairs():
            if keycomparer(k, keyval):
                if not valcomparer:
                    matched = True
                else:
                    if valcomparer(v, valval):
                        matched = True
        if negate:
            return not matched
        else:
            return matched

    return f

def gen_filter_by_post_params(keycomparer, keyval, valcomparer=None, valval=None,
                         negate=False):
    def f(req):
        matched = False
        for k, v in req.post_params.all_pairs():
            if keycomparer(k, keyval):
                if not valcomparer:
                    matched = True
                else:
                    if valcomparer(v, valval):
                        matched = True
        if negate:
            return not matched
        else:
            return matched


    return f

def gen_filter_by_params(keycomparer, keyval, valcomparer=None, valval=None,
                         negate=False):
    def f(req):
        matched = False
        # purposely don't pass negate here, otherwise we get double negatives
        f1 = gen_filter_by_post_params(keycomparer, keyval, valcomparer, valval)
        f2 = gen_filter_by_url_params(keycomparer, keyval, valcomparer, valval)
        if f1(req):
            matched = True
        if f2(req):
            matched = True

        if negate:
            return not matched
        else:
            return matched

    return f

def get_relation(s, val):
    # Gets the relation function associated with the string
    # Returns none if not found
    if s in ("is",):
        return cmp_is
    elif s in ("contains", "ct"):
        return cmp_contains
    elif s in ("containsr", "ctr"):
        validate_regexp(val)
        return cmp_containsr
    elif s in ("exists", "ex"):
        return cmp_exists
    elif s in ("Leq",):
        return cmp_len_eq
    elif s in ("Lgt",):
        return cmp_len_gt
    elif s in ("Llt",):
        return cmp_len_lt
    elif s in ("eq",):
        return cmp_eq
    elif s in ("gt",):
        return cmp_gt
    elif s in ("lt",):
        return cmp_lt

    raise FilterParseError("Invalid relation: %s" % s)

@defer.inlineCallbacks
def init():
    yield reload_from_storage()

@defer.inlineCallbacks
def reload_from_storage():
    global active_requests
    global all_reqs
    active_requests = set()
    inactive_requests = set()
    all_reqs = set()
    reqs = yield http.Request.load_all_requests()
    for req in reqs:
        add_request(req)
        
def update_active_requests():
    global active_requests
    global all_reqs

    inactive_requests = set()
    active_requests = set()
    for req in all_reqs:
        add_request(req)
    
def add_filter(filt):
    global active_requests
    global active_filters
    active_filters.append(filt)
    (active_requests, deleted) = filter_reqs(active_requests, active_filters)
    for r in deleted:
        inactive_requests.add(r)
    
def add_request(req):
    global active_requests
    global active_filters
    global in_memory_requests
    global all_reqs

    # Check if we have to add it to in_memory
    if not req.reqid:
        req.reqid = get_memid()
    if req.reqid[0] == 'm':
        in_memory_requests.add(req)

    # Check if we have to add it to active_requests
    if passes_filters(req, active_filters):
        active_requests.add(req)
    else:
        inactive_requests.add(req)

    # Add it to all_reqs
    all_reqs.add(req)
    
def remove_request(req):
    global in_memory_requests
    global inactive_requests
    global active_requests
    global all_reqs

    if req in in_memory_requests:
        in_memory_requests.remove(req)
    if req in inactive_requests:
        inactive_requests.remove(req)
    if req in active_requests:
        active_requests.remove(req)
    if req in all_reqs:
        all_reqs.remove(req)

def filter_recheck():
    global active_requests
    global inactive_requests
    global all_reqs
    active_requests = set()
    inactive_requests = set()
    for req in all_reqs:
        if passes_filters(req, active_filters):
            active_requests.add(req)
        else:
            inactive_requests.add(req)
    
def passes_filters(request, filters):
    for filt in filters:
        if not filt(request):
            return False
    return True

def in_scope(request):
    global scope
    return passes_filters(request, scope)
    
def set_scope(filters):
    global scope
    scope = filters
    
def save_scope():
    global active_filters
    global scope
    scope = active_filters[:]

def reset_to_scope():
    global scope
    global active_filters
    active_filters = scope[:]
    update_active_requests()
    
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
        new_scope.append(new_filter)
    scope = new_scope

def get_memid():
    global next_in_mem_id
    i = 'm%d' % next_in_mem_id
    next_in_mem_id += 1
    return i

@defer.inlineCallbacks
def clear_tag(tag):
    # Remove a tag from every request
    reqs = yield http.Request.load_requests_by_tag(tag)
    for req in reqs:
        req.tags.remove(tag)
        if req.saved:
            yield req.async_save()
    filter_recheck()

@defer.inlineCallbacks
def async_set_tag(tag, reqs):
    """
    async_set_tag(tag, reqs)
    Remove the tag from every request then add the given requests to memory and
    give them the tag.
    """
    yield clear_tag(tag)
    for req in reqs:
        if not req.reqid:
            req.reqid = get_memid()
        req.tags.append(tag)
        add_request(req)

@crochet.wait_for(timeout=180.0)
@defer.inlineCallbacks
def set_tag(tag, reqs):
    yield async_set_tag(tag, reqs)

def validate_regexp(r):
    try:
        re.compile(r)
    except re.error as e:
        raise PappyException('Invalid regexp: %s' % e)

def filter_up():
    # Deletes the last filter of the context
    global active_filters
    if active_filters:
        active_filters = active_filters[:-1]
        filter_recheck()
