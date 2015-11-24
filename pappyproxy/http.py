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

ENCODE_NONE = 0
ENCODE_DEFLATE = 1
ENCODE_GZIP = 2

dbpool = None

class DataAlreadyComplete(PappyException):
    pass

def init(pool):
    global dbpool
    if dbpool is None:
        dbpool = pool
    assert(dbpool)

def destruct():
    assert(dbpool)
    dbpool.close()

def decode_encoded(data, encoding):
    if encoding == ENCODE_NONE:
        return data

    if encoding == ENCODE_DEFLATE:
        dec_data = zlib.decompress(data, -15)
    else:
        dec_data = gzip.GzipFile('', 'rb', 9, StringIO.StringIO(data))
        dec_data = dec_data.read()
    return dec_data

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

def strip_leading_newlines(string):
    while (len(string) > 1 and string[0:2] == '\r\n') or \
            (len(string) > 0 and string[0] == '\n'):
        if len(string) > 1 and string[0:2] == '\r\n':
            string = string[2:]
        elif len(string) > 0 and string[0] == '\n':
            string = string[1:]
    return string

def consume_line(instr):
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
            raise DataAlreadyComplete()
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
            self.from_cookie(set_cookie_string)

    @property
    def cookie_av(self):
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

    def parse_cookie_av(self, cookie_av):
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
            
    def from_cookie(self, set_cookie_string):
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
                self.parse_cookie_av(cookie_av)
        else:
            self.key, self.val = set_cookie_string.split('=',1)


class Request(object):

    def __init__(self, full_request=None, update_content_length=False):
        self.time_end = None
        self.time_start = None
        self.complete = False
        self.cookies = RepeatableDict()
        self.fragment = None
        self.get_params = RepeatableDict()
        self.header_len = 0
        self.headers = RepeatableDict(case_insensitive=True)
        self.headers_complete = False
        self.host = None
        self.is_ssl = False
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

        self._first_line = True
        #self._connect_response = False
        #self._encoding_type = ENCODE_NONE
        self._data_length = 0
        self._partial_data = ''

        self.set_dict_callbacks()

        # Get values from the raw request
        if full_request is not None:
            self.from_full_request(full_request, update_content_length)

    @property
    def rsptime(self):
        if self.time_start and self.time_end:
            return self.time_end-self.time_start
        else:
            return None

    @property
    def status_line(self):
        if not self.verb and not self.path and not self.version:
            return ''
        return '%s %s %s' % (self.verb, self.full_path, self.version)

    @status_line.setter
    def status_line(self, val):
        self.handle_statusline(val)

    @property
    def full_path(self):
        path = self.path
        if self.get_params:
            path += '?'
            pairs = []
            for pair in self.get_params.all_pairs():
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
        ret = self.status_line + '\r\n'
        for k, v in self.headers.all_pairs():
            ret = ret + "%s: %s\r\n" % (k, v)
        ret = ret + '\r\n'
        return ret

    @property
    def full_request(self):
        if not self.status_line:
            return ''
        ret = self.raw_headers
        ret = ret + self.raw_data
        return ret

    @property
    def raw_data(self):
        return self._raw_data

    @raw_data.setter
    def raw_data(self, val):
        self._raw_data = val
        self.update_from_data()
        self.complete = True

    @property
    def url(self):
        if self.is_ssl:
            retstr = 'https://'
        else:
            retstr = 'http://'
        retstr += self.host
        if not ((self.is_ssl and self.port == 443) or \
                (not self.is_ssl and self.port == 80)):
            retstr += ':%d' % self.port
        if self.path:
            retstr += self.path
        if self.get_params:
            retstr += '?'
            pairs = []
            for p in self.get_params.all_pairs():
                pairs.append('='.join(p))
            retstr += '&'.join(pairs)
        if self.fragment:
            retstr += '#%s' % self.fragment
        return retstr
        
    @url.setter
    def url(self, val):
        self._handle_statusline_uri(val)

    def set_dict_callbacks(self):
        # Add callbacks to dicts
        self.headers.set_modify_callback(self.update_from_text)
        self.cookies.set_modify_callback(self.update_from_objects)
        self.post_params.set_modify_callback(self.update_from_data)

    def from_full_request(self, full_request, update_content_length=False):
        # Get rid of leading CRLF. Not in spec, should remove eventually
        # technically doesn't treat \r\n same as \n, but whatever.
        full_request = strip_leading_newlines(full_request)
        if full_request == '':
            return

        remaining = full_request
        while remaining and not self.headers_complete:
            line, remaining = consume_line(remaining)
            self.add_line(line)

        if not self.headers_complete:
            self.add_line('')

        if not self.complete:
            if update_content_length:
                self.raw_data = remaining
            else:
                self.add_data(remaining)
        assert(self.complete)

    def update_from_data(self):
        # Updates metadata that's based off of data
        self.headers.update('Content-Length', str(len(self.raw_data)), do_callback=False)
        if 'content-type' in self.headers:
            if self.headers['content-type'] == 'application/x-www-form-urlencoded':
                self.post_params = repeatable_parse_qs(self.raw_data)
                self.set_dict_callbacks()

    def update_from_objects(self):
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
            for k, v in self.post_params:
                pairs.append('%s=%s' % (k, v))
            self.raw_data = '&'.join(pairs)

    def update_from_text(self):
        # Updates metadata that depends on header/status line values
        self.cookies = RepeatableDict()
        self.set_dict_callbacks()
        for k, v in self.headers.all_pairs():
            self.handle_header(k, v)

    def add_data(self, data):
        # Add data (headers must be complete)
        len_remaining = self._data_length - len(self._partial_data)
        if len(data) >= len_remaining:
            self._partial_data += data[:len_remaining]
            self._raw_data = self._partial_data
            self.complete = True
            self.handle_data_end()
        else:
            self._partial_data += data

    def _process_host(self, hostline):
        # Get address and port
        # Returns true if port was explicitly stated
        port_given = False
        if ':' in hostline:
            self.host, self.port = hostline.split(':')
            self.port = int(self.port)
            if self.port == 443:
                self.is_ssl = True
            port_given = True
        else:
            self.host = hostline
            if not self.port:
                self.port = 80
        self.host.strip()
        return port_given
            
    def add_line(self, line):
        # Add a line (for status line and headers)
        # Modifies first line if it is in full url form

        if self._first_line and line == '':
            # Ignore leading newlines because fuck the spec
            return

        if self._first_line:
            self.handle_statusline(line)
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
                if self.handle_header(key, val):
                    self.headers.append(key, val, do_callback=False)
        self.header_len += len(line)+2

    def _handle_statusline_uri(self, uri):
        if not re.match('(?:^.+)://', uri):
            uri = '//' + uri

        parsed_path = urlparse.urlparse(uri)
        netloc = parsed_path.netloc
        port_given = False
        if netloc:
            port_given = self._process_host(netloc)

        if re.match('^https://', uri) or self.port == 443:
            self.is_ssl = True
            if not port_given:
                self.port = 443
        if re.match('^http://', uri):
            self.is_ssl = False

        if not self.port:
            if self.is_ssl:
                self.port = 443
            else:
                self.port = 80

        reqpath = parsed_path.path
        self.path = parsed_path.path
        if parsed_path.query:
            reqpath += '?'
            reqpath += parsed_path.query
            self.get_params = repeatable_parse_qs(parsed_path.query)
        if parsed_path.fragment:
            reqpath += '#'
            reqpath += parsed_path.fragment
            self.fragment = parsed_path.fragment
        
    def handle_statusline(self, status_line):
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
                
    def handle_header(self, key, val):
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
    
    def handle_data_end(self):
        if 'content-type' in self.headers:
            if self.headers['content-type'] == 'application/x-www-form-urlencoded':
                self.post_params = repeatable_parse_qs(self.raw_data)
                self.set_dict_callbacks()
            
    @defer.inlineCallbacks
    def save(self):
        assert(dbpool)
        if self.reqid:
            # If we have reqid, we're updating
            yield dbpool.runInteraction(self._update)
            assert(self.reqid is not None)
        else:
            yield dbpool.runInteraction(self._insert)
            assert(self.reqid is not None)

    @defer.inlineCallbacks
    def deep_save(self):
        "Saves self, unmangled, response, and unmangled response"
        if self.response:
            if self.response.unmangled:
                yield self.response.unmangled.save()
            yield self.response.save()
        if self.unmangled:
            yield self.unmangled.save()
        yield self.save()
            
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
        self.reqid = txn.lastrowid
        assert txn.lastrowid is not None
        assert self.reqid is not None

    def to_json(self):
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
        data['port'] = self.port
        data['is_ssl'] = self.is_ssl

        return json.dumps(data)

    def from_json(self, json_string):
        data = json.loads(json_string)
        self.from_full_request(base64.b64decode(data['full_request']))
        self.port = data['port']
        self.is_ssl = data['is_ssl']
        self.update_from_text()
        self.update_from_data()
        if data['reqid']:
            self.reqid = int(data['reqid'])
            
    def delete(self):
        assert(self.reqid is not None)
        row = yield dbpool.runQuery(
            """
            DELETE FROM requests WHERE id=?;
            """,
            (self.reqid,)
            )

    def duplicate(self):
        return Request(self.full_request)

    @staticmethod
    @defer.inlineCallbacks
    def submit(host, port, is_ssl, full_request):
        new_obj = Request(full_request)
        factory = pappyproxy.proxy.ProxyClientFactory(new_obj)
        factory.connection_id = pappyproxy.proxy.get_next_connection_id()
        if is_ssl:
            reactor.connectSSL(host, port, factory, pappyproxy.proxy.ClientTLSContext())
        else:
            reactor.connectTCP(host, port, factory)
        new_req = yield factory.data_defer
        defer.returnValue(new_req)

    def submit_self(self):
        new_req = Request.submit(self.host, self.port, self.is_ssl,
                                 self.full_request)
        return new_req

    @staticmethod
    @defer.inlineCallbacks
    def load_request(reqid):
        assert(dbpool)
        rows = yield dbpool.runQuery(
            """
            SELECT full_request, response_id, id, unmangled_id, start_datetime, end_datetime, port, is_ssl
            FROM requests
            WHERE id=?;
            """,
            (reqid,)
            )
        if len(rows) != 1:
            raise PappyException("Request with id %d does not exist" % reqid)
        full_request = rows[0][0]
        req = Request(full_request)
        if rows[0][1]:
            rsp = yield Response.load_response(int(rows[0][1]))
            req.response = rsp
        if rows[0][3]:
            unmangled_req = yield Request.load_request(int(rows[0][3]))
            req.unmangled = unmangled_req
        if rows[0][4]:
            req.time_start = datetime.datetime.strptime(rows[0][4], "%Y-%m-%dT%H:%M:%S.%f")
        if rows[0][5]:
            req.time_end = datetime.datetime.strptime(rows[0][5], "%Y-%m-%dT%H:%M:%S.%f")
        if rows[0][6] is not None:
            req.port = int(rows[0][6])
        if rows[0][7] == 1:
            req.is_ssl = True
        req.reqid = int(rows[0][2])
        defer.returnValue(req)

    @staticmethod
    @defer.inlineCallbacks
    def load_from_filters(filters):
        # Not efficient in any way
        # But it stays this way until we hit performance issues
        assert(dbpool)
        rows = yield dbpool.runQuery(
            """
            SELECT r1.id FROM requests r1
                LEFT JOIN requests r2 ON r1.id=r2.unmangled_id
            WHERE r2.id is NULL;
            """,
            )
        reqs = []
        for r in rows:
            newreq = yield Request.load_request(int(r[0]))
            reqs.append(newreq)

        reqs = pappyproxy.context.filter_reqs(reqs, filters)

        defer.returnValue(reqs)
            


class Response(object):

    def __init__(self, full_response=None, update_content_length=False):
        self.complete = False
        self.cookies = RepeatableDict()
        self.header_len = 0
        self.headers = RepeatableDict(case_insensitive=True)
        self.headers_complete = False
        self.host = None
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

        self.set_dict_callbacks()

        if full_response is not None:
            self.from_full_response(full_response, update_content_length)

    @property
    def raw_headers(self):
        ret = self.status_line + '\r\n'
        for k, v in self.headers.all_pairs():
            ret = ret + "%s: %s\r\n" % (k, v)
        ret = ret + '\r\n'
        return ret

    @property
    def status_line(self):
        if not self.version and self.response_code == 0 and not self.version:
            return ''
        return '%s %d %s' % (self.version, self.response_code, self.response_text)

    @status_line.setter
    def status_line(self, val):
        self.handle_statusline(val)

    @property
    def raw_data(self):
        return self._raw_data
        
    @raw_data.setter
    def raw_data(self, val):
        self._raw_data = val
        self._data_obj = LengthData(len(val))
        self._data_obj.add_data(val)
        self._encoding_type = ENCODE_NONE
        self.complete = True
        self.update_from_data()

    @property
    def full_response(self):
        if not self.status_line:
            return ''
        ret = self.raw_headers
        ret = ret + self.raw_data
        return ret

    def set_dict_callbacks(self):
        # Add callbacks to dicts
        self.headers.set_modify_callback(self.update_from_text)
        self.cookies.set_modify_callback(self.update_from_objects)

    def from_full_response(self, full_response, update_content_length=False):
        # Get rid of leading CRLF. Not in spec, should remove eventually
        full_response = strip_leading_newlines(full_response)
        if full_response == '':
            return

        remaining = full_response
        while remaining and not self.headers_complete:
            line, remaining = consume_line(remaining)
            self.add_line(line)

        if not self.headers_complete:
            self.add_line('')

        if not self.complete:
            if update_content_length:
                self.raw_data = remaining
            else:
                self.add_data(remaining)
        assert(self.complete)

    def add_line(self, line):
        assert(not self.headers_complete)
        self.header_len += len(line)+2
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
            self.handle_statusline(line)
            self._first_line = False
        else:
            key, val = line.split(':', 1)
            val = val.strip()
            self.handle_header(key, val)

    def handle_statusline(self, status_line):
        self._first_line = False
        self.version, self.response_code, self.response_text = \
                                            status_line.split(' ', 2)
        self.response_code = int(self.response_code)

        if self.response_code == 304 or self.response_code == 204 or \
            self.response_code/100 == 1:
            self._end_after_headers = True

    def handle_header(self, key, val):
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
        elif key.lower() == 'host':
            self.host = val

        if stripped:
            return False
        else:
            self.headers.append(key, val, do_callback=False)
            return True

    def update_from_data(self):
        self.headers.update('Content-Length', str(len(self.raw_data)), do_callback=False)

    def update_from_objects(self):
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
                        new_headers.append('Set-Cookie', c.cookie_av)
                    cookies_added = True
            else:
                new_headers.append(pair[0], pair[1])

        if not cookies_added:
            # Add all our cookies to the end
            for k, c in self.cookies.all_pairs():
                new_headers.append('Set-Cookie', c.cookie_av)

        self.headers = new_headers
        self.set_dict_callbacks()
                
    def update_from_text(self):
        self.cookies = RepeatableDict()
        self.set_dict_callbacks()
        for k, v in self.headers.all_pairs():
            if k.lower() == 'set-cookie':
                # Parse the cookie
                cookie = ResponseCookie(v)
                self.cookies.append(cookie.key, cookie, do_callback=False)

    def add_data(self, data):
        assert(self._data_obj)
        assert(not self._data_obj.complete)
        assert not self.complete
        self._data_obj.add_data(data)
        if self._data_obj.complete:
            self._raw_data = decode_encoded(self._data_obj.raw_data,
                                            self._encoding_type)
            self.complete = True
            self.update_from_data()

    def add_cookie(self, cookie):
        self.cookies.append(cookie.key, cookie, do_callback=False)

    def to_json(self):
        # We base64 encode the full response because json doesn't paly nice with
        # binary blobs
        data = {
            'rspid': self.rspid,
            'full_response': base64.b64encode(self.full_response),
        }
        if self.unmangled:
            data['unmangled_id'] = self.unmangled.rspid

        return json.dumps(data)
            
    def from_json(self, json_string):
        data = json.loads(json_string)
        self.from_full_response(base64.b64decode(data['full_response']))
        self.update_from_text()
        self.update_from_data()
        if data['rspid']:
            self.rspid = int(data['rspid'])
        
    @defer.inlineCallbacks
    def save(self):
        assert(dbpool)
        if self.rspid:
            # If we have rspid, we're updating
            yield dbpool.runInteraction(self._update)
        else:
            yield dbpool.runInteraction(self._insert)
        assert(self.rspid is not None)

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

    def delete(self):
        assert(self.rspid is not None)
        row = yield dbpool.runQuery(
            """
            DELETE FROM responses WHERE id=?;
            """,
            (self.rspid,)
            )

    @staticmethod
    @defer.inlineCallbacks
    def load_response(respid):
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
            raise PappyException("Response with request id %d does not exist" % respid)
        full_response = rows[0][0]
        resp = Response(full_response)
        resp.rspid = int(rows[0][1])
        if rows[0][2]:
            unmangled_response = yield Response.load_response(int(rows[0][2]))
            resp.unmangled = unmangled_response
        defer.returnValue(resp)
            
        
