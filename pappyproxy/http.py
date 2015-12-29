import base64
import collections
import crochet
import datetime
import gzip
import json
import pappyproxy
import re
import StringIO
import urlparse
import zlib
from twisted.internet import defer, reactor
from pappyproxy.util import PappyException
import bs4

ENCODE_NONE = 0
ENCODE_DEFLATE = 1
ENCODE_GZIP = 2

dbpool = None

def init(pool):
    """
    Initialize the http module.

    :param pool: The ConnectionPool to use to store the request/response objects
    :type pool: SQLite ConnectionPool
    """
    global dbpool
    if dbpool is None:
        dbpool = pool
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
    return instr

###################
## Functions to use

def get_request(url='', url_params={}):
    """
    get_request(url='', url_params={})

    Create a request object that makes a GET request to the given url with the
    given url params.
    """
    r = Request()
    r.status_line = 'GET / HTTP/1.1'
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
    r.status_line = 'POST / HTTP/1.1'
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
        self._keys.remove(key)
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
        return self._pairs[:]

    def append(self, key, val, do_callback=True):
        # Add a duplicate entry for key
        self._add_key(key)
        self._pairs.append((key, val))
        if do_callback:
            self._mod_callback()

    def set_val(self, key, val, do_callback=True):
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
        self._pairs = []
        if do_callback:
            self._mod_callback()
            
    def all_vals(self, key):
        return [p[1] for p in self._pairs if self._ef_key(p[0]) == self._ef_key(key)]

    def add_pairs(self, pairs, do_callback=True):
        for pair in pairs:
            self._add_key(pair[0])
        self._pairs += pairs
        if do_callback:
            self._mod_callback()

    def from_dict(self, d):
        self._pairs = list(d.items())
        self._mod_callback()

    def sort(self):
        # Sorts pairs by key alphabetaclly
        pairs = sorted(pairs, key=lambda x: x[0])

    def set_modify_callback(self, callback):
        # Add a function to be called whenever an element is added, changed, or
        # deleted. Set to None to remove
        self._modify_callback = callback
        

class LengthData:
    def __init__(self, length=None):
        self.raw_data = ''
        self.complete = False
        self.length = length or 0

        if self.length == 0:
            self.complete = True

    def add_data(self, data):
        if self.complete:
            raise PappyException("Data already complete!")
        remaining_length = self.length-len(self.raw_data)
        if len(data) >= remaining_length:
            self.raw_data += data[:remaining_length]
            assert(len(self.raw_data) == self.length)
            self.complete = True
        else:
            self.raw_data += data

class ChunkedData:

    def __init__(self):
        self.raw_data = ''
        self._pos = 0
        self._state = 0 # 0=reading length, 1=reading data, 2=going over known string
        self._len_str = ''
        self._chunk_remaining = 0
        self._known_str = ''
        self._known_str_pos = 0
        self._next_state = 0
        self._raw_data = ''
        self.complete = False
        self.unchunked_data = ''

    def add_data(self, data):
        self._raw_data += data
        self.scan_forward()

    def scan_forward(self):
        # Don't add more data if we're already done
        if self.complete:
            return

        while self._pos < len(self._raw_data):
            curchar = self._raw_data[self._pos]
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
                        # I should probably just rename raw_data since it's what
                        # you use to look at unchunked data, but you're not
                        # supposed to look at it until after it's complete
                        # anyways
                        self._raw_data = self.unchunked_data
                        self.raw_data = self._raw_data # Expose raw_data
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
                    self.unchunked_data += curchar
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


class Request(object):
    """
    :ivar time_end: The datetime that the request ended.
    :vartype time_end: datetime.datetime
    :ivar time_start: The datetime that the request was made
    :vartype time_start: datetime.datetime
    :ivar complete: When creating the request with :func:`~pappyproxy.http.Request.add_line`
        and :func:`~pappyproxy.http.Request.add_data`, returns whether
        the request is complete.
    :vartype complete: Bool
    :ivar cookies: Cookies sent with the request
    :vartype cookies: RepeatableDict
    :ivar fragment: The fragment part of the url (The part that comes after the #)
    :vartype fragment: String
    :ivar url_params: The url parameters of the request (aka the get parameters)
    :vartype url_params: RepeatableDict
    :ivar headers: The headers of the request
    :vartype headers: RepeatableDict
    :ivar headers_complete: When creating the request with
        :func:`~pappyproxy.http.Request.add_line` and
        :func:`~pappyproxy.http.Request.add_data`, returns whether the headers
        are complete
    :vartype headers_complete: Bool
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
    """


    def __init__(self, full_request=None, update_content_length=True,
                 port=None, is_ssl=None):
        self.time_end = None
        self.time_start = None
        self.complete = False
        self.cookies = RepeatableDict()
        self.fragment = None
        self.url_params = RepeatableDict()
        self.headers = RepeatableDict(case_insensitive=True)
        self.headers_complete = False
        self._host = None
        self._is_ssl = False
        self.path = ''
        self.port = None
        self.post_params = RepeatableDict()
        self._raw_data = ''
        self.reqid = None
        self.response = None
        self.submitted = False
        self.unmangled = None
        self.verb = ''
        self.version = ''
        self.tags = []

        self._first_line = True
        self._data_length = 0
        self._partial_data = ''

        self._set_dict_callbacks()

        # Set values from init
        if is_ssl:
            self.is_ssl = True
        if port:
            self.port = port

        # Get values from the raw request
        if full_request is not None:
            self._from_full_request(full_request, update_content_length)
            
    def __copy__(self):
        if not self.complete:
            raise PappyException("Cannot copy incomplete requests")
        newreq = Request(self.full_request)
        newreq.is_ssl = self.is_ssl
        newreq.port = self.port
        newreq._host = self._host
        newreq.time_start = self.time_start
        newreq.time_end = self.time_end
        if self.unmangled:
            newreq.unmangled = self.unmangled.copy()
        if self.response:
            newreq.response = self.response.copy()
        return newreq

    def __eq__(self, other):
        if self.full_request != other.full_request:
            return False
        if self.port != other.port:
            return False
        if self.is_ssl != other.is_ssl:
            return False
        if self._host != other._host:
            return False
        return True
    
    def copy(self):
        """
        Returns a copy of the request

        :rtype: Request
        """
        return self.__copy__()

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
    def status_line(self):
        """
        The status line of the request. ie `GET / HTTP/1.1`

        :getter: Returns the status line of the request
        :setter: Sets the status line of the request
        :type: string
        """
        if not self.verb and not self.path and not self.version:
            return ''
        return '%s %s %s' % (self.verb, self.full_path, self.version)

    @status_line.setter
    def status_line(self, val):
        self._handle_statusline(val)

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
        The raw text of the headers including the extra newline at the end.

        :getter: Returns the raw text of the headers including the extra newline at the end.
        :type: string
        """
        ret = self.status_line + '\r\n'
        for k, v in self.headers.all_pairs():
            ret = ret + "%s: %s\r\n" % (k, v)
        ret = ret + '\r\n'
        return ret

    @property
    def full_request(self):
        """
        The full text of the request including the headers and data.

        :getter: Returns the full text of the request
        :type: string
        """
        if not self.status_line:
            return ''
        ret = self.raw_headers
        ret = ret + self.raw_data
        return ret

    @property
    def raw_data(self):
        """
        The data portion of the request

        :getter: Returns the data portion of the request
        :setter: Set the data of the request and update metadata
        :type: string
        """
        return self._raw_data

    @raw_data.setter
    def raw_data(self, val):
        self._raw_data = val
        self._update_from_data()
        self.complete = True

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
        if self.is_ssl:
            retstr = 'https://'
        else:
            retstr = 'http://'
        retstr += self.host
        if not ((self.is_ssl and self.port == 443) or \
                (not self.is_ssl and self.port == 80)):
            retstr += ':%d' % self.port
        if self.path and self.path != '/':
            retstr += self.path
        if self.url_params:
            retstr += '?'
            pairs = []
            for p in self.url_params.all_pairs():
                pairs.append('='.join(p))
            retstr += '&'.join(pairs)
        if self.fragment:
            retstr += '#%s' % self.fragment
        return retstr
        
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

    def _from_full_request(self, full_request, update_content_length=False):
        # Get rid of leading CRLF. Not in spec, should remove eventually
        # technically doesn't treat \r\n same as \n, but whatever.
        full_request = _strip_leading_newlines(full_request)
        if full_request == '':
            return

        remaining = full_request
        while remaining and not self.headers_complete:
            line, remaining = _consume_line(remaining)
            self.add_line(line)

        if not self.headers_complete:
            self.add_line('')

        if not self.complete:
            if update_content_length:
                self.raw_data = remaining
            else:
                self.add_data(remaining)
        assert(self.complete)
        self._handle_data_end()

    ############################
    ## Internal update functions

    def _set_dict_callbacks(self):
        # Add callbacks to dicts
        self.headers.set_modify_callback(self._update_from_text)
        self.cookies.set_modify_callback(self._update_from_objects)
        self.post_params.set_modify_callback(self._update_from_objects)
        
    def _update_from_data(self):
        # Updates metadata that's based off of data
        self.headers.update('Content-Length', str(len(self.raw_data)), do_callback=False)
        if 'content-type' in self.headers:
            if self.headers['content-type'] == 'application/x-www-form-urlencoded':
                self.post_params = repeatable_parse_qs(self.raw_data)
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
        if self.post_params:
            pairs = []
            for k, v in self.post_params.all_pairs():
                pairs.append('%s=%s' % (k, v))
            self.raw_data = '&'.join(pairs)

    def _update_from_text(self):
        # Updates metadata that depends on header/status line values
        self.cookies = RepeatableDict()
        self._set_dict_callbacks()
        for k, v in self.headers.all_pairs():
            self._handle_header(k, v)

    ###############
    ## Data loading
            
    def add_line(self, line):
        """
        Used for building a request from a Twisted protocol.
        Add a line (for status line and headers). Lines must be added in order
        and the first line must be the status line. The line should not contain
        the trailing carriage return/newline. I do not suggest you use this for
        anything.

        :param line: The line to add
        :type line: string
        """

        if self._first_line and line == '':
            # Ignore leading newlines because fuck the spec
            return

        if self._first_line:
            self._handle_statusline(line)
            self._first_line = False
        else:
            # Either header or newline (end of headers)
            if line == '':
                self.headers_complete = True
                if self._data_length == 0:
                    self.complete = True
            else:
                key, val = line.split(':', 1)
                val = val.strip()
                if self._handle_header(key, val):
                    self.headers.append(key, val, do_callback=False)

    def add_data(self, data):
        """
        Used for building a request from a Twisted protocol.
        Add data to the request.
        I do not suggest that you use this function ever.

        :param data: The data to add
        :type data: string
        """
        # Add data (headers must be complete)
        len_remaining = self._data_length - len(self._partial_data)
        if len(data) >= len_remaining:
            self._partial_data += data[:len_remaining]
            self._raw_data = self._partial_data
            self.complete = True
            self._handle_data_end()
        else:
            self._partial_data += data

    ###############
    ## Data parsing
            
    def _process_host(self, hostline):
        # Get address and port
        # Returns true if port was explicitly stated
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
        
    def _handle_statusline(self, status_line):
        parts = status_line.split()
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
                
    def _handle_header(self, key, val):
        # We may have duplicate headers
        stripped = False

        if key.lower() == 'content-length':
            self._data_length = int(val)
        elif key.lower() == 'cookie':
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
        elif key.lower() == 'connection':
            #stripped = True
            pass

        return (not stripped)
    
    def _handle_data_end(self):
        if 'content-type' in self.headers:
            if self.headers['content-type'] == 'application/x-www-form-urlencoded':
                self.post_params = repeatable_parse_qs(self.raw_data)
                self._set_dict_callbacks()
                
    ##############
    ## Serializing

    def to_json(self):
        """
        Return a JSON encoding of the request that can be used by
        :func:`~pappyproxy.http.Request.from_json` to recreate the request.
        The `full_request` portion is base64 encoded because json doesn't play
        nice with binary blobs.
        """
        # We base64 encode the full response because json doesn't paly nice with
        # binary blobs
        data = {
            'full_request': base64.b64encode(self.full_request),
            'reqid': self.reqid,
        }
        if self.response:
            data['response_id'] = self.response.rspid
        else:
            data['response_id'] = None

        if self.unmangled:
            data['unmangled_id'] = self.unmangled.reqid

        if self.time_start:
            data['start'] = self.time_start.isoformat()
        if self.time_end:
            data['end'] = self.time_end.isoformat()
        data['tags'] = self.tags
        data['port'] = self.port
        data['is_ssl'] = self.is_ssl

        return json.dumps(data)

    def from_json(self, json_string):
        """
        Update the metadata of the request to match data from
        :func:`~pappyproxy.http.Request.to_json`

        :param json_string: The JSON data to use
        :type json_string: JSON data in a string
        """

        data = json.loads(json_string)
        self._from_full_request(base64.b64decode(data['full_request']))
        self.port = data['port']
        self._is_ssl = data['is_ssl']
        if 'tags' in data:
            self.tags = data['tags']
        else:
            self.tags = []
        self._update_from_text()
        self._update_from_data()
        if data['reqid']:
            self.reqid = data['reqid']
            
    #######################
    ## Data store functions
                
    @defer.inlineCallbacks
    def async_save(self):
        """
        async_save()
        Save/update the request in the data file. Returns a twisted deferred which
        fires when the save is complete.

        :rtype: twisted.internet.defer.Deferred
        """

        assert(dbpool)
        try:
            # Check for intyness
            _ = int(self.reqid)

            # If we have reqid, we're updating
            yield dbpool.runInteraction(self._update)
            assert(self.reqid is not None)
            yield dbpool.runInteraction(self._update_tags)
            pappyproxy.context.add_request(self)
        except (ValueError, TypeError):
            # Either no id or in-memory
            yield dbpool.runInteraction(self._insert)
            assert(self.reqid is not None)
            yield dbpool.runInteraction(self._update_tags)
            pappyproxy.context.add_request(self)

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
        Saves self, unmangled, response, and unmangled response. Returns a deferred
        which fires after everything has been saved.

        :rtype: twisted.internet.defer.Deferred
        """

        if self.response:
            if self.response.unmangled:
                yield self.response.unmangled.async_save()
            yield self.response.async_save()
        if self.unmangled:
            yield self.unmangled.async_save()
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
            queryargs.append(self.time_start.isoformat())
        if self.time_end:
            setnames.append('end_datetime=?')
            queryargs.append(self.time_end.isoformat())

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
        if self.response:
            colnames.append('response_id')
            assert(self.response.rspid is not None) # should be saved first
            colvals.append(self.response.rspid)
        if self.unmangled:
            colnames.append('unmangled_id')
            assert(self.unmangled.reqid is not None) # should be saved first
            colvals.append(self.unmangled.reqid)
        if self.time_start:
            colnames.append('start_datetime')
            colvals.append(self.time_start.isoformat())
        if self.time_end:
            colnames.append('end_datetime')
            colvals.append(self.time_end.isoformat())
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
    def delete(self):
        assert(self.reqid is not None)
        yield dbpool.runQuery(
            """
            DELETE FROM requests WHERE id=?;
            """,
            (self.reqid,)
            )
        yield dbpool.runQuery(
            """
            DELETE FROM tagged WHERE reqid=?;
            """,
            (self.reqid,)
        )
        self.reqid = None

    @defer.inlineCallbacks
    def deep_delete(self):
        if self.unmangled:
            yield self.unmangled.delete()
        if self.response:
            if self.response.unmangled:
                yield self.response.unmangled.delete()
            yield self.response.delete()
        yield self.delete()

    @staticmethod
    def _gen_sql_row(tablename=None):
        template = "{pre}full_request, {pre}response_id, {pre}id, {pre}unmangled_id, {pre}start_datetime, {pre}end_datetime, {pre}port, {pre}is_ssl"
        if tablename:
            return template.format(pre=('%s.'%tablename))
        else:
            return template.format(pre='')
        
        
    @staticmethod
    @defer.inlineCallbacks
    def _from_sql_row(row):
        req = Request(row[0])
        if row[1]:
            rsp = yield Response.load_response(str(row[1]))
            req.response = rsp
        if row[3]:
            unmangled_req = yield Request.load_request(str(row[3]))
            req.unmangled = unmangled_req
        if row[4]:
            req.time_start = datetime.datetime.strptime(row[4], "%Y-%m-%dT%H:%M:%S.%f")
        if row[5]:
            req.time_end = datetime.datetime.strptime(row[5], "%Y-%m-%dT%H:%M:%S.%f")
        if row[6] is not None:
            req.port = int(row[6])
        if row[7] == 1:
            req._is_ssl = True
        req.reqid = str(row[2])

        # tags
        rows = yield dbpool.runQuery(
            """
            SELECT tg.tag
            FROM tagged tgd, tags tg
            WHERE tgd.tagid=tg.id AND tgd.reqid=?;
            """,
            (req.reqid,)
        )
        req.tags = []
        for row in rows:
            req.tags.append(row[0])
        defer.returnValue(req)

    @staticmethod
    @defer.inlineCallbacks
    def load_all_requests():
        """
        load_all_requests()
        Load all the requests in the data file and return them in a list.
        Returns a deferred which calls back with the list of requests when complete.

        :rtype: twisted.internet.defer.Deferred
        """
        
        reqs = []
        reqs += list(pappyproxy.context.in_memory_requests)
        rows = yield dbpool.runQuery(
            """
            SELECT %s
            FROM requests;
            """ % Request._gen_sql_row(),
            )
        for row in rows:
            req = yield Request._from_sql_row(row)
            reqs.append(req)
        defer.returnValue(reqs)

    @staticmethod
    @defer.inlineCallbacks
    def load_requests_by_tag(tag):
        """
        load_requests_by_tag(tag)
        Load all the requests in the data file with a given tag and return them in a list.
        Returns a deferred which calls back with the list of requests when complete.

        :rtype: twisted.internet.defer.Deferred
        """
        # tags
        rows = yield dbpool.runQuery(
            """
            SELECT tgd.reqid
            FROM tagged tgd, tags tg
            WHERE tgd.tagid=tg.id AND tg.tag=?;
            """,
            (tag,)
        )
        reqs = []
        for row in rows:
            req = Request.load_request(row[0])
            reqs.append(req)
        defer.returnValue(reqs)
        
    @staticmethod
    @defer.inlineCallbacks
    def load_request(to_load, allow_special=True):
        """
        load_request(to_load)
        Load a request with the given request id and return it.
        Returns a deferred which calls back with the request when complete.

        :rtype: twisted.internet.defer.Deferred
        """

        assert(dbpool)

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
                return r.unmangled
            if rsp_unmangled:
                if not r.response:
                    raise PappyException("Request %s does not have a response" % r.reqid)
                if not r.response.unmangled:
                    raise PappyException("Response to request %s was not mangled" % r.reqid)
                r.response = r.response.unmangled
                return r
            else:
                return r

        for r in pappyproxy.context.in_memory_requests:
            if r.reqid == to_load:
                defer.returnValue(retreq(r))
        for r in pappyproxy.context.all_reqs:
            if r.reqid == to_load:
                defer.returnValue(retreq(r))
        for r in pappyproxy.context.active_requests:
            if r.reqid == to_load:
                defer.returnValue(retreq(r))
        if to_load[0] == 'm':
            # An in-memory request should have been loaded in the previous loop
            raise PappyException('In-memory request %s not found' % to_load)
        rows = yield dbpool.runQuery(
            """
            SELECT %s
            FROM requests
            WHERE id=?;
            """ % Request._gen_sql_row(),
            (loadid,)
            )
        if len(rows) != 1:
            raise PappyException("Request with id %s does not exist" % loadid)
        req = yield Request._from_sql_row(rows[0])
        req.reqid = to_load

        defer.returnValue(retreq(req))

    @staticmethod
    @defer.inlineCallbacks
    def load_from_filters(filters):
        # Not efficient in any way
        # But it stays this way until we hit performance issues
        assert(dbpool)
        rows = yield dbpool.runQuery(
            """
            SELECT %s FROM requests r1
                LEFT JOIN requests r2 ON r1.id=r2.unmangled_id
            WHERE r2.id is NULL;
            """ % Request._gen_sql_row('r1'),
            )
        reqs = []
        for row in rows:
            req = yield Request._from_sql_row(row)
            reqs.append(req)
        reqs += list(pappyproxy.context.in_memory_requests)
        (reqs, _) = pappyproxy.context.filter_reqs(reqs, filters)

        defer.returnValue(reqs)
    
    ######################
    ## Submitting Requests
        
    @staticmethod
    @defer.inlineCallbacks
    def submit_new(host, port, is_ssl, full_request):
        """
        submit_new(host, port, is_ssl, full_request)
        Submits a request with the given parameters and returns a request object
        with the response.

        :param host: The host to submit to
        :type host: string
        :param port: The port to submit to
        :type port: Integer
        :type is_ssl: Whether to use SSL
        :param full_request: The request data to send
        :type full_request: string
        :rtype: Twisted deferred that calls back with a Request
        """
        
        new_obj = Request(full_request)
        factory = pappyproxy.proxy.ProxyClientFactory(new_obj, save_all=False)
        factory.connection_id = pappyproxy.proxy.get_next_connection_id()
        if is_ssl:
            reactor.connectSSL(host, port, factory, pappyproxy.proxy.ClientTLSContext())
        else:
            reactor.connectTCP(host, port, factory)
        new_req = yield factory.data_defer
        defer.returnValue(new_req)

    @defer.inlineCallbacks
    def async_submit(self):
        """
        async_submit()
        Same as :func:`~pappyproxy.http.Request.submit` but generates deferreds.
        Submits the request using its host, port, etc. and updates its response value
        to the resulting response.

        :rtype: Twisted deferred
        """
        new_req = yield Request.submit_new(self.host, self.port, self.is_ssl,
                                           self.full_request)
        self.response = new_req.response
        self.time_start = new_req.time_start
        self.time_end = new_req.time_end

    @crochet.wait_for(timeout=180.0)
    @defer.inlineCallbacks
    def submit(self):
        """
        submit()
        Submits the request using its host, port, etc. and updates its response value
        to the resulting response.
        Cannot be called in async functions.
        This is what you should use to submit your requests in macros.
        """
        new_req = yield Request.submit_new(self.host, self.port, self.is_ssl,
                                           self.full_request)
        self.response = new_req.response
        self.time_start = new_req.time_start
        self.time_end = new_req.time_end


class Response(object):
    """
    :ivar complete: When creating the response with :func:`~pappyproxy.http.Response.add_line`
        and :func:`~pappyproxy.http.Response.add_data`, returns whether
        the request is complete.
    :vartype complete: Bool
    :ivar cookies: Cookies set by the response
    :vartype cookies: RepeatableDict of ResponseCookie objects
    :ivar headers: The headers of the response
    :vartype headers: RepeatableDict
    :ivar headers_complete: When creating the response with
        :func:`~pappyproxy.http.Response.add_line` and
        :func:`~pappyproxy.http.Response.add_data`, returns whether the headers
        are complete
    :vartype headers_complete: Bool
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

    def __init__(self, full_response=None, update_content_length=False):
        self.complete = False
        self.cookies = RepeatableDict()
        self.headers = RepeatableDict(case_insensitive=True)
        self.headers_complete = False
        self._raw_data = ''
        self.response_code = 0
        self.response_text = ''
        self.rspid = None
        self.unmangled = None
        self.version = ''
        
        self._encoding_type = ENCODE_NONE
        self._first_line = True
        self._data_obj = None
        self._end_after_headers = False

        self._set_dict_callbacks()

        if full_response is not None:
            self._from_full_response(full_response, update_content_length)

    def __copy__(self):
        if not self.complete:
            raise PappyException("Cannot copy incomplete responses")
        retrsp = Response(self.full_response)
        if self.unmangled:
            retrsp.unmangled = self.unmangled.copy()
        return retrsp

    def copy(self):
        return self.__copy__()

    def __eq__(self, other):
        if self.full_response != other.full_response:
            return False
        return True
            
    @property
    def raw_headers(self):
        """
        The raw text of the headers including the extra newline at the end.

        :getter: Returns the raw text of the headers including the extra newline at the end.
        :type: string
        """
        ret = self.status_line + '\r\n'
        for k, v in self.headers.all_pairs():
            ret = ret + "%s: %s\r\n" % (k, v)
        ret = ret + '\r\n'
        return ret

    @property
    def status_line(self):
        """
        The status line of the response. ie `HTTP/1.1 200 OK`

        :getter: Returns the status line of the response
        :setter: Sets the status line of the response
        :type: string
        """
        if not self.version and self.response_code == 0 and not self.version:
            return ''
        return '%s %d %s' % (self.version, self.response_code, self.response_text)

    @status_line.setter
    def status_line(self, val):
        self._handle_statusline(val)

    @property
    def raw_data(self):
        """
        The data portion of the response

        :getter: Returns the data portion of the response
        :setter: Set the data of the response and update metadata
        :type: string
        """
        return self._raw_data
        
    @raw_data.setter
    def raw_data(self, val):
        self._raw_data = val
        self._data_obj = LengthData(len(val))
        if len(val) > 0:
            self._data_obj.add_data(val)
        self._encoding_type = ENCODE_NONE
        self.complete = True
        self._update_from_data()

    @property
    def full_response(self):
        """
        The full text of the response including the headers and data.
        Response is automatically converted from compressed/chunked into an
        uncompressed response with a Content-Length header.

        :getter: Returns the full text of the response
        :type: string
        """
        if not self.status_line:
            return ''
        ret = self.raw_headers
        ret = ret + self.raw_data
        return ret

    @property
    def soup(self):
        """
        Returns a beautifulsoup4 object for parsing the html of the response

        :getter: Returns a BeautifulSoup object representing the html of the response
        """
        return bs4.BeautifulSoup(self.raw_data, 'lxml')
    
    def _from_full_response(self, full_response, update_content_length=False):
        # Get rid of leading CRLF. Not in spec, should remove eventually
        full_response = _strip_leading_newlines(full_response)
        if full_response == '':
            return

        remaining = full_response
        while remaining and not self.headers_complete:
            line, remaining = _consume_line(remaining)
            self.add_line(line)

        if not self.headers_complete:
            self.add_line('')

        if update_content_length:
            self.raw_data = remaining
        if not self.complete:
            self.add_data(remaining)
        assert(self.complete)

    ############################
    ## Internal update functions
    
    def _set_dict_callbacks(self):
        # Add callbacks to dicts
        self.headers.set_modify_callback(self._update_from_text)
        self.cookies.set_modify_callback(self._update_from_objects)

    def _update_from_data(self):
        self.headers.update('Content-Length', str(len(self.raw_data)), do_callback=False)

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
                
    def _update_from_text(self):
        self.cookies = RepeatableDict()
        self._set_dict_callbacks()
        for k, v in self.headers.all_pairs():
            if k.lower() == 'set-cookie':
                # Parse the cookie
                cookie = ResponseCookie(v)
                self.cookies.append(cookie.key, cookie, do_callback=False)

    ###############
    ## Data parsing
        
    def _handle_statusline(self, status_line):
        self._first_line = False
        self.version, self.response_code, self.response_text = \
                                            status_line.split(' ', 2)
        self.response_code = int(self.response_code)

        if self.response_code == 304 or self.response_code == 204 or \
            self.response_code/100 == 1:
            self._end_after_headers = True

    def _handle_header(self, key, val):
        stripped = False
        if key.lower() == 'content-encoding':
            if val in ('gzip', 'x-gzip'):
                self._encoding_type = ENCODE_GZIP
            elif val in ('deflate'):
                self._encoding_type = ENCODE_DEFLATE

            # We send our requests already decoded, so we don't want a header
            # saying it's encoded
            if self._encoding_type != ENCODE_NONE:
                stripped = True
        elif key.lower() == 'transfer-encoding' and val.lower() == 'chunked':
            self._data_obj = ChunkedData()
            self.complete = self._data_obj.complete
            stripped = True
        elif key.lower() == 'content-length':
            # We use our own content length
            self._data_obj = LengthData(int(val))
        elif key.lower() == 'set-cookie':
            cookie = ResponseCookie(val)
            self.cookies.append(cookie.key, cookie, do_callback=False)

        if stripped:
            return False
        else:
            self.headers.append(key, val, do_callback=False)
            return True

    ###############
    ## Data loading
                
    def add_line(self, line):
        """
        Used for building a response from a Twisted protocol.
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

            if self._end_after_headers:
                self.complete = True
                return

            if not self._data_obj:
                self._data_obj = LengthData(0)
            self.complete = self._data_obj.complete
            return

        if self._first_line:
            self._handle_statusline(line)
            self._first_line = False
        else:
            key, val = line.split(':', 1)
            val = val.strip()
            self._handle_header(key, val)

    def add_data(self, data):
        """
        Used for building a response from a Twisted protocol.
        Add data to the response. The data must conform to the content encoding
        and transfer encoding given in the headers passed in to
        :func:`~pappyproxy.http.Response.add_line`. Can be any fragment of the data.
        I do not suggest that you use this function ever.

        :param data: The data to add
        :type data: string
        """
        assert(self._data_obj)
        assert(not self._data_obj.complete)
        assert not self.complete
        self._data_obj.add_data(data)
        if self._data_obj.complete:
            self._raw_data = _decode_encoded(self._data_obj.raw_data,
                                             self._encoding_type)
            self.complete = True
            self._update_from_data()

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

    ##############
    ## Serializing

    def to_json(self):
        """
        Return a JSON encoding of the response that can be used by
        :func:`~pappyproxy.http.Response.from_json` to recreate the response.
        The ``full_response`` portion is base64 encoded because json doesn't play
        nice with binary blobs.
        """
        data = {
            'rspid': self.rspid,
            'full_response': base64.b64encode(self.full_response),
        }
        if self.unmangled:
            data['unmangled_id'] = self.unmangled.rspid

        return json.dumps(data)
            

    def from_json(self, json_string):
        """
        Update the metadata of the response to match data from
        :func:`~pappyproxy.http.Response.to_json`

        :param json_string: The JSON data to use
        :type json_string: JSON data in a string
        """
        data = json.loads(json_string)
        self._from_full_response(base64.b64decode(data['full_response']))
        self._update_from_text()
        self._update_from_data()
        if data['rspid']:
            self.rspid = str(data['rspid'])

    #######################
    ## Database interaction
        
    @defer.inlineCallbacks
    def async_save(self):
        """
        async_save()
        Save/update the just request in the data file. Returns a twisted deferred which
        fires when the save is complete. It is suggested that you use
        :func: `~pappyproxy.http.Request.async_deep_save` instead to save responses.

        :rtype: twisted.internet.defer.Deferred
        """
        assert(dbpool)
        try:
            # Check for intyness
            _ = int(self.rspid)

            # If we have rspid, we're updating
            yield dbpool.runInteraction(self._update)
        except (ValueError, TypeError):
            yield dbpool.runInteraction(self._insert)
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
        self.rspid = txn.lastrowid
        assert(self.rspid is not None)

    @defer.inlineCallbacks
    def delete(self):
        assert(self.rspid is not None)
        row = yield dbpool.runQuery(
            """
            DELETE FROM responses WHERE id=?;
            """,
            (self.rspid,)
            )
        self.rspid = None

    @staticmethod
    @defer.inlineCallbacks
    def load_response(respid):
        """
        Load a response from its response id. Returns a deferred. I don't suggest you use this.

        :rtype: twisted.internet.defer.Deferred
        """
        assert(dbpool)
        rows = yield dbpool.runQuery(
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
            unmangled_response = yield Response.load_response(int(rows[0][2]))
            resp.unmangled = unmangled_response
        defer.returnValue(resp)
            
