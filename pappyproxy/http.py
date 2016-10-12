import StringIO
import base64
import bs4
import crochet
import datetime
import gzip
import json
import pygments
import re
import time
import urlparse
import zlib
import weakref
import Queue

from .util import PappyException, printable_data, short_data, PappyStringTransport, sha1, print_traceback
from .requestcache import RequestCache
from .colors import Colors, host_color, path_formatter
from .proxy import ProtocolProxy, make_proxied_connection, get_http_proxy_addr, start_maybe_tls
from pygments.formatters import TerminalFormatter
from pygments.lexers import get_lexer_for_mimetype, HttpLexer
from twisted.internet import defer
from autobahn.twisted.websocket import WebSocketServerFactory, WebSocketClientFactory, WebSocketServerProtocol, WebSocketClientProtocol
from autobahn.websocket.protocol import WebSocketProtocol
from autobahn.websocket.compress import PERMESSAGE_COMPRESSION_EXTENSION

ENCODE_NONE = 0
ENCODE_DEFLATE = 1
ENCODE_GZIP = 2

PATH_RELATIVE = 0
PATH_ABSOLUTE = 1
PATH_HOST = 2

dbpool = None
web_server = None

def init(pool):
    """
    Initialize the http module.

    :param pool: The ConnectionPool to use to store the request/response objects
    :type pool: SQLite ConnectionPool
    """
    from .site import PappyWebServer

    global dbpool
    global web_server
    if dbpool is None:
        dbpool = pool
    web_server = PappyWebServer()
    assert(dbpool)

def destruct():
    assert(dbpool)
    dbpool.close()
    
def _decode_encoded(data, encoding):
    if encoding == ENCODE_NONE:
        return data

    if encoding == ENCODE_DEFLATE:
        dec_data = zlib.decompress(data, -15)
    else:
        dec_data = gzip.GzipFile('', 'rb', 9, StringIO.StringIO(data))
        dec_data = dec_data.read()
    return dec_data

def _strip_leading_newlines(string):
    while (len(string) > 1 and string[0:2] == '\r\n') or \
            (len(string) > 0 and string[0] == '\n'):
        if len(string) > 1 and string[0:2] == '\r\n':
            string = string[2:]
        elif len(string) > 0 and string[0] == '\n':
            string = string[1:]
    return string

def _consume_line(instr):
    # returns (line, rest)
    l = []
    pos = 0
    while pos < len(instr):
        if instr[pos] == '\n':
            if l and l[-1] == '\r':
                l = l[:-1]
            return (''.join(l), instr[pos+1:])
        l.append(instr[pos])
        pos += 1
    return (instr, '')

###################
## Functions to use

def get_request(url='', url_params={}):
    """
    get_request(url='', url_params={})

    Create a request object that makes a GET request to the given url with the
    given url params.
    """
    r = Request()
    r.start_line = 'GET / HTTP/1.1'
    r.url = url
    r.headers['Host'] = r.host
    if url_params:
        r.url_params.from_dict(url_params)
    return r

def post_request(url, post_params={}, url_params={}):
    """
    post_request(url, post_params={}, url_params={})

    Create a request object that makes a POST request to the given url with the
    given post and url params.
    """
    r = Request()
    r.start_line = 'POST / HTTP/1.1'
    r.url = url
    r.headers['Host'] = r.host
    if url_params:
        r.url_params.from_dict(url_params)
    if post_params:
        r.post_params.from_dict(post_params)
    return r

def repeatable_parse_qs(s):
    pairs = s.split('&')
    ret_dict = RepeatableDict()
    for pair in pairs:
        if '=' in pair:
            t = tuple(pair.split('=', 1))
            ret_dict.append(t[0], t[1])
        else:
            ret_dict.append(pair, None)
    return ret_dict

@crochet.wait_for(timeout=180.0)
@defer.inlineCallbacks
def request_by_id(reqid):
    req = yield Request.load_request(str(reqid))
    defer.returnValue(req)
    
@defer.inlineCallbacks
def async_submit_requests(reqs, mangle=False, save=False, save_in_mem=False, unique_paths=False,
                          unique_path_and_args=False, use_cookie_jar=False, tag=None):
    """
    async_submit_requests(reqs, mangle=False)
    :param mangle: Whether to pass the requests through intercepting macros
    :type mangle: Bool
    :rtype: DeferredList

    Copies and submits a list of requests at the same time asynchronously.
    Responses/unmangled versions will be attached to the request objects in the list.
    Prints progress to stdout.
    Returns list of submitted requests
    """
    import sys
    from pappyproxy.plugin import add_to_history

    if unique_paths and unique_path_and_args:
        raise PappyException("Cannot use both unique_paths and unique_paths_and_argts")
    if save and save_in_mem:
        raise PappyException("Cannot use both save and save_in_mem")

    to_submit = [r.copy() for r in reqs]

    if unique_paths or unique_path_and_args:
        endpoints = set()
        new_reqs = []
        for r in reqs:
            if unique_path_and_args:
                s = r.url
            else:
                s = r.path

            if not s in endpoints:
                new_reqs.append(r)
                endpoints.add(s)
        to_submit = new_reqs

    print 'Submitting %d request(s)' % len(to_submit)
    sys.stdout.flush()

    dones = 0
    errors = 0
    list_deferred = defer.Deferred()

    deferreds = []
    for r in to_submit:
        if tag is not None:
            r.tags.add(tag)
        d = r.async_submit(mangle=mangle)
        deferreds.append(d)

    # Really not the best way to do this. If one request hangs forever the whole thing will
    # just hang in the middle
    for d in deferreds:
        try:
            yield d
            dones += 1
        except Exception as e:
            errors += 1
            print e

        finished = dones+errors
        
        if finished % 30 == 0 or finished == len(to_submit):
            if errors > 0:
                print '{0}/{1} complete with {3} errors ({2:.2f}%)'.format(finished, len(to_submit), (float(finished)/len(to_submit))*100, errors)
            else:
                print '{0}/{1} complete ({2:.2f}%)'.format(finished, len(to_submit), (float(finished)/len(to_submit))*100)
        sys.stdout.flush()
        if finished == len(to_submit):
            list_deferred.callback(None)

    if save:
        for r in to_submit:
            yield r.async_deep_save()
    elif save_in_mem:
        for r in to_submit:
            add_to_history(r)

@crochet.wait_for(timeout=180.0)
@defer.inlineCallbacks
def submit_requests(*args, **kwargs):
    ret = yield async_submit_requests(*args, **kwargs)
    defer.returnValue(ret)

def apply_http_proxy_creds(req):
    from pappyproxy import pappy

    if not pappy.session.config.http_proxy:
        return
    if 'username' in pappy.session.config.http_proxy and \
       'password' in pappy.session.config.http_proxy:
        req.proxy_creds = (pappy.session.config.http_proxy['username'],
                           pappy.session.config.http_proxy['password'])

@defer.inlineCallbacks
def handle_webserver_request(req):
    global web_server
    yield web_server.handle_request(req)

##########
## Classes

class RepeatableDict:
    """
    A dict that retains the order of items inserted and keeps track of
    duplicate values. Can optionally treat keys as case insensitive.
    Custom made for the proxy, so it has strange features
    """

    def __init__(self, from_pairs=None, case_insensitive=False):
        # If efficiency becomes a problem, add a dict that keeps a list by key
        # and use that for getting data. But until then, this stays.
        self._pairs = []
        self._keys = set()
        self._modify_callback = None
        self.case_insensitive = case_insensitive

        if from_pairs:
            for k, v in from_pairs:
                self.append(k, v)

    def _ef_key(self, key):
        # "effective key", returns key.lower() if we're case insensitive,
        # otherwise it returns the same key
        if self.case_insensitive:
            return key.lower()
        return key

    def _mod_callback(self):
        # Calls the modify callback if we have one
        if self._modify_callback:
            self._modify_callback()
                
    def __contains__(self, val):
        return self._ef_key(val) in self._keys
                
    def __getitem__(self, key):
        for p in reversed(self._pairs):
            if self._ef_key(p[0]) == self._ef_key(key):
                return p[1]
        raise KeyError

    def __setitem__(self, key, val):
        # Replaces first instance of `key` and deletes the rest
        self.set_val(key, val)

    def __delitem__(self, key):
        self._remove_key(key)
        self._pairs = [p for p in self._pairs if self._ef_key(p[0]) != self._ef_key(key)]
        self._mod_callback()

    def __nonzero__(self):
        if self._pairs:
            return True
        else:
            return False

    def _add_key(self, key):
        self._keys.add(self._ef_key(key))

    def _remove_key(self, key):
        self._keys.remove(self._ef_key(key))
    
    def all_pairs(self):
        """
        A list of all the key/value pairs stored in the dictionary
        """
        return self._pairs[:]

    def append(self, key, val, do_callback=True):
        """
        append(key, val)
        Append a pair to the end of the dictionary. Will add a duplicate if the key already exists.
        """
        # Add a duplicate entry for key
        self._add_key(key)
        self._pairs.append((key, val))
        if do_callback:
            self._mod_callback()

    def set_val(self, key, val, do_callback=True):
        """
        set_val(key, val)
        Set a value in the dictionary. Will replace the first instance of the
        key with the value. If multiple values of the keys are already in the
        dictionary, the duplicates of the key will be removed and the first instance
        of the key will be replaced with the value. If the dictionary is case
        insensitive, it will maintain the original capitalization. This is the same
        behavior as assigning a value via ``d[key] = val``. If the key is not
        present, it will be added to the end of the dict.
        """
        new_pairs = []
        added = False
        self._add_key(key)
        for p in self._pairs:
            if self._ef_key(p[0]) == self._ef_key(key):
                if not added:
                    # only add the first instance
                    new_pairs.append((key, val))
                    added = True
            else:
                new_pairs.append(p)
        if not added:
            new_pairs.append((key, val))
        self._pairs = new_pairs

        if do_callback:
            self._mod_callback()

    def update(self, key, val, do_callback=True):
        # If key is already in the dict, replace that value with the new value
        if key in self:
            for k, v in self.all_pairs():
                if self._ef_key(k) == self._ef_key(key):
                    self.set_val(k, val, do_callback=do_callback)
                    break
        else:
            self.set_val(key, val, do_callback=do_callback)

    def clear(self, do_callback=True):
        """
        clear()
        Remove all key/value pairs from the dictionary
        """
        self._pairs = []
        if do_callback:
            self._mod_callback()
            
    def all_vals(self, key):
        """
        all_vals(key)
        Return all the values associated with a given key
        """
        return [p[1] for p in self._pairs if self._ef_key(p[0]) == self._ef_key(key)]

    def add_pairs(self, pairs, do_callback=True):
        """
        add_pairs(pairs)
        Add a list of pairs to the dictionary.

        :param pairs: The list of key/value pairs to add
        :type pairs: List of tuples of length 2
        """
        for pair in pairs:
            self._add_key(pair[0])
        self._pairs += pairs
        if do_callback:
            self._mod_callback()

    def from_dict(self, d, do_callback=True):
        """
        from_dict(d)
        Set the RepeatableDict to contain the same items as a normal dictionary.

        :param d: The dictionary to use
        :type d: dict
        """
        self._pairs = list(d.items())
        if do_callback:
            self._mod_callback()

    def sort(self):
        """
        sort()
        Sort the dictionary by the key. Requires that all keys can be compared
        to each other
        """
        # Sorts pairs by key alphabetaclly
        self._pairs = sorted(self._pairs, key=lambda x: x[0])

    def set_modify_callback(self, callback):
        # Add a function to be called whenever an element is added, changed, or
        # deleted. Set to None to remove
        self._modify_callback = callback
        

class LengthData:
    def __init__(self, length=None):
        self.body = ''
        self.complete = False
        self.length = length or 0

        if self.length == 0 or self.length == -1:
            self.complete = True

    def add_data(self, data):
        if self.complete and self.length != -1:
            raise PappyException("Data already complete!")
        remaining_length = self.length-len(self.body)
        if self.length == -1:
            self.body += data
            complete = True
        else:
            if len(data) >= remaining_length:
                self.body += data[:remaining_length]
                assert(len(self.body) == self.length)
                self.complete = True
            else:
                self.body += data

class ChunkedData:

    def __init__(self):
        self.body = ''
        self._pos = 0
        self._state = 0 # 0=reading length, 1=reading data, 2=going over known string
        self._len_str = ''
        self._chunk_remaining = 0
        self._known_str = ''
        self._known_str_pos = 0
        self._next_state = 0
        self._body = []
        self.complete = False
        self.unchunked_data = []

    def add_data(self, data):
        for c in data:
            self._body.append(c)
        self.scan_forward()

    def scan_forward(self):
        # Don't add more data if we're already done
        if self.complete:
            return

        while self._pos < len(self._body):
            curchar = self._body[self._pos]
            if self._state == 0:
                if curchar.lower() in '0123456789abcdef':
                    # Read the next char of the length
                    self._len_str += curchar

                    # Move to the next char
                    self._pos += 1
                elif curchar == '\r':
                    # Save how much chunk to read
                    self._chunk_remaining = int(self._len_str, 16)

                    # If the length is 0, chunked encoding is done!
                    if self._chunk_remaining == 0:
                        self.complete = True
                        self.body = ''.join(self.unchunked_data)
                        return

                    # There should be a newline after the \r
                    self._known_str = '\n'
                    self._state = 2
                    self._next_state = 1

                    # Reset the length str
                    self._len_str = ''

                    # Move to the next char
                    self._pos += 1
                else:
                    raise Exception("Malformed chunked encoding!")

            elif self._state == 1:
                if self._chunk_remaining > 0:
                    # Read next byte of data
                    self.unchunked_data.append(curchar)
                    self._chunk_remaining -= 1
                    self._pos += 1
                else:
                    # Read newline then read a new chunk
                    self._known_str = '\r\n'
                    self._next_state = 0 # Read len after newlines
                    self._state = 2 # Read newlines
                    # Don't move to the next char because we didn't do anything
            elif self._state == 2:
                # Read a char of an expected string

                # If the expected char doesn't match, throw an error
                if self._known_str[self._known_str_pos] != curchar:
                    raise Exception("Unexpected data")

                # Move to the next char in the raw data and in our known string
                self._known_str_pos += 1
                self._pos += 1

                # If we've reached the end of the known string, go to the next state
                if self._known_str_pos == len(self._known_str):
                    self._known_str_pos = 0
                    self._state = self._next_state

class ResponseCookie(object):
    """
    A cookie representing a cookie set by a response

    :ivar key: The key of the cookie
    :type key: string
    :ivar val: The value of the cookie
    :type val: string
    :ivar expires: The value of the "expires" attribute
    :type expires: string
    :ivar max_age: The max age of the cookie
    :type max_age: int
    :ivar domain: The domain of the cookie
    :type domain: string
    :ivar path: The path of the cookie
    :type path: string
    :ivar secure: The secure flag of the cookie
    :type secure: Bool
    :ivar http_only: The httponly flag of the cookie
    :type http_only: Bool
    """

    def __init__(self, set_cookie_string=None):
        self.key = None
        self.val = None
        self.expires = None
        self.max_age = None
        self.domain = None
        self.path = None
        self.secure = False
        self.http_only = False

        if set_cookie_string:
            self._from_cookie(set_cookie_string)

    @property
    def cookie_str(self):
        """
        Returns the full string of the cookie. ie ``foo=bar; secure; path=/``

        :getter: Returns the full string of the cookie.
        :setter: Set the metadata from a cookie string. ie from a ``Set-Cookie`` header
        """
        av = '%s=%s' % (self.key, self.val)
        to_add = [av]
        if self.expires:
            to_add.append('expires=%s'%self.expires)
        if self.max_age:
            to_add.append('Max-Age=%d'%self.max_age)
        if self.domain:
            to_add.append('Domain=%s'%self.domain)
        if self.path:
            to_add.append('Path=%s'%self.path)
        if self.secure:
            to_add.append('secure')
        if self.http_only:
            to_add.append('httponly')
        return '; '.join(to_add)

    @cookie_str.setter
    def cookie_str(self, val):
        self._from_cookie(val)

    def _parse_cookie_av(self, cookie_av):
        if '=' in cookie_av:
            key, val = cookie_av.split('=', 1)
            key = key.lstrip()
            if key.lower() == 'expires':
                self.expires = val
            if key.lower() == 'max-age':
                self.max_age = int(val)
            if key.lower() == 'domain':
                self.domain = val
            if key.lower() == 'path':
                self.path = val
        elif cookie_av.lstrip().lower() == 'secure':
            self.secure = True
        elif cookie_av.lstrip().lower() == 'httponly':
            self.http_only = True
            
    def _from_cookie(self, set_cookie_string):
        self.key = None
        self.val = None
        self.expires = None
        self.max_age = None
        self.domain = None
        self.path = None
        self.secure = False
        self.http_only = False
        if ';' in set_cookie_string:
            cookie_pair, rest = set_cookie_string.split(';', 1)
            if '=' in cookie_pair:
                self.key, self.val = cookie_pair.split('=',1)
            elif cookie_pair == '' or re.match('\s+', cookie_pair):
                self.key = ''
                self.val = ''
            else:
                self.key = cookie_pair
                self.val = ''
            cookie_avs = rest.split(';')
            for cookie_av in cookie_avs:
                cookie_av.lstrip()
                self._parse_cookie_av(cookie_av)
        else:
            self.key, self.val = set_cookie_string.split('=',1)
            
class WebSocketMessage(object):
    """
    A class representing a websocket message
    """

    DIRECTION_OUTGOING = 0
    DIRECTION_INCOMING = 1

    TYPE_MESSAGE = 0

    def __init__(self, direction=None, contents=None, message_type=None, time_sent=None, is_binary=None):
        self.direction = None
        self.contents = None
        self.message_type = WebSocketMessage.TYPE_MESSAGE
        self.time_sent = None
        self.unmangled = None
        self.parent_request = None
        self.is_unmangled_version = False
        self.is_binary = False
        self.msgid = '--'

    def __eq__(self, other):
        if self.contents != other.contents:
            return False
        if self.is_binary != other.is_binary:
            return False
        return True

    def __copy__(self):
        new_msg = WebSocketMessage()
        new_msg.direction = self.direction
        new_msg.contents = self.contents
        new_msg.message_type = self.message_type
        new_msg.is_binary = self.is_binary
        return new_msg

    def copy(self):
        return self.__copy__()

    def duplicate(self):
        m = self.copy()
        m.msgid = self.msgid
        m.time_sent = self.time_sent
        if self.unmangled:
            m.unmangled = self.unmangled.duplicate()
        return m

    @defer.inlineCallbacks
    def async_save(self, cust_dbpool=None):
        from .pappy import main_context

        global dbpool
        if cust_dbpool:
            use_dbpool = cust_dbpool
        else:
            use_dbpool = dbpool

        assert(use_dbpool)
        if not self.msgid:
            self.msgid = '--'
        try:
            # Check for intyness
            _ = int(self.msgid)

            # If we have msgid, we're updating
            yield use_dbpool.runInteraction(self._update)
            assert(self.msgid is not None)
        except (ValueError, TypeError):
            # Either no id or in-memory
            yield use_dbpool.runInteraction(self._insert)
            assert(self.msgid is not None)
        main_context.cache_reset()

    @defer.inlineCallbacks
    def async_deep_save(self):
        if self.unmangled:
            yield self.unmangled.async_deep_save()
        yield self.async_save()

    def _update(self, txn):
        setnames = ['is_binary=?', 'contents=?']
        queryargs = [self.is_binary, self.contents]

        # Direction
        if self.direction == 'OUTGOING':
            setnames.append('direction=?')
            queryargs.append(0)
        elif self.direction == 'INCOMING':
            setnames.append('direction=?')
            queryargs.append(1)
        else:
            setnames.append('direction=?')
            queryargs.append(-1)

        # Unmangled
        if self.unmangled:
            setnames.append('unmangled_id=?')
            assert(self.unmangled.msgid is not None) # should be saved first
            queryargs.append(self.unmangled.msgid)

        # Message time
        if self.time_sent:
            setnames.append('time_sent=?')
            queryargs.append((self.time_sent-datetime.datetime(1970,1,1)).total_seconds())

        # Parent request
        if self.parent_request:
            assert(self.parent_request.reqid)
            setnames.append('parent_request=?')
            queryargs.append(self.parent_request.reqid)

        queryargs.append(self.msgid)
        txn.execute(
            """
            UPDATE websocket_messages SET %s WHERE id=?;
            """ % ','.join(setnames),
            tuple(queryargs)
        )

    def _insert(self, txn):
        colnames = ['is_binary', 'contents']
        colvals = [self.is_binary, self.contents]
        
        # Direction
        if self.direction == 'OUTGOING':
            colnames.append('direction')
            colvals.append(0)
        elif self.direction == 'INCOMING':
            colnames.append('direction')
            colvals.append(1)
        else:
            colnames.append('direction')
            colvals.append(-1)

        # Unmangled
        if self.unmangled:
            colnames.append('unmangled_id')
            assert(self.unmangled.msgid is not None) # should be saved first
            colvals.append(self.unmangled.msgid)

        # Message time
        if self.time_sent:
            colnames.append('time_sent')
            colvals.append((self.time_sent-datetime.datetime(1970,1,1)).total_seconds())

        # Parent request
        if self.parent_request:
            assert(self.parent_request.reqid)
            colnames.append('parent_request')
            colvals.append(self.parent_request.reqid)
        txn.execute(
            """
            INSERT INTO websocket_messages (%s) VALUES (%s);
            """ % (','.join(colnames), ','.join(['?']*len(colvals))),
            tuple(colvals)
        )
        self.msgid = str(txn.lastrowid)
        
class WebSocketProxy(object):

    def __init__(self, server_transport, client_transport, client_handshake, server_handshake, parent_proxy, log_id=None):
        self.message_callback = None
        self.close_callback = None
        self.log_id = log_id
        self.intercepting_macros = None
        self.parent_http_proxy = parent_proxy

        # The raw http messages from the handshake
        self.client_handshake = client_handshake
        self.server_handshake = server_handshake

        self.server_factory = WebSocketServerFactory()
        self.server_factory.protocol = WebSocketServerProtocol
        self.server_transport = server_transport

        self.client_factory = WebSocketClientFactory()
        self.client_factory.protocol = WebSocketClientProtocol
        self.client_transport = client_transport

        self._fake_handshake()

    def log(self, message, symbol='*', verbosity_level=3):
        from pappyproxy.proxy import log

        if self.log_id:
            log(message, id=log_id, symbol=symbol, verbosity_level=verbosity_level)
        else:
            log(message, symbol=symbol, verbosity_level=verbosity_level)

    def _build_server_protocol(self):
        self.server_protocol = self.server_factory.buildProtocol(None)
        self.server_protocol.makeConnection(self.server_transport)
        self._patch_server_protocol()

    def _build_client_protocol(self):
        """
        Builds the client protocol then returns the bytes written to the
        transport after creation
        """
        self.client_protocol = self.client_factory.buildProtocol(None)
        tr = PappyStringTransport()
        self.client_protocol.makeConnection(tr)
        tval = tr.pop_value()
        self.client_protocol.transport = self.client_transport
        self._patch_client_protocol()
        return tval

    def _patch_server_protocol(self):
        self.log("Patching server protocol")
        self._add_hook(self.server_protocol, 'onMessage', '_on_server_message')

    def _patch_client_protocol(self):
        self.log("Patching client protocol")
        self._add_hook(self.client_protocol, 'onMessage', '_on_client_message')

    def _add_hook(self, c, their_method, my_method):
        """
        Make it so that c.their_method(*args, **kwargs) calls self.my_method(*args, **kwargs)
        before calling their method
        """
        old = getattr(c, their_method)
        def patched(*args, **kwargs):
            getattr(self, my_method)(*args, **kwargs)
            old(*args, **kwargs)
        setattr(c, their_method, patched)

    @staticmethod
    def _gen_sec_websocket_accept(token):
        MAGIC_STRING = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        concatenated = token + MAGIC_STRING
        hashed = sha1(concatenated)
        reencoded = base64.b64encode(hashed)
        return reencoded

    def _parse_extension_header(self, hd):
        """
        Parses the extension header and returns a list of offers
        """
        offers = []
        extensions = self.server_protocol._parseExtensionsHeader(hd)
        for (extension, params) in extensions:
            if extension in PERMESSAGE_COMPRESSION_EXTENSION:

                PMCE = PERMESSAGE_COMPRESSION_EXTENSION[extension]

                try:
                    offer = PMCE['Offer'].parse(params)
                    offers.append(offer)
                except Exception as e:
                    raise PappyException(str(e))
            else:
                self.log("Bad extension: %s" % extension)
        return offers

    def _set_up_ws_client(self, ws_server_factory, ws_client_factory, hs_req, hs_rsp):
        """
        Sets up a WebSocketClientProtocolFactory from a WebSocketServerProtocolFactory
        """
        self.log("Setting up websocket client")
        client_settings = {}

        # Common attributes
        skip_attrs = ('logFrames','trackTimings','logOctets')
        for attr in WebSocketProtocol.CONFIG_ATTRS_COMMON:
            if attr not in skip_attrs:
                client_settings[attr] = getattr(ws_server_factory, attr)

        def accept(response):
            from autobahn.websocket.compress import PerMessageDeflateResponse, \
                   PerMessageDeflateResponseAccept, \
                   PerMessageBzip2Response, \
                   PerMessageBzip2ResponseAccept, \
                   PerMessageSnappyResponse, \
                   PerMessageSnappyResponseAccept
            if isinstance(response, PerMessageDeflateResponse):
                return PerMessageDeflateResponseAccept(response)

            elif isinstance(response, PerMessageBzip2Response):
                return PerMessageBzip2ResponseAccept(response)

            elif isinstance(response, PerMessageSnappyResponse):
                return PerMessageSnappyResponseAccept(response)

        # Client specific attributes
        client_settings['version'] = int(hs_req.headers['Sec-WebSocket-Version'])
        client_settings['acceptMaskedServerFrames'] = True
        client_settings['maskClientFrames'] = True
        #client_settings['serverConnectionDropTimeout'] = None

        offers = self._parse_extension_header(hs_req.headers['Sec-WebSocket-Extensions'])
        client_settings['perMessageCompressionOffers'] = offers
        client_settings['perMessageCompressionAccept'] = accept

        # debug
        client_settings['openHandshakeTimeout'] = 8

        self.log("Setting client options: %s" % client_settings)
        ws_client_factory.setProtocolOptions(**client_settings)

    def _fake_handshake(self):
        self.log("Performing fake handshake")

        # Set up our server listener
        self._build_server_protocol()
        old_server_transport = self.server_protocol.transport
        self.server_protocol.transport = PappyStringTransport()
        self.log("Sending fake handshake response to server protocol:")
        self.log("pf> %s" % printable_data(self.server_handshake.full_message))
        self.server_protocol.dataReceived(self.server_handshake.full_message)
        tval = self.server_protocol.transport.pop_value()
        self.log("<fp %s" % printable_data(tval))
        assert tval
        self.server_protocol.transport = old_server_transport

        # Set up our client
        self._set_up_ws_client(self.server_factory,
                               self.client_factory,
                               self.server_handshake,
                               self.client_handshake)
        # Perform rest of client handshake
        tval = self._build_client_protocol()
        self.log("Getting handshake request start from client protocol")
        self.log("<fp %s" % printable_data(tval))
        # Revert transport handshake so that any data sent after our response is
        # sent to the real transport
        self.log("Reverting client transport")
        self.log("Sending fake handshake response to client protocol:")
        handshake_req = Request(tval)
        handshake_rsp = self.client_handshake.copy()
        sec_ws_key = handshake_req.headers['Sec-WebSocket-Key']
        self.log("Generating Sec-WebSocket-Accept for %s" % sec_ws_key)
        sec_ws_accept = WebSocketProxy._gen_sec_websocket_accept(sec_ws_key)
        self.log("Sec-WebSocket-Accept = %s" % sec_ws_accept)
        handshake_rsp.headers['Sec-WebSocket-Accept'] = sec_ws_accept
        self.log("pf> %s" % printable_data(handshake_rsp.full_message))
        self.client_protocol.dataReceived(handshake_rsp.full_message) # Tell it whatever the remote server told us
        self.log("Compressed after handshake? %s" % self.client_protocol._perMessageCompress)

        self.log("Fake handshake complete")

    def _on_server_message(self, payload, is_binary):
        """
        Wrapper to convert arguments to onMessage into an object and call on_server_message
        """
        # Turn into object
        m = WebSocketMessage()
        m.direction = 'OUTGOING'
        m.contents = payload
        m.time_sent = datetime.datetime.utcnow()
        m.is_binary = is_binary
        self.log("rp< (websocket, binary=%s) %s" % (m.is_binary, m.contents))

        self.on_server_message(m)

    def _on_client_message(self, payload, is_binary):
        """
        Wrapper function for when the client protocol gets a data frame
        """
        # Turn into object
        m = WebSocketMessage()
        m.direction = 'INCOMING'
        m.contents = payload
        m.time_sent = datetime.datetime.utcnow()
        m.is_binary = is_binary
        self.log("cp> (websocket, binary=%s) %s" % (m.is_binary, m.contents))

        self.on_client_message(m)

    @defer.inlineCallbacks
    def mangle_message(self, message):
        from pappyproxy import context, macros

        # Mangle object
        sendreq = self.server_handshake
        custom_macros = self.parent_http_proxy.custom_macros
        mangle_macros = self.parent_http_proxy.mangle_macros
        client_protocol = self.parent_http_proxy.client_protocol
        save_requests = self.parent_http_proxy.save_requests
        dropped = False
        sendmsg = message

        if context.in_scope(sendreq) or custom_macros:
            self.log("Passing ws message through macros")
            if not custom_macros:
                mangle_macros = client_protocol.factory.get_macro_list()

            if save_requests:
                yield sendreq.async_deep_save()

            (mangmsg, mangled) = yield macros.mangle_websocket_message(message, sendreq, mangle_macros)
            if mangmsg is None:
                self.log("Message dropped")
                dropped = True
            elif mangled:
                self.log("Message mangled")
                sendmsg.time_sent = None
                mangmsg.unmangled = sendmsg
                sendmsg = mangmsg
            else:
                self.log("Message not modified")

            mangmsg.time_sent = datetime.datetime.utcnow()
            if not dropped:
                sendreq.add_websocket_message(sendmsg)
            if save_requests:
                yield sendreq.async_deep_save()
        else:
            sendreq.add_websocket_message(sendmsg)
            self.log("Request out of scope, passing ws message along unmangled")

        # Send data frame through server object to the client
        defer.returnValue((sendmsg, dropped))

    @defer.inlineCallbacks
    def on_server_message(self, message):
        """
        Wrapper function for when the server protocol gets a data frame
        """
        # Mangle object
        sendmsg, dropped = yield self.mangle_message(message)

        # Send data frame through client object to remote server
        if not dropped:
            self.send_server_message(sendmsg.contents, sendmsg.is_binary)

    @defer.inlineCallbacks
    def on_client_message(self, message):
        """
        Wrapper function for when the client protocol gets a data frame
        """
        sendmsg, dropped = yield self.mangle_message(message)

        # Send data frame through server object to the client
        if not dropped:
            self.send_client_message(sendmsg.contents, sendmsg.is_binary)

    def client_data_received(self, data):
        # Called when data is received from the client
        # Sends RAW DATA to server protocol. NOT frame data
        self.server_protocol.dataReceived(data)

    def server_data_received(self, data):
        # Called when data is received from the server
        # Sends RAW DATA to client protocol. NOT frame data
        self.client_protocol.dataReceived(data)

    def send_client_message(self, message_data, is_binary=False):
        # Write a message to the client over the actual transport
        self.server_protocol.sendMessage(message_data, is_binary)

    def send_server_message(self, message_data, is_binary=False):
        # Write a message to the remote server over the actual transport
        self.client_protocol.sendMessage(message_data, is_binary)

    def on_client_frame(self, frame_data, is_binary=False):
        # Call callback and have callback return mangled frame data
        self.server_protocol.sendFrame(frame_data, is_binary)

class HTTPMessage(object):
    """
    A base class which represents an HTTP message. It is used to implement
    both requests and responses

    :ivar complete: When loading data with
        :func:`~pappyproxy.http.HTTPMessage.add_line` and
        :func:`~pappyproxy.http.HTTPMessage.add_data`, returns whether the message
        is complete
    :vartype complete: bool
    :ivar headers: Headers of the message
    :vartype complete: RepeatableDict
    :ivar headers_complete: When creating the message with
        :func:`~pappyproxy.http.HTTPMessage.add_line` and
        :func:`~pappyproxy.http.HTTPMessage.add_data`, returns whether the headers
        are complete
    :ivar start_line: The start line of the message
    :vartype start_line: string
    """

    reserved_meta_keys = ['full_message']
    """
    Internal class variable. Do not modify.
    """

    def __init__(self, full_message=None, update_content_length=False):
        # Initializes instance variables too
        self.clear()

        self.metadata_unique_keys = tuple()
        if full_message is not None:
            self._from_full_message(full_message, update_content_length)

    def __eq__(self, other):
        if self.full_message != other.full_message:
            return False
        m1 = self.get_metadata()
        m2 = other.get_metadata()
        for k in self.metadata_unique_keys:
            if k in m1:
                del m1[k]
            if k in m2:
                del m2[k]
        if m1 != m2:
            return False
        return True

    def __copy__(self):
        if not self.complete:
            raise PappyException("Cannot copy incomplete http messages")
        retmsg = self.__class__(self.full_message)
        retmsg.set_metadata(self.get_metadata(include_unique=False))
        return retmsg

    def copy(self):
        """
        Returns a copy of the request

        :rtype: Request
        """
        return self.__copy__()

    def deepcopy(self):
        """
        Returns a deep copy of the message. Implemented by child.

        NOINDEX
        """
        return self.__deepcopy__()

    def clear(self):
        """
        Resets all internal data and clears the message
        """
        self.complete = False
        self.headers = RepeatableDict(case_insensitive=True)
        self.headers_complete = False
        self.malformed = False
        self.start_line = ''
        self.reset_metadata()
        self._decoded = False

        self._encoding_type = ENCODE_NONE
        self._first_line = True
        self._data_obj = None
        self._end_after_headers = False
        self._data_buffer = ''

    def _from_full_message(self, full_message, update_content_length=False, meta=None):
        # Set defaults for metadata
        self.clear()
        # Get rid of leading CRLF. Not in spec, should remove eventually
        full_message = _strip_leading_newlines(full_message)
        if full_message == '':
            return

        self.add_data(full_message, enforce_content_length=(not update_content_length))

        if meta:
            self.set_metadata(meta)

        if update_content_length:
            # If we have no body and didn't have a content-length header in the first
            # place, don't add one
            if 'Content-Length' in self.headers or len(self.body) > 0:
                self.headers['Content-Length'] = str(len(self.body))
        assert(self.complete)

    ###############################
    ## Properties/attribute setters

    @property
    def headers_section(self):
        """
        The raw text of the headers including the extra newline at the end.

        :getter: Returns the raw text of the headers including the extra newline at the end.
        :type: string
        """
        ret = ''
        if self.start_line:
            ret = self.start_line + '\r\n'
        for k, v in self.headers.all_pairs():
            ret = ret + "%s: %s\r\n" % (k, v)
        if ret:
            ret = ret + '\r\n'
        return ret

    @property
    def headers_section_pretty(self):
        """
        Same thing as :func:`pappyproxy.http.HTTPMessage.headers_section` except
        that the headers are colorized for terminal printing.
        """
        to_ret = printable_data(self.headers_section, colors=False)
        to_ret = pygments.highlight(to_ret, HttpLexer(), TerminalFormatter())
        return to_ret

    @property
    def body(self):
        """
        The data portion of the message

        :getter: Returns the data portion of the message
        :setter: Set the data of the response and update metadata
        :type: string
        """
        if self._data_obj:
            return self._data_obj.body
        else:
            return ''
        
    @body.setter
    def body(self, val):
        self._data_obj = LengthData(len(val))
        if len(val) > 0:
            self._data_obj.add_data(val)
        self._encoding_type = ENCODE_NONE
        self.complete = True
        self.update_from_body()

    @property
    def body_pretty(self):
        """
        Same thing as :func:`pappy.http.HTTPMessage.body` but the output is
        colorized for the terminal.
        """
        if self.body == '':
            return ''
        to_ret = printable_data(self.body, colors=False)
        if 'content-type' in self.headers:
            try:
                lexer = get_lexer_for_mimetype(self.headers['content-type'].split(';')[0])
                to_ret = pygments.highlight(to_ret, lexer, TerminalFormatter())
            except:
                pass
        return to_ret

    @property
    def full_message(self):
        """
        The full message including the start line, headers, and body
        """
        if self.headers_section == '':
            return self.body
        else:
            return (self.headers_section + self.body)

    @property
    def full_message_pretty(self):
        """
        Same as :func:`pappyproxy.http.HTTPMessage.full_message` except the
        output is colorized
        """
        if self.body:
            return (self.headers_section_pretty + '\r\n' + self.body_pretty)
        else:
            return self.headers_section_pretty

    ###############
    ## Data loading

    def add_line(self, line, enforce_content_length=True):
        """
        Used for building a message from a Twisted protocol.
        Add a line (for status line and headers). Lines must be added in order
        and the first line must be the status line. The line should not contain
        the trailing carriage return/newline. I do not suggest you use this for
        anything.

        :param line: The line to add
        :type line: string
        """
        assert(not self.headers_complete)
        if not line and self._first_line:
            return
        if not line:
            self.headers_complete = True

            if not self._data_obj:
                self._data_obj = LengthData(0)

            if self._end_after_headers:
                self.complete = True
                return

            if not enforce_content_length or 'content-length' not in self.headers:
                if isinstance(self._data_obj, LengthData):
                    self._data_obj = LengthData(-1)
            self.complete = self._data_obj.complete
            self.headers_end()
            return

        if self._first_line:
            self.handle_start_line(line)
            self._first_line = False
        else:
            if ':' in line:
                key, val = line.split(':', 1)
                val = val.strip()
            else:
                key = line
                val = None
            if self.handle_header(key, val):
                self.headers.append(key, val, do_callback=False)

    def add_data(self, data, enforce_content_length=True):
        """
        Used for building a message from a Twisted protocol.
        Add data to the message. The data must conform to the content encoding
        and transfer encoding given in the headers passed in to
        :func:`~pappyproxy.http.HTTPMessage.add_line`. Can be any fragment of the data.
        I do not suggest that you use this function ever.

        :param data: The data to add
        :type data: string
        """
        assert not self.complete or not enforce_content_length
        self._data_buffer += data

        def popline(s):
            parts = s.split('\n', 1)
            if len(parts) == 1:
                return (s, '')
            line, rest = (parts[0], ''.join(parts[1:]))
            if line[-1] == '\r':
                line = line[:-1]
            return (line, rest)

        # Add headers from the data buffer if headers aren't complete
        if not self.headers_complete:
            while '\n' in self._data_buffer and not self.headers_complete:
                line, self._data_buffer = popline(self._data_buffer)
                self.add_line(line, enforce_content_length=enforce_content_length)

        # Add the data section if the headers are complete and we have stuff left in the buffer
        if self.headers_complete:
            if self._data_buffer:
                to_add = self._data_buffer
                self._data_buffer = ''
                self._data_obj.add_data(to_add)
            if self._data_obj.complete:
                self.complete = True
                self.body_complete()

    ###############
    ## Data parsing

    def handle_header(self, key, val):
        """
        Called when a header is loaded into the message. Should not be called
        outside of implementation.

        :param key: Header key
        :type line: string
        :param key: Header value
        :type line: string

        NOINDEX
        """
        if val is None:
            return True
        stripped = False
        if key.lower() == 'content-encoding':
            if val in ('gzip', 'x-gzip'):
                self._encoding_type = ENCODE_GZIP
            elif val in ('deflate'):
                self._encoding_type = ENCODE_DEFLATE

            # We send our requests already decoded, so we don't want a header
            # saying it's encoded
            if self._encoding_type != ENCODE_NONE:
                self._decoded = True
                stripped = True
        elif key.lower() == 'transfer-encoding' and val.lower() == 'chunked':
            self._data_obj = ChunkedData()
            self.complete = self._data_obj.complete
            self._decoded = True
            stripped = True
        elif key.lower() == 'content-length':
            # We use our own content length
            if self._data_obj and self._data_obj.complete:
                # We're regenerating or something so we want to base this header
                # off our existing body
                val = self._data_obj.body
                self._data_obj = LengthData(len(val))
                if len(val) > 0:
                    self._data_obj.add_data(val)
                self._encoding_type = ENCODE_NONE
                self.complete = True
            else:
                self._data_obj = LengthData(int(val))

        return (not stripped)

    def handle_start_line(self, start_line):
        """
        A handler function for the status line.

        NOINDEX
        """
        self.start_line = start_line

    def headers_end(self):
        """
        Called when the headers are complete.

        NOINDEX
        """
        pass

    def body_complete(self):
        """
        Called when the body of the message is complete

        NOINDEX
        """
        try:
            self.body = _decode_encoded(self._data_obj.body,
                                        self._encoding_type)
        except IOError:
            # Screw handling it gracefully, this is the server's fault.
            print 'Error decoding request, storing raw data in body instead'
            self.body = self._data_obj.body

    def update_from_body(self):
        """
        Called when the body of the message is modified directly. Should be used
        to update metadata that depends on the body of the message.

        NOINDEX
        """
        if len(self.body) > 0 or 'Content-Length' in self.headers:
            self.headers.update('Content-Length', str(len(self.body)), do_callback=False)

    def update_from_headers(self):
        """
        Called when a header is modified. Should be used to update metadata that
        depends on the values of headers.

        NOINDEX
        """
        pass

    ###########
    ## Metadata

    # The metadata functions are used so that we only have to make changes in a
    # few similar functions which will update all copying, serialization, etc
    # functions at the same time.

    def get_metadata(self):
        """
        Get all the metadata of the message in dictionary form.
        Should be implemented in child class.
        Should not be invoked outside of implementation!

        NOINDEX
        """
        pass

    def set_metadata(self, data):
        """
        Set metadata values based off of a data dictionary.
        Should be implemented in child class.
        Should not be invoked outside of implementation!

        :param data: Metadata to apply
        :type line: dict

        NOINDEX
        """
        pass

    def reset_metadata(self):
        """
        Reset meta values to default values. Overridden by child class.
        Should not be invoked outside of implementation!

        NOINDEX
        """
        pass

    ##############
    ## Serializing

    def to_json(self):
        """
        Return a JSON encoding of the message that can be used by
        :func:`~pappyproxy.http.Message.from_json` to recreate the message.
        The ``full_message`` portion is base64 encoded because json doesn't play
        nice with binary blobs.
        """
        data = {
            'full_message': base64.b64encode(self.full_message),
        }

        metadata = self.get_metadata()
        for k, v in metadata.iteritems():
            if k in HTTPMessage.reserved_meta_keys:
                raise PappyException('A message with %s as a key for a metavalue cannot be encoded into JSON')
            data[k] = v

        return json.dumps(data)
            

    def from_json(self, json_string):
        """
        Update the metadata of the message to match data from
        :func:`~pappyproxy.http.Message.to_json`

        :param json_string: The JSON data to use
        :type json_string: JSON data in a string
        """
        data = json.loads(json_string)
        full_message = base64.b64decode(data['full_message'])
        for k in HTTPMessage.reserved_meta_keys:
            if k in data:
                del data[k]
        self._from_full_message(full_message, meta=data)
        # self.update_from_headers()
        # self.update_from_body()


class Request(HTTPMessage):
    """
    :ivar time_end: The datetime that the request ended.
    :vartype time_end: datetime.datetime
    :ivar time_start: The datetime that the request was made
    :vartype time_start: datetime.datetime
    :ivar cookies: Cookies sent with the request
    :vartype cookies: RepeatableDict
    :ivar fragment: The fragment part of the url (The part that comes after the #)
    :vartype fragment: String
    :ivar url_params: The url parameters of the request (aka the get parameters)
    :vartype url_params: RepeatableDict
    :ivar path: The path of the request
    :vartype path: String
    :ivar port: The port that the request was sent to (or will be sent to)
    :vartype port: Integer
    :ivar post_params: The post parameters of the request
    :vartype post_params: RepeatableDict
    :ivar reqid: The request id of the request
    :vartype reqid: String
    :ivar response: The associated response of this request
    :vartype response: Response
    :ivar submitted: Whether the request has been submitted
    :vartype submitted: Bool
    :ivar unmangled: If the request was mangled, the version of the request
                     before it was mangled.
    :vartype unmangled: Request
    :ivar verb: The HTTP verb of the request (ie POST, GET)
    :vartype verb: String
    :ivar version: The HTTP version of the request (ie HTTP/1.1)
    :vartype version: String
    :ivar tags: Tags associated with the request
    :vartype tags: List of Strings
    :ivar plugin_data: Data about the request created by plugins. If you modify this, please add your own key to it for your plugin and store all your plugin's data under that key (probably as another dict). For example if you have a plugin called ``foo``, try and store all your data under ``req.plugin_data['foo']``.
    :vartype plugin_data: Dict
    :ivar path_type: An enum which describes how the path portion of the request should be represented. ``PATH_RELATIVE`` -> normal relative path, ``PATH_ABSOLUTE`` -> The absolute path (including the protocol), ``PATH_HOST`` -> Just the path and the port (Used for CONNECT requests when connecting to an upstream HTTP proxy).
    :vartype path_type: Enum
    :ivar explicit_port: A flag to indicate that the port should always be included in the URL
    """

    cache = RequestCache(100)
    """
    The request cache that stores requests in memory for performance
    """

    def __init__(self, full_request=None, update_content_length=True,
                 port=None, is_ssl=None, host=None, path_type=None,
                 proxy_creds=None, explicit_port=False):
        # Resets instance variables
        self.clear()

        # Called after instance vars since some callbacks depend on
        # instance vars
        HTTPMessage.__init__(self, full_request, update_content_length)

        # metadata that is unique to a specific Request instance
        self.metadata_unique_keys = ('reqid',)

        # After message init so that other instance vars are initialized
        self._set_dict_callbacks()

        # Set values from init
        if is_ssl:
            self.is_ssl = True
        if port:
            self.port = port
        if host:
            self._host = host
        if path_type:
            self.path_type = path_type
        if explicit_port:
            self.explicit_port = explicit_port

        self.is_websocket = False
        self.websocket_messages = []
            
    def __copy__(self):
        if not self.complete:
            import pdb; pdb.set_trace()
            raise PappyException("Cannot copy incomplete http messages")
        retreq = self.__class__(self.full_message)
        retreq.set_metadata(self.get_metadata())
        retreq.time_start = self.time_start
        retreq.time_end = self.time_end
        retreq.reqid = None
        if self.response:
            retreq.response = self.response.copy()
        if self.unmangled:
            retreq.unmangled = self.unmangled.copy()
        retreq.set_websocket_messages([m.duplicate() for m in self.websocket_messages])
        return retreq

    def duplicate(self):
        retreq = self.copy()
        retreq.reqid = self.reqid
        if self.unmangled:
            retreq.unmangled = self.unmangled.duplicate()
        if self.response:
            retreq.response = self.response.duplicate()
        return retreq
            
    @property
    def rsptime(self):
        """
        The response time of the request

        :getter: Returns the response time of the request
        :type: datetime.timedelta
        """
        if self.time_start and self.time_end:
            return self.time_end-self.time_start
        else:
            return None

    @property
    def start_line(self):
        """
        The status line of the request. ie `GET / HTTP/1.1`

        :getter: Returns the status line of the request
        :setter: Sets the status line of the request
        :type: string
        """
        if not self.verb and not self.full_path and not self.version:
            return ''
        if self.path_type == PATH_ABSOLUTE:
            path = self._url_helper(always_have_path=True)
        elif self.path_type == PATH_HOST:
            path = ':'.join((self.host, str(self.port)))
        else:
            path = self.full_path
        return '%s %s %s' % (self.verb, path, self.version)

    @start_line.setter
    def start_line(self, val):
        self.handle_start_line(val)

    @property
    def status_line(self):
        """
        Alias for `pappyproxy.http.Request.start_line`.

        :getter: Returns the status line of the request
        :setter: Sets the status line of the request
        :type: string
        """
        return self.start_line

    @status_line.setter
    def status_line(self, val):
        self.start_line = val

    @property
    def full_path(self):
        """
        The full path of the request including URL params and fragment.
        ie `/path/to/stuff?foo=bar&baz=something#somewhere`

        :getter: Returns the full path of the request
        :type: string
        """

        path = self.path
        if self.url_params:
            path += '?'
            pairs = []
            for pair in self.url_params.all_pairs():
                if pair[1] is None:
                    pairs.append(pair[0])
                else:
                    pairs.append('='.join(pair))
            path += '&'.join(pairs)
        if self.fragment:
            path += '#'
            path += self.fragment
        return path

    @property
    def raw_headers(self):
        """
        Alias for Request.headers_section

        :getter: Returns the raw text of the headers including the extra newline at the end.
        :type: string
        """
        return self.headers_section

    @property
    def full_request(self):
        """
        Alias for Request.full_message

        :getter: Returns the full text of the request
        :type: string
        """
        return self.full_message

    @property
    def raw_data(self):
        """
        Alias for Request.body

        :getter: Returns the data portion of the request
        :setter: Set the data of the request and update metadata
        :type: string
        """
        return self.body

    @raw_data.setter
    def raw_data(self, val):
        self.body = val

    @property
    def connect_request(self):
        """
        If the request uses SSL, this will be a request object that can be used
        with an upstream HTTP server to connect to a server using SSL
        """
        if not self.is_ssl:
            return None
        ret = Request()
        ret.status_line = self.status_line
        ret.host = self.host
        ret.port = self.port
        ret.explicit_port = True
        ret.path_type = PATH_HOST
        authu, authp = self.proxy_creds
        ret.verb = 'CONNECT'
        if authu and authp:
            ret.proxy_creds = self.proxy_creds
        return ret

    @property
    def proxy_creds(self):
        """
        A username/password tuple representing the username/password to
        authenticate to a proxy server. Sets the ``Proxy-Authorization``
        header. Getter will return (None, None) if no creds exist

        :getter: Returns the username/password tuple used for proxy authorization
        :setter: Sets the username/password tuple used for proxy authorization
        :type: Tuple of two strings: (username, password)
        """
        if not 'Proxy-Authorization' in self.headers:
            return (None, None)
        return Request._parse_basic_auth(self.headers['Proxy-Authorization'])

    @proxy_creds.setter
    def proxy_creds(self, creds):
        username, password = creds
        self.headers['Proxy-Authorization'] = Request._encode_basic_auth(username, password)

    @staticmethod
    def _parse_basic_auth(header):
        """
        Parse a raw basic auth header and return (username, password)
        """
        _, creds = header.split(' ', 1)
        decoded = base64.b64decode(creds)
        username, password = decoded.split(':', 1)
        return (username, password)

    @staticmethod
    def _encode_basic_auth(username, password):
        decoded = '%s:%s' % (username, password)
        encoded = base64.b64encode(decoded)
        header = 'Basic %s' % encoded
        return header

    def _url_helper(self, colored=False, always_have_path=False):
        retstr = ''
        if self.is_ssl:
            retstr += 'https://'
        else:
            if colored:
                retstr += Colors.RED
                retstr += 'http'
                retstr += Colors.ENDC
                retstr += '://'
            else:
                retstr += 'http://'
        if colored:
            retstr += host_color(self.host)
            retstr += self.host
            retstr += Colors.ENDC
        else:
            retstr += self.host
        if not ((self.is_ssl and self.port == 443) or \
                (not self.is_ssl and self.port == 80) or \
                self.explicit_port):
            if colored:
                retstr += ':'
                retstr += Colors.MAGENTA
                retstr += str(self.port)
                retstr += Colors.ENDC
            else:
                retstr += ':%d' % self.port
        if (self.path and self.path != '/') or always_have_path:
            if colored:
                retstr += path_formatter(self.path)
            else:
                retstr += self.path
        if self.url_params:
            retstr += '?'
            pairs = []
            for p in self.url_params.all_pairs():
                if p[1] is None:
                    pairs.append(p)
                else:
                    pairs.append('='.join(p))
            retstr += '&'.join(pairs)
        if self.fragment:
            retstr += '#%s' % self.fragment
        return retstr

    @property
    def url(self):
        """
        The full url of the request including url params, protocol, etc.
        ie `https://www.google.com`, `http://foo.fakewebsite.com:1234/path?a=b`.
        When setting the URL, the port, is_ssl, path, url params, host, etc are all
        automatically updated.

        :getter: Returns the url of the request
        :setter: Sets the url of the request and updates metadata
        :type: string
        """
        return self._url_helper(False)

    @property
    def url_color(self):
        """
        same as .url, except colored. Used for printing URLs to the terminal.

        :getter: Returns the url of the request
        :type: string
        """
        return self._url_helper(True)
        
    @url.setter
    def url(self, val):
        self._handle_statusline_uri(val)

    @property
    def host(self):
        """
        The host of the request. ie `www.google.com`.

        :getter: Returns the host of the request
        :setter: Changes the host of the request and updates the Host header
        :type: string
        """
        return self._host
        
    @host.setter
    def host(self, val):
        self._host = val
        self.headers.update('Host', val, do_callback=False)
        
    @property
    def is_ssl(self):
        """
        Whether the request is sent over SSL

        :getter: Returns if the request is sent over SSL
        :setter: Sets if the request is sent over SSL
        :type: Bool
        """
        return self._is_ssl
        
    @is_ssl.setter
    def is_ssl(self, val):
        if val:
            self._is_ssl = True
            if self.port == 80:
                self.port = 443
        else:
            self._is_ssl = False
            if self.port == 443:
                self.port = 80

    @property
    def saved(self):
        """
        If the request is saved in the data file

        :getter: Returns True if the request is saved in the data file
        :type: Bool
        """
        if self.reqid is None:
            return False
        try:
            _ = int(self.reqid)
            return True
        except (ValueError, TypeError):
            return False
        
    @property
    def path_tuple(self):
        """
        The path in tuple form starting with the host. For example, path_parts for
        a request to http://www.example.com/foo/bar.php would be::

          ('www.example.com', 'foo', 'bar.php')
        
        :getter: Returns the path in tuple form
        :type: Tuple
        """
        # the first element is blank because the path always starts with /
        ret = [self.host] + self.path.split('/')[1:]
        if ret[-1] == '':
            ret = ret[:-1]
        return tuple(ret)

    @property
    def sort_time(self):
        """
        If the request has a submit time, returns the submit time's unix timestamp.
        Returns 0 otherwise
        """
        if self.time_start:
            return time.mktime(self.time_start.timetuple())
        else:
            return 0

    ###########
    ## Metadata

    def get_metadata(self, include_unique=True):
        data = {}
        if self.port is not None:
            data['port'] = self.port
        data['is_ssl'] = self.is_ssl
        data['host'] = self.host
        data['reqid'] = self.reqid
        if self.response:
            data['response_id'] = self.response.rspid
        data['tags'] = list(self.tags)
        if not include_unique:
            for k in self.metadata_unique_keys:
                if k in data:
                    del data[k]
        return data

    def set_metadata(self, data):
        if 'reqid' in data:
            self.reqid = data['reqid']
        if 'is_ssl' in data:
            self.is_ssl = data['is_ssl']
        if 'host' in data:
            self._host = data['host']
        if 'port' in data:
            self.port = data['port']
        if 'tags' in data:
            self.tags = set(data['tags'])

    def reset_metadata(self):
        self.port = 80
        self.is_ssl = False
        self.reqid = None
        self._host = ''
        self.tags = set()

    def get_plugin_dict(self, name):
        """
        Get the data dictionary for the given plugin name.
        """
        if not name in self.plugin_data:
            self.plugin_data[name] = {}
        return self.plugin_data[name]

    def clear(self):
        HTTPMessage.clear(self)
        self.time_end = None
        self.time_start = None
        self.cookies = RepeatableDict()
        self.fragment = None
        self.url_params = RepeatableDict()
        self._is_ssl = False
        self.path = ''
        self.post_params = RepeatableDict()
        self.response = None
        self.submitted = False
        self.unmangled = None
        self.verb = ''
        self.version = ''
        self.plugin_data = {}
        self.reset_metadata()
        self.is_unmangled_version = False
        self.path_type = PATH_RELATIVE
        self.explicit_port = False

    ############################
    ## Internal update functions

    def _set_dict_callbacks(self):
        # Add callbacks to dicts
        def f1():
            obj = weakref.proxy(self)
            obj.update_from_headers()
        def f2():
            obj = weakref.proxy(self)
            obj._update_from_objects()
        self.headers.set_modify_callback(f1)
        self.cookies.set_modify_callback(f2)
        self.post_params.set_modify_callback(f2)
        
    def update_from_body(self):
        # Updates metadata that's based off of data
        HTTPMessage.update_from_body(self)
        if 'content-type' in self.headers:
            if 'application/x-www-form-urlencoded' in self.headers['content-type']:
                self.post_params = repeatable_parse_qs(self.body)
                self._set_dict_callbacks()

    def _update_from_objects(self):
        # Updates text values that depend on objects.
        # DOES NOT MAINTAIN HEADER DUPLICATION, ORDER, OR CAPITALIZATION
        if self.cookies:
            assignments = []
            for ck, cv in self.cookies.all_pairs():
                asn = '%s=%s' % (ck, cv)
                assignments.append(asn)
            header_val = '; '.join(assignments)
            self.headers.update('Cookie', header_val, do_callback=False)
        elif 'Cookie' in self.headers:
            del self.headers['Cookie']

        if self.post_params:
            pairs = []
            for k, v in self.post_params.all_pairs():
                pairs.append('%s=%s' % (k, v))
            self.headers['Content-Type'] =  'application/x-www-form-urlencoded'
            self.body = '&'.join(pairs)

    def update_from_headers(self):
        # Updates metadata that depends on header/status line values
        self.cookies = RepeatableDict()
        self._set_dict_callbacks()
        for k, v in self.headers.all_pairs():
            self.handle_header(k, v)

    def _sort_websocket_messages(self):
        """
        Sort websocket message list by their submission time
        """
        def sort_key(mes):
            if not mes.time_sent:
                return datetime.datetime(1970,1,1)
            return mes.time_sent
        self.websocket_messages = sorted(self.websocket_messages, key=sort_key)
        
    def add_websocket_message(self, mes):
        # Right now just insert and sort. We'll do a better structure later
        mes.parent_request = self
        self.websocket_messages.append(mes)
        self._sort_websocket_messages()

    def set_websocket_messages(self, msgs):
        self.websocket_messages = msgs
        self._sort_websocket_messages()

    ###############
    ## Data parsing
            
    def _process_host(self, hostline):
        # Get address and port
        # Returns true if port was explicitly stated
        # Used only for processing host header
        port_given = False
        if ':' in hostline:
            self._host, self.port = hostline.split(':')
            self.port = int(self.port)
            if self.port == 443:
                self._is_ssl = True
            port_given = True
        else:
            self._host = hostline
            if not self.port:
                self.port = 80
        self._host.strip()
        return port_given
            
    def _handle_statusline_uri(self, uri):
        if not re.match('(?:^.+)://', uri):
            uri = '//' + uri

        parsed_path = urlparse.urlparse(uri)
        netloc = parsed_path.netloc
        port_given = False
        if netloc:
            port_given = self._process_host(netloc)

        if re.match('^https://', uri) or self.port == 443:
            self._is_ssl = True
            if not port_given:
                self.port = 443
        if re.match('^http://', uri):
            self._is_ssl = False

        if not self.port:
            if self.is_ssl:
                self.port = 443
            else:
                self.port = 80

        reqpath = parsed_path.path
        if parsed_path.path:
            self.path = parsed_path.path
        else:
            self.path = '/'
        if parsed_path.query:
            reqpath += '?'
            reqpath += parsed_path.query
            self.url_params = repeatable_parse_qs(parsed_path.query)
        if parsed_path.fragment:
            reqpath += '#'
            reqpath += parsed_path.fragment
            self.fragment = parsed_path.fragment
        
    def handle_start_line(self, start_line):
        #HTTPMessage.handle_start_line(self, start_line)
        if start_line == '':
            self.verb = ''
            self.path = ''
            self.version = ''
            return
        parts = start_line.split()
        uri = None
        if len(parts) == 3:
            self.verb, uri, self.version = parts
        elif len(parts) == 2:
            self.verb, self.version = parts
        else:
            raise Exception("Unexpected format of first line of request")

        # Get path using urlparse
        if uri is not None:
            self._handle_statusline_uri(uri)
                
    def handle_header(self, key, val):
        # We may have duplicate headers
        if val is None:
            return True
        keep = HTTPMessage.handle_header(self, key, val)
        if not keep:
            return False

        stripped = False
        if key.lower() == 'cookie':
            # We still want the raw key/val for the cookies header
            # because it's still a header
            cookie_strs = val.split('; ')

            # The only whitespace that matters is the space right after the
            # semicolon. If actual implementations mess this up, we could
            # probably strip whitespace around the key/value
            for cookie_str in cookie_strs:
                if '=' in cookie_str:
                    splitted = cookie_str.split('=',1)
                    assert(len(splitted) == 2)
                    (cookie_key, cookie_val) = splitted
                else:
                    cookie_key = cookie_str
                    cookie_val = ''
                # we want to parse duplicate cookies
                self.cookies.append(cookie_key, cookie_val, do_callback=False)
        elif key.lower() == 'host':
            self._process_host(val)
        elif re.match('^proxy.*', key.lower()):
            stripped = True

        return (not stripped)
    
    def body_complete(self):
        HTTPMessage.body_complete(self)
        if 'content-type' in self.headers:
            if self.headers['content-type'] == 'application/x-www-form-urlencoded':
                self.post_params = repeatable_parse_qs(self.body)
                self._set_dict_callbacks()
                
    #######################
    ## Data store functions
                
    def save_in_mem(self, cust_cache=None):
        if cust_cache:
            use_cache = cust_cache
        else:
            use_cache = Request.cache
        if not self.reqid:
            use_cache.add(self)
    
    @defer.inlineCallbacks
    def async_save(self, cust_dbpool=None, cust_cache=None):
        """
        async_save()
        Save/update the request in the data file. Returns a twisted deferred which
        fires when the save is complete.

        :rtype: twisted.internet.defer.Deferred
        """
        from .pappy import main_context
        if not self.complete:
            raise PappyException('Cannot save incomplete messages')

        global dbpool
        if cust_dbpool:
            use_dbpool = cust_dbpool
            use_cache = cust_cache
        else:
            use_dbpool = dbpool
            use_cache = Request.cache

        assert(use_dbpool)
        if not self.reqid:
            self.reqid = '--'
        try:
            # Check for intyness
            _ = int(self.reqid)

            # If we have reqid, we're updating
            yield use_dbpool.runInteraction(self._update)
            assert(self.reqid is not None)
            yield use_dbpool.runInteraction(self._update_tags)
        except (ValueError, TypeError):
            # Either no id or in-memory
            yield use_dbpool.runInteraction(self._insert)
            assert(self.reqid is not None)
            yield use_dbpool.runInteraction(self._update_tags)
        if use_cache:
            use_cache.add(self)
        main_context.cache_reset()

    @crochet.wait_for(timeout=180.0)
    @defer.inlineCallbacks
    def save(self):
        """
        save()
        Save/update the request in the data file.
        Saves the request, its unmangled version, the response, and the unmanbled response.
        Cannot be called from inside an async function.
        """

        yield self.async_deep_save()
            
    @defer.inlineCallbacks
    def async_deep_save(self):
        """
        async_deep_save()
        Saves self, unmangled, response, unmangled response, and websocket messages. Returns a deferred
        which fires after everything has been saved.

        :rtype: twisted.internet.defer.Deferred
        """

        if self.response:
            if self.response.unmangled:
                yield self.response.unmangled.async_save()
            yield self.response.async_save()
        if self.unmangled:
            yield self.unmangled.async_save()
        for m in self.websocket_messages:
            yield m.async_deep_save()
        yield self.async_save()

    def _update_tags(self, txn):
        # This should never be called on an unsaved or in-memory request
        txn.execute(
            """
            DELETE FROM tagged WHERE reqid=?;
            """,
            (self.reqid,)
        )

        tagids = []
        tags_to_add = []
        # Find ids that already exist
        for tag in self.tags:
            txn.execute(
                """
                SELECT id, tag FROM tags WHERE tag=?;
                """,
                (tag,)
            )
            result = txn.fetchall()
            if len(result) == 0:
                tags_to_add.append(tag)
            else:
                tagid = int(result[0][0])
                tagids.append(tagid)

        # Add new tags
        for tag in tags_to_add:
            txn.execute(
                """
                INSERT INTO tags (tag) VALUES (?);
                """,
                (tag,)
            )
            tagids.append(int(txn.lastrowid))

        # Tag our request
        for tagid in tagids:
            txn.execute(
                """
                INSERT INTO tagged (reqid, tagid) VALUES (?, ?);
                """,
                (int(self.reqid), tagid)
            )
            
    def _update(self, txn):
        # If we don't have an reqid, we're creating a new reuqest row
        setnames = ["full_request=?", "port=?"]
        queryargs = [self.full_request, self.port]
        if self.response:
            setnames.append('response_id=?')
            assert(self.response.rspid is not None) # should be saved first
            queryargs.append(self.response.rspid)
        if self.unmangled:
            setnames.append('unmangled_id=?')
            assert(self.unmangled.reqid is not None) # should be saved first
            queryargs.append(self.unmangled.reqid)
        if self.time_start:
            setnames.append('start_datetime=?')
            queryargs.append((self.time_start-datetime.datetime(1970,1,1)).total_seconds())
        if self.time_end:
            setnames.append('end_datetime=?')
            queryargs.append((self.time_end-datetime.datetime(1970,1,1)).total_seconds())

        setnames.append('is_ssl=?')
        if self.is_ssl:
            queryargs.append('1')
        else:
            queryargs.append('0')

        setnames.append('submitted=?')
        if self.submitted:
            queryargs.append('1')
        else:
            queryargs.append('0')

        setnames.append('host=?')
        if self.host:
            queryargs.append(self.host)
        else:
            queryargs.append('')
        
        setnames.append('plugin_data=?')
        if self.plugin_data:
            queryargs.append(json.dumps(self.plugin_data))
        else:
            queryargs.append('{}')

        queryargs.append(self.reqid)
        txn.execute(
            """
            UPDATE requests SET %s WHERE id=?;
            """ % ','.join(setnames),
            tuple(queryargs)
        )

    def _insert(self, txn):
        # If we don't have an reqid, we're creating a new reuqest row
        colnames = ["full_request", "port"]
        colvals = [self.full_request, self.port]
        if self.response and self.response.rspid:
            colnames.append('response_id')
            colvals.append(self.response.rspid)
        if self.unmangled and self.unmangled.reqid:
            colnames.append('unmangled_id')
            colvals.append(self.unmangled.reqid)
        if self.time_start:
            colnames.append('start_datetime')
            colvals.append((self.time_start-datetime.datetime(1970,1,1)).total_seconds())
        if self.time_end:
            colnames.append('end_datetime')
            colvals.append((self.time_end-datetime.datetime(1970,1,1)).total_seconds())
        colnames.append('submitted')
        if self.submitted:
            colvals.append('1')
        else:
            colvals.append('0')

        colnames.append('is_ssl')
        if self.is_ssl:
            colvals.append('1')
        else:
            colvals.append('0')

        colnames.append('host')
        if self.host:
            colvals.append(self.host)
        else:
            colvals.append('')

        colnames.append('plugin_data')
        if self.plugin_data:
            colvals.append(json.dumps(self.plugin_data))
        else:
            colvals.append('{}')

        txn.execute(
            """
            INSERT INTO requests (%s) VALUES (%s);
            """ % (','.join(colnames), ','.join(['?']*len(colvals))),
            tuple(colvals)
        )
        self.reqid = str(txn.lastrowid)
        assert txn.lastrowid is not None
        assert self.reqid is not None
            
    @defer.inlineCallbacks
    def delete(self, cust_dbpool=None, cust_cache=None):
        from .context import reset_context_caches

        global dbpool
        if cust_dbpool:
            use_dbpool = cust_dbpool
            use_cache = cust_cache
        else:
            use_dbpool = dbpool
            use_cache = Request.cache

        if self.reqid is None:
            raise PappyException("Cannot delete request with id=None")

        if use_cache:
            use_cache.evict(self.reqid)
            Request.cache.all_ids.remove(self.reqid)
            if self.reqid in Request.cache.ordered_ids:
                Request.cache.ordered_ids.remove(self.reqid)
            if self.reqid in Request.cache.req_times:
                del Request.cache.req_times[self.reqid]
            if self.reqid in Request.cache.inmem_reqs:
                Request.cache.inmem_reqs.remove(self.reqid)
            if self.reqid in Request.cache.unmangled_ids:
                Request.cache.unmangled_ids.remove(self.reqid)

        reset_context_caches()

        if self.reqid[0] != 'm':
            yield use_dbpool.runQuery(
                """
                DELETE FROM requests WHERE id=?;
                """,
                (self.reqid,)
                )
            yield use_dbpool.runQuery(
                """
                DELETE FROM tagged WHERE reqid=?;
                """,
                (self.reqid,)
            )
        self.reqid = None

    @defer.inlineCallbacks
    def deep_delete(self):
        """
        deep_delete()
        Delete a request, its unmangled version, its response, and its response's
        unmangled version from history. Also removes the request from all contexts.
        Returns a Twisted deferred.

        :rtype: Deferred
        """
        if self.unmangled:
            yield self.unmangled.delete()
        if self.response:
            if self.response.unmangled:
                yield self.response.unmangled.delete()
            yield self.response.delete()
        yield self.delete()

    @staticmethod
    def _gen_sql_row(tablename=None):
        template = "{pre}full_request, {pre}response_id, {pre}id, {pre}unmangled_id, {pre}start_datetime, {pre}end_datetime, {pre}port, {pre}is_ssl, {pre}host, {pre}plugin_data"
        if tablename:
            return template.format(pre=('%s.'%tablename))
        else:
            return template.format(pre='')
        
    @staticmethod
    @defer.inlineCallbacks
    def _load_request_ws_messages(req):
        ws_messages = yield Request._async_load_ws_by_parent(req.reqid)
        req.set_websocket_messages(ws_messages)
        
    @staticmethod
    @defer.inlineCallbacks
    def _from_sql_row(row, cust_dbpool=None, cust_cache=None):
        from .http import Request

        global dbpool

        if cust_dbpool:
            use_dbpool = cust_dbpool
        else:
            use_dbpool = dbpool

        req = Request(row[0])
        if row[1]:
            rsp = yield Response.load_response(str(row[1]),
                                               cust_dbpool=cust_dbpool,
                                               cust_cache=cust_cache)
            req.response = rsp
        if row[3]:
            unmangled_req = yield Request.load_request(str(row[3]),
                                                       cust_dbpool=cust_dbpool,
                                                       cust_cache=cust_cache)
            req.unmangled = unmangled_req
            req.unmangled.is_unmangled_version = True
        if row[4]:
            req.time_start = datetime.datetime.utcfromtimestamp(row[4])
        if row[5]:
            req.time_end = datetime.datetime.utcfromtimestamp(row[5])
        if row[6] is not None:
            req.port = int(row[6])
        if row[7] == 1:
            req._is_ssl = True
        if row[8]:
            req._host = row[8]
        if row[9]:
            req.plugin_data = json.loads(row[9])
        req.reqid = str(row[2])

        # tags
        rows = yield use_dbpool.runQuery(
            """
            SELECT tg.tag
            FROM tagged tgd, tags tg
            WHERE tgd.tagid=tg.id AND tgd.reqid=?;
            """,
            (req.reqid,)
        )
        req.tags = set()
        for row in rows:
            req.tags.add(row[0])
        yield Request._load_request_ws_messages(req)
        defer.returnValue(req)

    @staticmethod
    @defer.inlineCallbacks
    def load_requests_by_time(first, num, cust_dbpool=None, cust_cache=None):
        """
        load_requests_by_time()
        Load all the requests in the data file and return them in a list.
        Returns a deferred which calls back with the list of requests when complete.

        :rtype: twisted.internet.defer.Deferred
        """
        from .http import Request

        global dbpool
        if cust_dbpool:
            use_dbpool = cust_dbpool
            use_cache = cust_cache
        else:
            use_dbpool = dbpool
            use_cache = Request.cache

        if use_cache:
            starttime = use_cache.req_times[first]
            rows = yield use_dbpool.runQuery(
                """
                SELECT %s
                FROM requests
                WHERE start_datetime<=? ORDER BY start_datetime desc LIMIT ?;
                """ % Request._gen_sql_row(), (starttime, num)
                )
        else:
            rows = yield use_dbpool.runQuery(
                """
                SELECT %s
                FROM requests r1, requests r2
                WHERE r2.id=? AND
                r1.start_datetime<=r2.start_datetime
                ORDER BY start_datetime desc LIMIT ?;
                """ % Request._gen_sql_row('r1'), (first, num)
                )
        reqs = []
        for row in rows:
            req = yield Request._from_sql_row(row, cust_dbpool=cust_dbpool, cust_cache=cust_cache)
            reqs.append(req)
        defer.returnValue(reqs)

    @staticmethod
    @defer.inlineCallbacks
    def load_requests_by_tag(tag, cust_dbpool=None, cust_cache=None):
        """
        load_requests_by_tag(tag)
        Load all the requests in the data file with a given tag and return them in a list.
        Returns a deferred which calls back with the list of requests when complete.

        :rtype: twisted.internet.defer.Deferred
        """
        from .http import Request

        global dbpool
        if cust_dbpool:
            use_dbpool = cust_dbpool
        else:
            use_dbpool = dbpool

        # tags
        rows = yield use_dbpool.runQuery(
            """
            SELECT tgd.reqid
            FROM tagged tgd, tags tg
            WHERE tgd.tagid=tg.id AND tg.tag=?;
            """,
            (tag,)
        )
        reqs = []
        for row in rows:
            req = Request.load_request(row[0],
                                       cust_dbpool=cust_dbpool,
                                       cust_cache=cust_cache)
            reqs.append(req)
        defer.returnValue(reqs)
        
    @staticmethod
    @defer.inlineCallbacks
    def load_request(to_load, allow_special=True, use_cache=True, cust_dbpool=None, cust_cache=None):
        """
        load_request(to_load)
        Load a request with the given request id and return it.
        Returns a deferred which calls back with the request when complete.

        :param allow_special: Whether to allow special IDs such as ``u##`` or ``s##``
        :type allow_special: bool
        :param use_cache: Whether to use the cache. If set to false, it will always query the data file to get the request
        :type use_cache: bool

        :rtype: twisted.internet.defer.Deferred
        """
        global dbpool

        if cust_dbpool:
            use_dbpool = cust_dbpool
            cache_to_use = cust_cache
        else:
            use_dbpool = dbpool
            cache_to_use = Request.cache

        if not use_dbpool:
            raise PappyException('No database connection to load from')

        if to_load == '--':
            raise PappyException('Invalid request ID. Wait for it to save first.')
        
        if not allow_special:
            try:
                int(to_load)
            except (ValueError, TypeError):
                raise PappyException('Cannot load special id %s' % to_load)

        ret_unmangled = False
        rsp_unmangled = False
        if to_load[0] == 'u':
            ret_unmangled = True
            loadid = to_load[1:]
        elif to_load[0] == 's':
            rsp_unmangled = True
            loadid = to_load[1:]
        else:
            loadid = to_load

        def retreq(r):
            if ret_unmangled:
                if not r.unmangled:
                    raise PappyException("Request %s was not mangled"%r.reqid)
                return r.unmangled.duplicate()
            if rsp_unmangled:
                if not r.response:
                    raise PappyException("Request %s does not have a response" % r.reqid)
                if not r.response.unmangled:
                    raise PappyException("Response to request %s was not mangled" % r.reqid)
                retreq = r.duplicate()
                retreq.response = retreq.response.unmangled
                return retreq
            else:
                return r.duplicate()

        # Get it through the cache
        if use_cache and cache_to_use:
            # If it's not cached, load_request will be called again and be told
            # not to use the cache.
            r = yield cache_to_use.get(loadid)
            defer.returnValue(retreq(r))

        # Load it from the data file
        rows = yield use_dbpool.runQuery(
            """
            SELECT %s
            FROM requests
            WHERE id=?;
            """ % Request._gen_sql_row(),
            (loadid,)
            )
        if len(rows) != 1:
            raise PappyException("Request with id %s does not exist" % loadid)
        req = yield Request._from_sql_row(rows[0], cust_dbpool=cust_dbpool, cust_cache=cust_cache)
        assert req.reqid == loadid
        if cache_to_use:
            cache_to_use.add(req)
        defer.returnValue(retreq(req))

    @staticmethod
    @defer.inlineCallbacks
    def _async_load_ws(msgid, cust_dbpool=None):
        global dbpool
        if cust_dbpool:
            use_dbpool = cust_dbpool
        else:
            use_dbpool = dbpool
        assert(use_dbpool)
        rows = yield use_dbpool.runQuery(
            """
            SELECT id,parent_request,unmangled_id,is_binary,direction,time_sent,contents
            FROM websocket_messages
            WHERE id=?;
            """,
            (int(msgid),)
            )
        if len(rows) == 0:
            raise PappyException("No websocket message with id=%s" % msgid)
        assert(len(rows) == 1)
        row = rows[0]
        m = WebSocketMessage()
        m.msgid = row[0]
        #if load_parent:
        #    m.parent_request = yield Request.load_request(str(row[1]))
        if row[2]:
            m.unmangled = yield Request._async_load_ws(str(row[2]))
        if row[3] >= 0:
            m.is_binary = True
        else:
            m.is_binary = False
        if row[4] == 0:
            m.direction = 'OUTGOING'
        else:
            m.direction = 'INCOMING'
        if row[5] is not None:
            m.time_sent = datetime.datetime.utcfromtimestamp(row[5])
        m.contents = row[6]
        defer.returnValue(m)

    @staticmethod
    @defer.inlineCallbacks
    def _async_load_ws_by_parent(reqid, cust_dbpool=None):
        global dbpool
        if cust_dbpool:
            use_dbpool = cust_dbpool
        else:
            use_dbpool = dbpool
        assert(use_dbpool)
        rows = yield use_dbpool.runQuery(
            """
            SELECT id
            FROM websocket_messages
            WHERE parent_request=?;
            """,
            (int(reqid),)
            )
        messages = []
        # Yes we could do it in one query but we'll deal with it if it causes
        # performance issues
        for row in rows:
            m = yield Request._async_load_ws(row[0])
            messages.append(m)
        defer.returnValue(messages)

    ######################
    ## Submitting Requests

    @staticmethod
    @defer.inlineCallbacks
    def submit_raw_request(message, host, port, is_ssl, mangle=False, int_macros=[]):
        """
        Submits a request to the target host and returns a request object
        """
        from pappyproxy.plugin import active_intercepting_macros

        use_int_macros = int_macros
        if mangle:
            use_int_macros = active_intercepting_macros()

        proxy_protocol = HTTPProtocolProxy(addr=(host, port, is_ssl),
                                           int_macros=use_int_macros,
                                           save_requests=False)
        d = proxy_protocol.get_next_response()
        proxy_protocol.client_data_received(message)
        retreq = yield d
        proxy_protocol.close_connections()
        defer.returnValue(retreq)
        
    @defer.inlineCallbacks
    def async_submit(self, mangle=False):
        """
        async_submit()
        Same as :func:`~pappyproxy.http.Request.submit` but generates deferreds.
        Submits the request using its host, port, etc. and updates its response value
        to the resulting response.

        :param mangle: Whether to pass the request through active intercepting macros.
        :type mangle: Bool

        :rtype: Twisted deferred
        """
        from pappyproxy.plugin import active_intercepting_macros
        
        newreq = yield Request.submit_raw_request(self.full_message, self.host, self.port,
                                                  self.is_ssl, mangle=mangle)
        self.unmangled = newreq.unmangled
        self.response = newreq.response
        self.time_start = newreq.time_start
        self.time_end = newreq.time_end
        self.set_metadata(newreq.get_metadata())

    @crochet.wait_for(timeout=180.0)
    @defer.inlineCallbacks
    def submit(self, *args, **kwargs):
        """
        submit()
        Submits the request using its host, port, etc. and updates its response value
        to the resulting response.
        Cannot be called in async functions.
        If an error is encountered while submitting the request, it is printed
        to the console.
        This is what you should use to submit your requests in macros.
        """
        try:
            yield self.async_submit(*args, **kwargs)
        except Exception as e:
            print 'Submitting request to %s failed: %s' % (self.host, str(e))


class Response(HTTPMessage):
    """
    :ivar cookies: Cookies set by the response
    :vartype cookies: RepeatableDict of ResponseCookie objects
    :ivar response_code: The response code of the response
    :vartype response_code: Integer
    :ivar response_text: The text associated with the response code (ie OK, NOT FOUND, etc)
    :vartype response_text: String
    :ivar rspid: If the response is saved in the data file, the id of the response
    :vartype rspid: String
    :ivar unmangled: If the response was mangled, the unmangled version of the response
    :vartype unmangled: Response
    :ivar version: The version part of the status line (ie HTTP/1.1)
    :vartype version: String
    """

    def __init__(self, full_response=None, update_content_length=True):
        # Resets instance variables
        self.clear()

        # Called after instance vars since some callbacks depend on
        # instance vars
        HTTPMessage.__init__(self, full_response, update_content_length)

        # metadata that is unique to a specific Response instance
        self.metadata_unique_keys = ('rspid',)
        
        # After message init so that other instance vars are initialized
        self._set_dict_callbacks()

    def __copy__(self):
        if not self.complete:
            raise PappyException("Cannot copy incomplete http messages")
        retrsp = self.__class__(self.full_message)
        retrsp.set_metadata(self.get_metadata())
        retrsp.rspid = None
        if self.unmangled:
            retrsp.unmangled = self.unmangled.copy()
        return retrsp

    def duplicate(self):
        retrsp = self.copy()
        retrsp.rspid = self.rspid
        if self.unmangled:
            retrsp.unmangled = self.unmangled.duplicate()
        return retrsp

    @property
    def raw_headers(self):
        """
        Alias for Response.headers_section

        :getter: Returns the raw text of the headers including the extra newline at the end.
        :type: string
        """
        return self.headers_section

    @property
    def start_line(self):
        """
        The status line of the response. ie `HTTP/1.1 200 OK`

        :getter: Returns the status line of the response
        :setter: Sets the status line of the response
        :type: string
        """
        if not self.version and self.response_code == 0 and not self.version:
            return ''
        if self.response_text == '':
            return '%s %d' % (self.version, self.response_code)
        else:
            return '%s %d %s' % (self.version, self.response_code, self.response_text)

    @start_line.setter
    def start_line(self, val):
        self.handle_start_line(val)

    @property
    def status_line(self):
        return self.start_line
        
    @status_line.setter
    def status_line(self, val):
        self.start_line = val

    @property
    def raw_data(self):
        """
        Alias for Response.body

        :getter: Returns the data portion of the response
        :setter: Set the data of the response and update metadata
        :type: string
        """
        return self.body
        
    @raw_data.setter
    def raw_data(self, val):
        self.body = val

    @property
    def full_response(self):
        """
        The full text of the response including the headers and data.
        Alias for Response.full_message

        :getter: Returns the full text of the response
        :type: string
        """
        return self.full_message

    @property
    def soup(self):
        """
        Returns a beautifulsoup4 object for parsing the html of the response

        :getter: Returns a BeautifulSoup object representing the html of the response
        """
        return bs4.BeautifulSoup(self.body, 'lxml')
    
    ###########
    ## Metadata

    def get_metadata(self, include_unique=True):
        data = {}
        data['rspid'] = self.rspid
        if not include_unique:
            for k in self.metadata_unique_keys:
                if k in data:
                    del data[k]
        return data

    def set_metadata(self, data):
        if 'rspid' in data:
            self.rspid = data['rspid']

    def reset_metadata(self):
        self.rspid = None

    def clear(self):
        HTTPMessage.clear(self)
        self.cookies = RepeatableDict()
        self.response_code = 0
        self.response_text = ''
        self.rspid = None
        self.unmangled = None
        self.version = ''
    
    ############################
    ## Internal update functions
    
    def _set_dict_callbacks(self):
        # Add callbacks to dicts
        def f1():
            obj = weakref.proxy(self)
            obj.update_from_headers()
        def f2():
            obj = weakref.proxy(self)
            obj._update_from_objects()
        self.headers.set_modify_callback(f1)
        self.cookies.set_modify_callback(f2)

    def update_from_body(self):
        HTTPMessage.update_from_body(self)

    def _update_from_objects(self):
        # Updates headers from objects
        # DOES NOT MAINTAIN HEADER DUPLICATION, ORDER, OR CAPITALIZATION

        # Cookies
        new_headers = RepeatableDict()
        cookies_added = False
        for pair in self.headers.all_pairs():
            if pair[0].lower() == 'set-cookie':
                # If we haven't added our cookies, add them all. Otherwise
                # strip the header (do nothing)
                if not cookies_added:
                    # Add all our cookies here
                    for k, c in self.cookies.all_pairs():
                        new_headers.append('Set-Cookie', c.cookie_str)
                    cookies_added = True
            else:
                new_headers.append(pair[0], pair[1])

        if not cookies_added:
            # Add all our cookies to the end
            for k, c in self.cookies.all_pairs():
                new_headers.append('Set-Cookie', c.cookie_str)

        self.headers = new_headers
        self._set_dict_callbacks()
                
    def update_from_headers(self):
        self.cookies = RepeatableDict()
        self._set_dict_callbacks()
        for k, v in self.headers.all_pairs():
            if k.lower() == 'set-cookie':
                # Parse the cookie
                cookie = ResponseCookie(v)
                self.cookies.append(cookie.key, cookie, do_callback=False)

    ###############
    ## Data parsing
        
    def handle_start_line(self, start_line):
        if start_line == '':
            self.response_code = 0
            self.version = ''
            self.response_text = ''
            return
        self._first_line = False
        if len(start_line.split(' ')) > 2:
            self.version, self.response_code, self.response_text = \
                                                start_line.split(' ', 2)
        else:
            self.version, self.response_code = start_line.split(' ', 1)
            self.response_text = ''
        self.response_code = int(self.response_code)

        if self.response_code == 304 or self.response_code == 204 or \
            self.response_code/100 == 1:
            self._end_after_headers = True

    def handle_header(self, key, val):
        if val is None:
            return True
        keep = HTTPMessage.handle_header(self, key, val)
        if not keep:
            return False

        stripped = False
        if key.lower() == 'set-cookie':
            cookie = ResponseCookie(val)
            self.cookies.append(cookie.key, cookie, do_callback=False)

        if stripped:
            return False
        else:
            return True

    ####################
    ## Cookie management
            
    def add_cookie(self, cookie):
        """
        Add a :class:`pappyproxy.http.ResponseCookie` to the response.

        .. warning::
            This will add duplicate cookies. If you want to add a cookie you're not sure exists,
            use :func:`~pappyproxy.http.Response.set_cookie`
        """
        self.cookies.append(cookie.key, cookie)

    def set_cookie(self, cookie):
        """
        Set a cookie in the response. ``cookie`` must be a :class:`pappyproxy.http.ResponseCookie`
        """
        self.cookies[cookie.key] = cookie

    def set_cookie_kv(self, key, val):
        """
        Set a cookie by key and value. Will not have path, secure, etc set at all.
        """
        cookie = ResponseCookie()
        cookie.key = key
        cookie.val = val
        self.cookies[cookie.key] = cookie

    def delete_cookie(self, key):
        """
        Delete a cookie from the response by its key
        """
        del self.cookies[key]

    #######################
    ## Database interaction
        
    @defer.inlineCallbacks
    def async_save(self, cust_dbpool=None, cust_cache=None):
        """
        async_save()
        Save/update the just request in the data file. Returns a twisted deferred which
        fires when the save is complete. It is suggested that you use
        :func: `~pappyproxy.http.Request.async_deep_save` instead to save responses.

        :rtype: twisted.internet.defer.Deferred
        """
        if not self.complete:
            raise PappyException('Cannot save incomplete messages')
        global dbpool
        if cust_dbpool:
            use_dbpool = cust_dbpool
        else:
            use_dbpool = dbpool
        assert(use_dbpool)
        try:
            # Check for intyness
            _ = int(self.rspid)

            # If we have rspid, we're updating
            yield use_dbpool.runInteraction(self._update)
        except (ValueError, TypeError):
            yield use_dbpool.runInteraction(self._insert)
        assert(self.rspid is not None)

    # Right now responses without requests are unviewable
    # @crochet.wait_for(timeout=180.0)
    # @defer.inlineCallbacks
    # def save(self):
    #     yield self.save()
        
    def _update(self, txn):
        setnames = ["full_response=?"]
        queryargs = [self.full_response]
        if self.unmangled:
            setnames.append('unmangled_id=?')
            assert(self.unmangled.rspid is not None) # should be saved first
            queryargs.append(self.unmangled.rspid)

        queryargs.append(self.rspid)
        txn.execute(
            """
            UPDATE responses SET %s WHERE id=?;
            """ % ','.join(setnames),
            tuple(queryargs)
            )
        assert(self.rspid is not None)
            
    def _insert(self, txn):
        # If we don't have an rspid, we're creating a new one
        colnames = ["full_response"]
        colvals = [self.full_response]
        if self.unmangled is not None:
            colnames.append('unmangled_id')
            assert(self.unmangled.rspid is not None) # should be saved first
            colvals.append(self.unmangled.rspid)

        txn.execute(
            """
            INSERT INTO responses (%s) VALUES (%s);
            """ % (','.join(colnames), ','.join(['?']*len(colvals))),
            tuple(colvals)
            )
        self.rspid = str(txn.lastrowid)
        assert(self.rspid is not None)

    @defer.inlineCallbacks
    def delete(self):
        if self.rspid is not None:
            yield dbpool.runQuery(
                """
                DELETE FROM responses WHERE id=?;
                """,
                (self.rspid,)
                )
        self.rspid = None

    @staticmethod
    def is_ws_upgrade(rsp):
        if rsp.response_code != 101:
            return False
        if 'Upgrade' not in rsp.headers:
            return False
        if 'Connection' not in rsp.headers:
            return False
        if rsp.headers['Upgrade'].lower() != 'websocket':
            return False
        if rsp.headers['Connection'].lower() != 'upgrade':
            return False
        return True

    @staticmethod
    @defer.inlineCallbacks
    def load_response(respid, cust_dbpool=None, cust_cache=None):
        """
        Load a response from its response id. Returns a deferred. I don't suggest you use this.

        :rtype: twisted.internet.defer.Deferred
        """
        global dbpool
        if cust_dbpool:
            use_dbpool = cust_dbpool
        else:
            use_dbpool = dbpool

        assert(use_dbpool)
        rows = yield use_dbpool.runQuery(
            """
            SELECT full_response, id, unmangled_id
            FROM responses
            WHERE id=?;
            """,
            (respid,)
            )
        if len(rows) != 1:
            raise PappyException("Response with request id %s does not exist" % respid)
        full_response = rows[0][0]
        resp = Response(full_response)
        resp.rspid = str(rows[0][1])
        if rows[0][2]:
            unmangled_response = yield Response.load_response(int(rows[0][2]),
                                                              cust_dbpool=cust_dbpool,
                                                              cust_cache=cust_cache)
            resp.unmangled = unmangled_response
        defer.returnValue(resp)

class HTTPProtocolProxy(ProtocolProxy):

    CLIENT_STATE_CLOSED = 1
    CLIENT_STATE_HTTP_READY = 2
    CLINET_STATE_WEBSDOCKET_READY = 3
    CLIENT_STATE_WEBSOCKET = 4

    SERVER_STATE_HTTP_READY = 1
    SERVER_STATE_PROCESSING_HTTP_REQUEST = 2
    SERVER_STATE_HTTP_AWAITING_RESPONSE = 3
    SERVER_STATE_HTTP_AWAITING_PROXY_CONNECT = 4
    SERVER_STATE_WEBSOCKET = 5

    BLANK_RESPONSE = ('HTTP/1.1 200 OK\r\n'
                      'Connection: close\r\n'
                      'Cache-control: no-cache\r\n'
                      'Pragma: no-cache\r\n'
                      'Cache-control: no-store\r\n'
                      'Content-Length: 0\r\n'
                      'X-Frame-Options: DENY\r\n\r\n')

    def __init__(self, *args, **kwargs):
        self.request_queue = Queue.Queue()
        self.request = Request()
        self.response = Response()
        self.stream_responses = True
        self.next_rsp_def = None
        self.ws_proxy = None

        if 'int_macros' in kwargs:
            self.custom_macros = True
            self.mangle_macros = kwargs['int_macros']
        else:
            self.custom_macros = False
            self.mangle_macros = []

        if 'save_requests' in kwargs:
            self.save_requests = kwargs['save_requests']
        else:
            self.save_requests = True

        if 'addr' in kwargs:
            self.connect_addr = kwargs['addr']
            self.force_addr = True
        else:
            self.connect_addr = None
            self.force_addr = False

        self.using_upstream_http_proxy = False
        self.was_streaming_responses = self.stream_responses
        self.upstream_http_connected = False

        self.client_state = HTTPProtocolProxy.CLIENT_STATE_CLOSED
        self.server_state = HTTPProtocolProxy.SERVER_STATE_HTTP_READY
        
        ProtocolProxy.__init__(self)

    def _set_client_state(self, state):
        # Updates the state and sets other metadata states
        # (like is_websocket)
        self.client_state = state
        self.log("Changing client state to %s" % self.client_state)

    def _set_server_state(self, state):
        # Updates the state and sets other metadata states
        # (like is_websocket)
        self.server_state = state
        self.log("Changing server state to %s" % self.server_state)

    def get_next_response(self):
        """
        Returns a deferred that fires with the next completed
        request/response pair
        """
        self.next_rsp_def = defer.Deferred()
        return self.next_rsp_def

    def set_connection(self, host, port, use_ssl, use_socks=False):
        """
        If not connected to the given host, port, use_ssl, disconnects
        the current connection and connects to the given endpoint. Otherwise
        does nothing
        """
        self.log("setting connection...")
        if self.conn_host != host or \
           self.conn_port != port or \
           self.conn_is_ssl != use_ssl:
            self.log("Closing connection to old server")
            self.close_server_connection()
        self.connect(host, port, use_ssl, use_socks=use_socks)

    def server_connection_lost(self, reason):
        self.log("Connection to server lost: %s" % str(reason))
        self.log(str(reason.getTraceback()))
        ProtocolProxy.server_connection_lost(self, reason)

    def client_data_received(self, data):
        self.log("cp> %s" % short_data(data))
        if self.client_state != HTTPProtocolProxy.CLIENT_STATE_WEBSOCKET:
            self.request.add_data(data)
            if self.request.complete:
                req = self.request
                self.request = Request()
                self.request_complete(req)
        else:
            self.ws_proxy.client_data_received(data)

    def server_data_received(self, data):
        self.log("rp< %s" % short_data(data))
        if self.client_state != HTTPProtocolProxy.CLIENT_STATE_WEBSOCKET:
            self.response.add_data(data)
            if self.stream_responses:
                self.send_client_data(data)
            if self.response.complete:
                rsp = self.response
                self.response = Response()
                self.response_complete(rsp)
        else:
            self.ws_proxy.server_data_received(data)

    @defer.inlineCallbacks
    def process_request(self, pop_request=True):
        from pappyproxy import context, macros, pappy

        if self.server_state != HTTPProtocolProxy.SERVER_STATE_HTTP_READY:
            self.log("Not ready to process a new HTTP request")
            return
        self._set_server_state(HTTPProtocolProxy.SERVER_STATE_PROCESSING_HTTP_REQUEST)

        if pop_request and self.request_queue.empty():
            #defer.returnValue(None)
            self.log("Request queue is empty, not processing request")
            self._set_server_state(HTTPProtocolProxy.SERVER_STATE_HTTP_READY)
            return

        if pop_request:
            self.waiting_req = self.request_queue.get()

        if self.waiting_req.host == 'pappy':
            self.log("Processing request to internal webserver")
            yield handle_webserver_request(self.waiting_req)
            self.send_response(self.waiting_req.response.full_message)
            self._set_server_state(HTTPProtocolProxy.SERVER_STATE_HTTP_READY)
            self.process_request()
            return

        self.mangle_macros = []
        self.stream_responses = True

        if self.waiting_req.verb.upper() == 'CONNECT':
            self.send_response('HTTP/1.1 200 Connection established\r\n\r\n')
            self.start_client_maybe_tls(cert_host=self.waiting_req.host)
            self.connect_addr = (self.waiting_req.host, self.waiting_req.port, self.waiting_req.is_ssl)
            #defer.returnValue(None)
            self.log("Client TLS setup, ready for next request")
            self._set_server_state(HTTPProtocolProxy.SERVER_STATE_HTTP_READY)
            self.process_request()
            return

        ## Process/store the request
        sendreq = self.waiting_req

        upstream_http_addr = get_http_proxy_addr()
        if self.connect_addr is not None:
            sendreq.host = self.connect_addr[0]
            sendreq.port = self.connect_addr[1]
            sendreq.is_ssl = self.connect_addr[2]

        if context.in_scope(sendreq) or self.custom_macros:
            if not self.custom_macros:
                self.mangle_macros = self.client_protocol.factory.get_macro_list()
            sendreq.time_start = datetime.datetime.utcnow()

            if self.mangle_macros:
                self.stream_responses = False
            else:
                self.stream_responses = True

            if self.stream_responses and not self.mangle_macros:
                if self.save_requests:
                    sendreq.async_deep_save()
            else:
                if self.save_requests:
                    yield sendreq.async_deep_save()

                (mangreq, mangled) = yield macros.mangle_request(sendreq, self.mangle_macros)
                if mangreq is None:
                    self.log("Request dropped. Closing connections.")
                    sendreq.tags.add('dropped')
                    sendreq.response = None
                    self.dropped_request = True
                    self._set_server_state(HTTPProtocolProxy.SERVER_STATE_HTTP_READY)
                    self.send_response(self.BLANK_RESPONSE)
                    defer.returnValue(None)
                elif mangled:
                    sendreq = mangreq

                self.log("Request in scope, saving")
                sendreq.time_start = datetime.datetime.utcnow()
                assert sendreq.complete
                if self.save_requests:
                    yield sendreq.async_deep_save()
                self.waiting_req = sendreq
        else:
            self.log("Request out of scope, passing along unmangled")

        self.log("Making new connection to %s:%d is_ssl=%s" % (self.waiting_req.host, self.waiting_req.port, self.waiting_req.is_ssl))
        if upstream_http_addr is not None:
            self.log("Using upstream http proxy")
            self.log(str(self.waiting_req))
            self.set_connection(upstream_http_addr[0], upstream_http_addr[1], False, use_socks=True)
            self.using_upstream_http_proxy = True
        else:
            self.log("Not using upstream http proxy")
            self.set_connection(sendreq.host, sendreq.port, sendreq.is_ssl, use_socks=True)
            self.using_upstream_http_proxy = False

        if self.using_upstream_http_proxy and sendreq.is_ssl and not self.upstream_http_connected:
            self.was_streaming_responses = self.stream_responses
            self.stream_responses = False
            r = sendreq.connect_request
            apply_http_proxy_creds(r)
            self.send_server_data(r.full_message)
            self._set_server_state(HTTPProtocolProxy.SERVER_STATE_HTTP_AWAITING_PROXY_CONNECT)
            return
        elif self.using_upstream_http_proxy and not sendreq.is_ssl:
            # We're already connected to the proxy
            r = sendreq.copy()
            r.path_type = PATH_ABSOLUTE
            apply_http_proxy_creds(r)
            self.send_server_data(r.full_message)
            self._set_server_state(HTTPProtocolProxy.SERVER_STATE_HTTP_AWAITING_RESPONSE)
            return
        else:
            self.send_server_data(sendreq.full_message)
            self._set_server_state(HTTPProtocolProxy.SERVER_STATE_HTTP_AWAITING_RESPONSE)
            return
    
    def request_complete(self, req):
        self.log("Request complete, adding to queue")
        self.request_queue.put(req)
        self.process_request()

    @defer.inlineCallbacks
    def response_complete(self, rsp):
        from pappyproxy import context, macros, http

        if self.server_state == HTTPProtocolProxy.SERVER_STATE_HTTP_AWAITING_PROXY_CONNECT:
            self.log("Got upstream connection established response")
            self.stream_responses = self.was_streaming_responses

            if rsp.response_code == 407:
                print "Incorrect credentials for HTTP proxy. Please check your username and password."
                self.close_server_connection()
                return

            self.upstream_http_connected = True
            self.start_server_tls()
            self.log("Remote proxy TLS setup, ready for next request")
            self._set_server_state(HTTPProtocolProxy.SERVER_STATE_HTTP_READY)
            self.process_request(pop_request=False) # waiting_req is already the request we want to send
            return

        assert self.server_state == HTTPProtocolProxy.SERVER_STATE_HTTP_AWAITING_RESPONSE

        self.waiting_req.response = self.response
        sendreq = self.waiting_req
        sendreq.response = rsp
        self.waiting_req = None

        if context.in_scope(sendreq) or self.custom_macros:
            self.log("Response in scope, saving")
            sendreq.time_end = datetime.datetime.utcnow()

            assert sendreq.complete

            if self.stream_responses and not self.mangle_macros:
                if self.save_requests:
                    sendreq.async_deep_save()
            else:
                if self.save_requests:
                    yield sendreq.async_deep_save()

            if self.mangle_macros:
                if sendreq.response:
                    mangled = yield macros.mangle_response(sendreq, self.mangle_macros)
                    if mangled is None:
                        self._set_server_state(HTTPProtocolProxy.SERVER_STATE_HTTP_READY)
                        self.send_response(self.BLANK_RESPONSE)
                        defer.returnValue(None)
                    if mangled and self.save_requests:
                        yield sendreq.async_deep_save()
        else:
            self.log("Out of scope, not touching response")

        self.log("Checking if we need to write response to transport")

        if self.next_rsp_def is not None:
            self.next_rsp_def.callback(sendreq)

        if not self.stream_responses:
            self.log("Wasn't streaming, writing response")
            self.send_response(sendreq.response.full_message)
        else:
            self.log("Already streamed response, not writing to transport, ending response")
            self.end_response()

        if Response.is_ws_upgrade(rsp):
            self.log("Upgrading to websocket connection")

            self.server_state = HTTPProtocolProxy.SERVER_STATE_WEBSOCKET
            self.client_state = HTTPProtocolProxy.CLIENT_STATE_WEBSOCKET

            self.ws_proxy = WebSocketProxy(self.client_transport, self.server_transport, rsp, sendreq, self)
            self.ws_proxy.message_callback = self.ws_message_complete

            self.request.is_websocket = True
            self.log("Upgraded to websocket")
        else:
            self.log("Processing of response complete, ready for next request")
            self._set_server_state(HTTPProtocolProxy.SERVER_STATE_HTTP_READY)
            self.process_request()

    def ws_message_complete(self, wsobj):
        """
        Handles objects from both client and server. The object itself
        has a direction attribute that says which direction it went.
        """
        self.request.websocket_messages.append(wsobj)

    # Probably just going to wait for the connection to close
    # def ws_close(self):
    #     self.log("Websocket connection closed. Processing next request.")
    #     self._set_server_state(HTTPProtocolProxy.SERVER_STATE_HTTP_READY)
    #     self.process_request()

    def send_response(self, data):
        """
        Sends a response back to the client and processes the next request
        """
        self.send_client_data(data)
        self.end_response()

    def end_response(self):
        """
        Signals that all response data has been sent and the object is ready
        to process the next request
        """
        self.process_request()

    def submit_websocket_frame(self, data):
        raise PappyException("Websocket stream is not active")

    def abort_connection(self):
        pass

    def client_connection_made(self, protocol):
        self._set_client_state(HTTPProtocolProxy.CLIENT_STATE_HTTP_READY)
        ProtocolProxy.client_connection_made(self, protocol)

