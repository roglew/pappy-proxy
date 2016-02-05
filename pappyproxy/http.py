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

from .util import PappyException, printable_data
from .requestcache import RequestCache
from .colors import Colors, host_color, path_formatter
from pygments.formatters import TerminalFormatter
from pygments.lexers import get_lexer_for_mimetype, HttpLexer
from twisted.internet import defer, reactor

import sys

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
    req = Request.load_request(str(reqid))
    defer.returnValue(req)

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

        if self.length == 0:
            self.complete = True

    def add_data(self, data):
        if self.complete:
            raise PappyException("Data already complete!")
        remaining_length = self.length-len(self.body)
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

    def __init__(self, full_message=None, update_content_length=False):
        # Initializes instance variables too
        self.clear()

        if full_message is not None:
            self._from_full_message(full_message, update_content_length)

    def __eq__(self, other):
        # TODO check meta
        if self.full_message != other.full_message:
            return False
        if self.get_metadata() != other.get_metadata():
            return False
        return True

    def __copy__(self):
        if not self.complete:
            raise PappyException("Cannot copy incomplete http messages")
        retmsg = self.__class__(self.full_message)
        retmsg.set_metadata(self.get_metadata())
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

    def _from_full_message(self, full_message, update_content_length=False, meta=None):
        # Set defaults for metadata
        self.clear()
        # Get rid of leading CRLF. Not in spec, should remove eventually
        full_message = _strip_leading_newlines(full_message)
        if full_message == '':
            return

        lines = full_message.splitlines(True)
        header_len = 0
        for line in lines:
            if line[-2] == '\r':
                l = line[:-2]
            else:
                l = line[:-1]
            self.add_line(l)
            header_len += len(line)
            if self.headers_complete:
                break
        remaining = full_message[header_len:]
            
        if not self.headers_complete:
            self.add_line('')

        if meta:
            self.set_metadata(meta)

        # We keep track of encoding here since if it's encoded, after
        # we call add_data it will update content-length automatically
        # and we won't have to update the content-length manually
        if not self.complete:
            # We do add data since just setting the body will keep the
            # object from decoding chunked/compressed messages
            self.add_data(remaining)
        if update_content_length and (not self._decoded):
            self.body = remaining
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
        to_ret = printable_data(self.headers_section)
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
        to_ret = printable_data(self.body)
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
        return (self.headers_section_pretty + '\r\n' + self.body_pretty)

    ###############
    ## Data loading

    def add_line(self, line):
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

            if self._end_after_headers:
                self.complete = True
                return

            if not self._data_obj:
                self._data_obj = LengthData(0)
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

    def add_data(self, data):
        """
        Used for building a message from a Twisted protocol.
        Add data to the message. The data must conform to the content encoding
        and transfer encoding given in the headers passed in to
        :func:`~pappyproxy.http.HTTPMessage.add_line`. Can be any fragment of the data.
        I do not suggest that you use this function ever.

        :param data: The data to add
        :type data: string
        """
        assert(self._data_obj)
        assert(not self._data_obj.complete)
        assert not self.complete
        self._data_obj.add_data(data)
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
        """
        self.start_line = start_line

    def headers_end(self):
        """
        Called when the headers are complete.
        """
        pass

    def body_complete(self):
        """
        Called when the body of the message is complete
        """
        self.body = _decode_encoded(self._data_obj.body,
                                    self._encoding_type)

    def update_from_body(self):
        """
        Called when the body of the message is modified directly. Should be used
        to update metadata that depends on the body of the message.
        """
        if len(self.body) > 0 or 'Content-Length' in self.headers:
            self.headers.update('Content-Length', str(len(self.body)), do_callback=False)

    def update_from_headers(self):
        """
        Called when a header is modified. Should be used to update metadata that
        depends on the values of headers.
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
        """
        pass

    def set_metadata(self, data):
        """
        Set metadata values based off of a data dictionary.
        Should be implemented in child class.
        Should not be invoked outside of implementation!

        :param data: Metadata to apply
        :type line: dict
        """
        pass

    def reset_metadata(self):
        """
        Reset meta values to default values. Overridden by child class.
        Should not be invoked outside of implementation!
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
    """

    cache = RequestCache(100)
    """
    The request cache that stores requests in memory for performance
    """

    def __init__(self, full_request=None, update_content_length=True,
                 port=None, is_ssl=None, host=None):
        # Resets instance variables
        self.clear()

        # Called after instance vars since some callbacks depend on
        # instance vars
        HTTPMessage.__init__(self, full_request, update_content_length)

        # After message init so that other instance vars are initialized
        self._set_dict_callbacks()

        # Set values from init
        if is_ssl:
            self.is_ssl = True
        if port:
            self.port = port
        if host:
            self._host = host
            
    def __copy__(self):
        if not self.complete:
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
        return '%s %s %s' % (self.verb, self.full_path, self.version)

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
        
    def _url_helper(self, colored=False):
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
                (not self.is_ssl and self.port == 80)):
            if colored:
                retstr += ':'
                retstr += Colors.MAGENTA
                retstr += str(self.port)
                retstr += Colors.ENDC
            else:
                retstr += ':%d' % self.port
        if self.path and self.path != '/':
            if colored:
                retstr += path_formatter(self.path)
            else:
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

    def get_metadata(self):
        data = {}
        if self.port is not None:
            data['port'] = self.port
        data['is_ssl'] = self.is_ssl
        data['host'] = self.host
        data['reqid'] = self.reqid
        if self.response:
            data['response_id'] = self.response.rspid
        data['tags'] = list(self.tags)
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
            if self.headers['content-type'] == 'application/x-www-form-urlencoded':
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
        elif key.lower() == 'connection':
            #stripped = True
            pass

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
            print 'adding'
            use_cache.add(self)
        else:
            print 'else adding'
    
    @defer.inlineCallbacks
    def async_save(self, cust_dbpool=None, cust_cache=None):
        """
        async_save()
        Save/update the request in the data file. Returns a twisted deferred which
        fires when the save is complete.

        :rtype: twisted.internet.defer.Deferred
        """
        from .context import Context
        from .pappy import main_context

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
        from .context import Context, reset_context_caches

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
            Request.cache.ordered_ids.remove(self.reqid)
            Request.cache.all_ids.remove(self.reqid)
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
    def _from_sql_row(row, cust_dbpool=None, cust_cache=None):
        from .http import Request

        global dbpool
        if cust_dbpool:
            use_dbpool = cust_dbpool
            use_cache = cust_cache
        else:
            use_dbpool = dbpool
            use_cache = Request.cache

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
        from .requestcache import RequestCache
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
            use_cache = cust_cache
        else:
            use_dbpool = dbpool
            use_cache = Request.cache

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
        from .context import Context

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
        from .proxy import ProxyClientFactory, get_next_connection_id, ClientTLSContext

        new_req = Request(full_request)
        new_req.is_ssl = is_ssl
        new_req.port = port
        factory = ProxyClientFactory(new_req, save_all=False)
        factory.connection_id = get_next_connection_id()
        if is_ssl:
            reactor.connectSSL(host, port, factory, ClientTLSContext())
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
        self.set_metadata(new_req.get_metadata())
        self.unmangled = new_req.unmangled
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
        yield self.async_submit()


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

    def get_metadata(self):
        data = {}
        data['rspid'] = self.rspid
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
        self.version, self.response_code, self.response_text = \
                                            start_line.split(' ', 2)
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
        global dbpool
        if cust_dbpool:
            use_dbpool = cust_dbpool
            use_cache = cust_cache
        else:
            use_dbpool = dbpool
            use_cache = Request.cache
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
            row = yield dbpool.runQuery(
                """
                DELETE FROM responses WHERE id=?;
                """,
                (self.rspid,)
                )
        self.rspid = None

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
            use_cache = cust_cache
        else:
            use_dbpool = dbpool
            use_cache = Request.cache

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
            
