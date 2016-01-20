import base64
import copy
import gzip
import json
import pytest
import StringIO
import zlib

from pappyproxy.pappy import http
from pappyproxy.util import PappyException

####################
# Helper Functions

class TException(Exception):
    pass

def by_lines_and_full_helper(Type, id_attr, load_func, header_lines, data=''):
    # Creates a request/response and returns versions created/recreated in
    # different ways. All of them should be equivalent.
    # Returned:
    # (created with constructor,
    #  created with add_line and add_data
    #  after calling update() on it,
    #  created by serializing and unserializing to json)
    
    t_lines = Type()
    for l in header_lines:
        t_lines.add_line(l)

    if data:
        t_lines.add_data(data)

    t_fulls = '\r\n'.join(header_lines)+'\r\n'
    t_fulls += data
    t_full = Type(t_fulls)
    t_updated = Type(t_fulls)

    t_json = Type(t_fulls)
    t_json.from_json(t_json.to_json())

    return (t_full, t_lines, t_updated, t_json)

def req_by_lines_and_full(header_lines, data=''):
    # Generates r_full, r_lines using the given header lines and data
    # r_lines is created with add_line/add_data and r_full is created with
    # the constructor
    return by_lines_and_full_helper(http.Request, 'reqid',
                                    http.Request.load_request,
                                    header_lines, data)
    
def rsp_by_lines_and_full(header_lines, data=''):
    # Generates r_full, r_lines using the given header lines and data
    # r_lines is created with add_line/add_data and r_full is created with
    # the constructor
    return by_lines_and_full_helper(http.Response, 'rspid',
                                    http.Response.load_response,
                                    header_lines, data)

def gzip_string(string):
    out = StringIO.StringIO()
    with gzip.GzipFile(fileobj=out, mode="w") as f:
        f.write(string)
    return out.getvalue()

def deflate_string(string):
    return zlib.compress(string)[2:-4]

def check_response_cookies(exp_pairs, rsp):
    pairs = rsp.cookies.all_pairs()
    pairs = [(c.key, c.val) for k, c in pairs]
    assert pairs == exp_pairs
    

####################
# Data storage

def test_chunked_simple():
    # Test a simple add_data
    c = http.ChunkedData()
    assert (not c.complete)

    full_data = '5\r\n'
    full_data += 'A'*5
    full_data += '\r\n'
    full_data += '0\r\n\r\n'
    c.add_data(full_data)
    assert c.complete
    assert c.body == 'A'*5

def test_chunked_hex():
    # Test hex lengths
    c = http.ChunkedData()
    full_data = 'af\r\n'
    full_data += 'A'*0xAF
    full_data += '\r\n'
    full_data += '0\r\n\r\n'
    c.add_data(full_data)
    assert c.complete
    assert c.body == 'A'*0xAF

    c = http.ChunkedData()
    full_data = 'AF\r\n'
    full_data += 'A'*0xAF
    full_data += '\r\n'
    full_data += '0\r\n\r\n'
    c.add_data(full_data)
    assert c.complete
    assert c.body == 'A'*0xAF

    c = http.ChunkedData()
    full_data = 'aF\r\n'
    full_data += 'A'*0xAF
    full_data += '\r\n'
    full_data += '0\r\n\r\n'
    c.add_data(full_data)
    assert c.complete
    assert c.body == 'A'*0xAF

def test_chunked_leading_zeros():
    # Test leading zeros
    c = http.ChunkedData()
    full_data = '000000000000000aF\r\n'
    full_data += 'A'*0xAF
    full_data += '\r\n'
    full_data += '0\r\n\r\n'
    c.add_data(full_data)
    assert c.complete
    assert c.body == 'A'*0xAF

def test_chunked_one_char_add():
    # Test adding one character at a time
    c = http.ChunkedData()
    full_data = 'af\r\n'
    full_data += 'A'*0xAF
    full_data += '\r\n'
    full_data += '0\r\n\r\n'
    for ch in full_data:
        c.add_data(ch)
    assert c.complete
    assert c.body == 'A'*0xAF

def test_chunked_incomplete():
    # Tests that complete isn't true until the data is received
    full_data = 'af\r\n'
    full_data += 'A'*0xAF
    full_data += '\r\n'
    full_data += '0' # right now we're fine ending on 0 without \r\n
    for i in range(len(full_data)-1):
        c = http.ChunkedData()
        c.add_data(full_data[:i])
        assert not c.complete

    # Test incomplete one character at a time
    full_data = 'af\r\n'
    full_data += 'A'*0xAF
    full_data += '\r\n'
    full_data += '0' # right now we're fine ending on 0 without \r\n
    for i in range(len(full_data)-1):
        c = http.ChunkedData()
        for ii in range(i):
            c.add_data(full_data[ii])
        assert not c.complete

def test_length_data_simple():
    # Basic test
    l = http.LengthData(100)
    assert not l.complete
    l.add_data('A'*100)
    assert l.complete
    assert l.body == 'A'*100

    l = http.LengthData(0)
    assert l.complete
    assert l.body == ''

    # Test incomplete
    l = http.LengthData(100)
    l.add_data('A'*99)
    assert not l.complete

def test_length_one_character():
    # Test adding one character at a time
    l = http.LengthData(100)
    for i in range(100):
        l.add_data('A')
    assert l.complete
    assert l.body == 'A'*100

    # Test adding one character at a time (incomplete)
    l = http.LengthData(100)
    for i in range(99):
        l.add_data('A')
    assert not l.complete

def test_length_overflow():
    # Test only saving the given number of chars
    l = http.LengthData(100)
    l.add_data('A'*400)
    assert l.complete
    assert l.body == 'A'*100

    # Test throwing an exception when adding data after complete
    l = http.LengthData(100)
    l.add_data('A'*100)
    with pytest.raises(PappyException):
        l.add_data('A')

def test_repeatable_dict_simple():
    d = http.RepeatableDict()
    assert not 'foo' in d
    d['foo'] = 'bar'
    assert 'foo' in d
    d['baz'] = 'fuzz'
    d.append('foo', 'fizz')
    assert d['foo'] == 'fizz'
    assert d['baz'] == 'fuzz'
    assert d.all_vals('foo') == ['bar', 'fizz']
    assert d.all_pairs() == [('foo', 'bar'),
                             ('baz', 'fuzz'),
                             ('foo', 'fizz')]
    assert not 'fee' in d
    d.add_pairs([('fee', 'fi'),
                 ('foo', 'fo')])
    assert 'fee' in d
    assert d['fee'] == 'fi'
    assert d['baz'] == 'fuzz'
    assert d['foo'] == 'fo'
    assert d.all_vals('foo') == ['bar', 'fizz', 'fo']
    assert d.all_pairs() == [('foo', 'bar'),
                             ('baz', 'fuzz'),
                             ('foo', 'fizz'),
                             ('fee', 'fi'),
                             ('foo', 'fo')]

def test_repeatable_dict_constructor():
    d = http.RepeatableDict([('foo','bar'),('baz','fuzz')])
    assert 'foo' in d
    assert d['foo'] == 'bar'
    assert d['baz'] == 'fuzz'
    assert d.all_vals('foo') == ['bar']
    assert d.all_pairs() == [('foo', 'bar'),
                             ('baz', 'fuzz')]
    
def test_repeatable_dict_case_insensitive():
    def test(d):
        assert 'foo' in d
        assert 'fOo' in d
        assert d['foo'] == 'fuzz'
        assert d['Foo'] == 'fuzz'
        assert d['FoO'] == 'fuzz'

        assert d.all_vals('foo') == ['bar', 'fuzz']
        assert d.all_vals('Foo') == ['bar', 'fuzz']
        assert d.all_vals('FoO') == ['bar', 'fuzz']

        assert d.all_pairs() == [('foo', 'bar'),
                                 ('fOo', 'fuzz')]

    d = http.RepeatableDict([('foo','bar'),('fOo','fuzz')], case_insensitive=True)
    test(d)

    d = http.RepeatableDict(case_insensitive=True)
    d['foo'] = 'bar'
    d.append('fOo', 'fuzz')
    test(d)

    d = http.RepeatableDict(case_insensitive=True)
    d.add_pairs([('foo','bar'),('fOo','fuzz')])
    test(d)

def test_repeatable_dict_overwrite():
    d = http.RepeatableDict([('foo','bar'),('foo','fuzz'),('bar','baz')])
    d['foo'] = 'asdf'
    assert d.all_vals('foo') == ['asdf']

def test_repeatable_dict_deletion():
    d = http.RepeatableDict([('foo','bar'),('fOo','fuzz'),('bar','baz')],
                             case_insensitive=True)
    assert 'foo' in d
    del d['foo']
    assert not 'foo' in d

    with pytest.raises(KeyError):
        x = d['foo']

    with pytest.raises(KeyError):
        x = d['fOo']

    assert d['bar'] == 'baz'
    assert d.all_vals('foo') == []

def test_repeatable_dict_callback():
    def f():
        raise TException()
        
    r = http.RepeatableDict()
    r['a'] = 'b'
    r.add_pairs([('c', 'd')])
    r.update('a', 'c')

    r.set_modify_callback(f)
    with pytest.raises(TException):
        r['a'] = 'b'
    with pytest.raises(TException):
        r.add_pairs([('c', 'd')])
    with pytest.raises(TException):
        r.update('a', 'c')
    

####################
## Cookies

def test_response_cookie_simple():
    s = 'ck=1234;'
    c = http.ResponseCookie(s)
    assert c.key == 'ck'
    assert c.val == '1234'
    assert not c.secure
    assert not c.http_only
    assert c.domain is None
    assert c.expires is None
    assert c.max_age is None
    assert c.path is None
    
def test_response_cookie_params():
    s = 'ck=1234; Expires=Wed, 09 Jun 2021 10:18:14 GMT; secure; httponly; path=/; max-age=12; domain=.foo.bar'
    c = http.ResponseCookie(s)
    assert c.key == 'ck'
    assert c.val == '1234'
    assert c.domain == '.foo.bar'
    assert c.expires == 'Wed, 09 Jun 2021 10:18:14 GMT'
    assert c.http_only
    assert c.max_age == 12
    assert c.path == '/'
    assert c.secure
    
def test_response_cookie_parsing():
    s = 'ck=1234=567;Expires=Wed, 09 Jun 2021 10:18:14 GMT;secure;httponly;path=/;max-age=12;domain=.foo.bar'
    c = http.ResponseCookie(s)
    assert c.key == 'ck'
    assert c.val == '1234=567'
    assert c.domain == '.foo.bar'
    assert c.expires == 'Wed, 09 Jun 2021 10:18:14 GMT'
    assert c.http_only
    assert c.max_age == 12
    assert c.path == '/'
    assert c.secure
    
def test_response_cookie_blank():
    # Don't ask why this exists, I've run into it
    s = ' ; path=/; secure'
    c = http.ResponseCookie(s)
    assert c.key == ''
    assert c.val == ''
    assert c.path == '/'
    assert c.secure

    s = '; path=/; secure'
    c = http.ResponseCookie(s)
    assert c.key == ''
    assert c.val == ''
    assert c.path == '/'
    assert c.secure

    s = 'asdf; path=/; secure'
    c = http.ResponseCookie(s)
    assert c.key == 'asdf'
    assert c.val == ''
    assert c.path == '/'
    assert c.secure
    
####################
## HTTPMessage tests

def test_message_simple():
    raw = ('foobar\r\n'
           'a: b\r\n'
           'Content-Length: 100\r\n\r\n')
    raw += 'A'*100
    m = http.HTTPMessage(raw)
    assert m.complete
    assert m.malformed == False
    assert m.start_line == 'foobar'
    assert m.body == 'A'*100
    assert m.headers.all_pairs() == [('a', 'b'), ('Content-Length', '100')]
    assert m.headers['A'] == 'b'
    assert m.headers_section == ('foobar\r\n'
                                 'a: b\r\n'
                                 'Content-Length: 100\r\n\r\n')
    assert m.full_message == raw
    
def test_message_build():
    raw = ('foobar\r\n'
           'a: b\r\n'
           'Content-Length: 100\r\n\r\n')
    raw += 'A'*100
    m = http.HTTPMessage()
    m.add_line('foobar')
    m.add_line('a: b')
    m.add_line('Content-Length: 100')
    m.add_line('')
    assert not m.complete
    m.add_data('A'*50)
    assert not m.complete
    m.add_data('A'*50)
    assert m.complete
    assert m.malformed == False
    assert m.start_line == 'foobar'
    assert m.body == 'A'*100
    assert m.headers.all_pairs() == [('a', 'b'), ('Content-Length', '100')]
    assert m.headers['A'] == 'b'
    assert m.headers_section == ('foobar\r\n'
                                 'a: b\r\n'
                                 'Content-Length: 100\r\n\r\n')
    assert m.full_message == raw
    
def test_message_build_chunked():
    raw = ('foobar\r\n'
           'a: b\r\n'
           'Content-Length: 100\r\n\r\n')
    raw += 'A'*100
    m = http.HTTPMessage()
    m.add_line('foobar')
    m.add_line('a: b')
    m.add_line('Transfer-Encoding: chunked')
    m.add_line('')
    assert not m.complete
    m.add_data('%x\r\n' % 50)
    m.add_data('A'*50)
    m.add_data('\r\n')
    m.add_data('%x\r\n' % 50)
    m.add_data('A'*50)
    m.add_data('\r\n')
    m.add_data('0\r\n')
    assert m.complete
    assert m.malformed == False
    assert m.start_line == 'foobar'
    assert m.body == 'A'*100
    assert m.headers.all_pairs() == [('a', 'b'), ('Content-Length', '100')]
    assert m.headers['A'] == 'b'
    assert m.headers_section == ('foobar\r\n'
                                 'a: b\r\n'
                                 'Content-Length: 100\r\n\r\n')
    assert m.full_message == raw

####################
## Request tests

def test_request_simple():
    header_lines = [
        'GET / HTTP/1.1',
        'Content-Type: text/xml; charset="utf-8"',
        'Accept-Encoding: gzip,deflate',
        'User-Agent: TestAgent',
        'Host: www.test.com',
        'Content-Length: 100',
        'Connection: Keep-Alive',
        'Cache-Control: no-cache',
        '',
    ]
    headers = '\r\n'.join(header_lines)+'\r\n'
    data = 'A'*100
    rf, rl, ru, rj = req_by_lines_and_full(header_lines, data)
    def test(r):
        assert r.complete
        assert r.fragment == None
        assert r.full_request == headers+data
        assert r.headers_complete
        assert r.host == 'www.test.com'
        assert r.is_ssl == False
        assert r.path == '/'
        assert r.port == 80
        assert r.start_line == 'GET / HTTP/1.1'
        assert r.verb == 'GET'
        assert r.version == 'HTTP/1.1'
        assert r.headers['Content-Length'] == '100'
        assert r.headers['CoNtent-lENGTH'] == '100'
        assert r.headers['Content-Type'] == 'text/xml; charset="utf-8"'
        assert r.headers['Accept-Encoding'] == 'gzip,deflate'
        assert r.headers['User-Agent'] == 'TestAgent'
        assert r.headers['Host'] == 'www.test.com'
        assert r.headers['Connection'] == 'Keep-Alive'
        assert r.headers['Cache-Control'] == 'no-cache'
        assert r.body == 'A'*100
    test(rf)
    test(rl)
    test(ru)
    test(rj)

def test_request_urlparams():
    header_lines = [
        'GET /?p1=foo&p2=bar#frag HTTP/1.1',
        'Content-Length: 0',
        '',
    ]
    rf, rl, ru, rj = req_by_lines_and_full(header_lines)
    def test(r):
        assert r.complete
        assert r.fragment == 'frag'
        assert r.url_params['p1'] == 'foo'
        assert r.url_params['p2'] == 'bar'
        assert r.full_request == ('GET /?p1=foo&p2=bar#frag HTTP/1.1\r\n'
                                  'Content-Length: 0\r\n'
                                  '\r\n')
    test(rf)
    test(rl)
    test(ru)
    test(rj)

def test_request_questionmark_url():
    header_lines = [
        'GET /path/??/to/?p1=foo&p2=bar#frag HTTP/1.1',
        'Content-Length: 0',
        '',
    ]
    rf, rl, ru, rj = req_by_lines_and_full(header_lines)
    def test(r):
        assert r.complete
        assert r.fragment == 'frag'
        assert r.url_params['?/to/?p1'] == 'foo'
        assert r.url_params['p2'] == 'bar'
        assert r.full_request == ('GET /path/??/to/?p1=foo&p2=bar#frag HTTP/1.1\r\n'
                                  'Content-Length: 0\r\n'
                                  '\r\n')
    test(rf)
    test(rl)
    test(ru)
    test(rj)

def test_request_postparams():
    header_lines = [
        'GET / HTTP/1.1',
        'Content-Length: 9',
        'Content-Type: application/x-www-form-urlencoded',
        '',
    ]
    data = 'a=b&c=dee'
    rf, rl, ru, rj = req_by_lines_and_full(header_lines, data)
    def test(r):
        assert r.complete
        assert r.post_params['a'] == 'b'
        assert r.post_params['c'] == 'dee'
    test(rf)
    test(rl)
    test(ru)
    test(rj)
    
def test_post_params_update():
    r = http.Request(('GET / HTTP/1.1\r\n'
                      'Content-Type: application/x-www-form-urlencoded\r\n'
                      'Content-Length: 7\r\n\r\n'
                      'a=b&c=d'))
    r.post_params['c'] = 'e'
    assert r.full_request == ('GET / HTTP/1.1\r\n'
                              'Content-Type: application/x-www-form-urlencoded\r\n'
                              'Content-Length: 7\r\n\r\n'
                              'a=b&c=e')
    r.post_params['a'] = 'f'
    assert r.full_request == ('GET / HTTP/1.1\r\n'
                              'Content-Type: application/x-www-form-urlencoded\r\n'
                              'Content-Length: 7\r\n\r\n'
                              'a=f&c=e')
    
def test_headers_end():
    header_lines = [
        'GET / HTTP/1.1',
        'Content-Type: text/xml; charset="utf-8"',
        'Accept-Encoding: gzip,deflate',
        'User-Agent: TestAgent',
        'Host: www.test.com',
        'Content-Length: 100',
        'Connection: Keep-Alive',
        'Cache-Control: no-cache',
        '',
    ]
    r = http.Request()
    for l in header_lines:
        r.add_line(l)
    assert not r.complete
    assert r.headers_complete
    
def test_request_cookies():
    header_lines = [
        'GET /?p1=foo&p2=bar#frag HTTP/1.1',
        'Content-Length: 0',
        'Cookie: abc=WRONG; def=456; ghi=789; abc=123',
        '',
    ]
    rf, rl, ru, rj = req_by_lines_and_full(header_lines)
    def test(r):
        assert r.complete
        assert r.cookies['abc'] == '123'
        assert r.cookies['def'] == '456'
        assert r.cookies['ghi'] == '789'
        assert r.cookies.all_vals('abc') == ['WRONG', '123']
    test(rf)
    test(rl)
    test(ru)
    test(rj)

def test_request_parse_host():
    header_lines = [
        'GET / HTTP/1.1',
        'Content-Length: 0',
        'Host: www.test.com:443',
        '',
    ]
    rf, rl, ru, rj = req_by_lines_and_full(header_lines)
    def test(r):
        assert r.complete
        assert r.port == 443
        assert r.host == 'www.test.com'
        assert r.is_ssl
    test(rf)
    test(rl)
    test(ru)
    test(rj)

def test_request_newline_delim():
    r = http.Request(('GET / HTTP/1.1\n'
                      'Content-Length: 4\n'
                      'Test-Header: foo\r\n'
                      'Other-header: bar\n\r\n'
                      'AAAA'))
    assert r.full_request == ('GET / HTTP/1.1\r\n'
                              'Content-Length: 4\r\n'
                              'Test-Header: foo\r\n'
                              'Other-header: bar\r\n\r\n'
                              'AAAA')
    
def test_repeated_request_headers():
    header_lines = [
        'GET /?p1=foo&p2=bar#frag HTTP/1.1',
        'Content-Length: 0',
        'Test-Header: WRONG',
        'Test-Header: RIGHTiguess',
        '',
    ]
    rf, rl, ru, rj = req_by_lines_and_full(header_lines)
    def test(r):
        assert r.complete
        assert r.headers['test-header'] == 'RIGHTiguess'
    test(rf)
    test(rl)
    test(ru)
    test(rj)

def test_request_update_statusline():
    r = http.Request()
    r.start_line = 'GET / HTTP/1.1'
    assert r.verb == 'GET'
    assert r.path == '/'
    assert r.version == 'HTTP/1.1'
    assert not r.complete

    assert r.full_request == 'GET / HTTP/1.1\r\n\r\n'

def test_request_update_cookies():
    r = http.Request()
    r.start_line = 'GET / HTTP/1.1'

    # Check new cookies
    r.cookies['foo'] = 'bar'
    r.cookies['baz'] = 'fuzz'
    assert r.full_request == ('GET / HTTP/1.1\r\n'
                              'Cookie: foo=bar; baz=fuzz\r\n'
                              '\r\n')

    # Check updated cookies (should be updated in place)
    r.cookies['foo'] = 'buzz'
    assert r.full_request == ('GET / HTTP/1.1\r\n'
                              'Cookie: foo=buzz; baz=fuzz\r\n'
                              '\r\n')

    # Check repeated cookies
    r.cookies.append('foo', 'bar')
    assert r.full_request == ('GET / HTTP/1.1\r\n'
                              'Cookie: foo=buzz; baz=fuzz; foo=bar\r\n'
                              '\r\n')

def test_request_update_headers(): 
    r = http.Request()
    r.start_line = 'GET / HTTP/1.1'
    r.headers['Content-Length'] = '0'
    r.headers['Test-Header'] = 'Test Value'
    r.headers['Other-Header'] = 'Other Value'
    r.headers['Host'] = 'www.test.com'
    r.headers.append('Test-Header', 'Test Value2')
    assert r.full_request == ('GET / HTTP/1.1\r\n'
                              'Content-Length: 0\r\n'
                              'Test-Header: Test Value\r\n'
                              'Other-Header: Other Value\r\n'
                              'Host: www.test.com\r\n'
                              'Test-Header: Test Value2\r\n'
                              '\r\n')
    assert r.host == 'www.test.com'

def test_request_modified_headers():
    r = http.Request()
    r.start_line = 'GET / HTTP/1.1'
    r.headers['content-length'] = '100'
    r.headers['cookie'] = 'abc=123'
    r.cookies['abc'] = '456'
    r.body = 'AAAA'
    assert r.full_request == ('GET / HTTP/1.1\r\n'
                              'content-length: 4\r\n'
                              'cookie: abc=456\r\n\r\n'
                              'AAAA')
    assert r.headers['content-length'] == '4'
    assert r.headers['cookie'] == 'abc=456'

def test_request_update_data():
    r = http.Request()
    r.start_line = 'GET / HTTP/1.1'
    r.headers['content-length'] = 500
    r.body = 'AAAA'
    assert r.full_request == ('GET / HTTP/1.1\r\n'
                              'content-length: 4\r\n'
                              '\r\n'
                              'AAAA')
def test_request_to_json():
    r = http.Request()
    r.start_line = 'GET / HTTP/1.1'
    r.headers['content-length'] = 500
    r.tags = ['foo', 'bar']
    r.body = 'AAAA'
    r.reqid = '1'

    rsp = http.Response()
    rsp.start_line = 'HTTP/1.1 200 OK'
    rsp.rspid = '2'

    r.response = rsp

    expected_reqdata = {u'full_message': unicode(base64.b64encode(r.full_request)),
                        u'response_id': str(rsp.rspid),
                        u'port': 80,
                        u'is_ssl': False,
                        u'tags': ['foo', 'bar'],
                        u'reqid': str(r.reqid),
                        u'host': '',
                       }

    assert json.loads(r.to_json()) == expected_reqdata

def test_request_update_content_length():
    r = http.Request(('GET / HTTP/1.1\r\n'
                      'Content-Length: 4\r\n\r\n'
                      'AAAAAAAAAA'), update_content_length=True)

    assert r.full_request == (('GET / HTTP/1.1\r\n'
                               'Content-Length: 10\r\n\r\n'
                               'AAAAAAAAAA'))
    
def test_request_blank_url_params():
    r = http.Request()
    r.add_line('GET /this/??-asdf/ HTTP/1.1')
    assert r.full_request == ('GET /this/??-asdf/ HTTP/1.1\r\n\r\n')

    r = http.Request()
    r.add_line('GET /this/??-asdf/?a=b&c&d=ef HTTP/1.1')
    assert r.full_request == ('GET /this/??-asdf/?a=b&c&d=ef HTTP/1.1\r\n\r\n')
    assert r.url_params['?-asdf/?a'] == 'b'
    assert r.url_params['c'] == None
    assert r.url_params['d'] == 'ef'

def test_request_blank():
    r = http.Request('\r\n\n\n')
    assert r.full_request == ''
    
def test_request_blank_headers():
    r = http.Request(('GET / HTTP/1.1\r\n'
                      'Header: \r\n'
                      'Header2:\r\n'))

    assert r.headers['header'] == ''
    assert r.headers['header2'] == ''
    
def test_request_blank_cookies():
    r = http.Request(('GET / HTTP/1.1\r\n'
                      'Cookie: \r\n'))
    assert r.cookies[''] == ''

    r = http.Request(('GET / HTTP/1.1\r\n'
                      'Cookie: a=b; ; c=d\r\n'))
    assert r.cookies[''] == ''

    r = http.Request(('GET / HTTP/1.1\r\n'
                      'Cookie: a=b; foo; c=d\r\n'))
    assert r.cookies['foo'] == ''

def test_request_set_url():
    r = http.Request('GET / HTTP/1.1\r\n')
    r.url = 'www.AAAA.BBBB'
    assert r.host == 'www.AAAA.BBBB'
    assert r.port == 80
    assert not r.is_ssl

    r.url = 'https://www.AAAA.BBBB'
    assert r.host == 'www.AAAA.BBBB'
    assert r.port == 443
    assert r.is_ssl

    r.url = 'https://www.AAAA.BBBB:1234'
    assert r.host == 'www.AAAA.BBBB'
    assert r.port == 1234
    assert r.is_ssl

    r.url = 'http://www.AAAA.BBBB:443'
    assert r.host == 'www.AAAA.BBBB'
    assert r.port == 443
    assert not r.is_ssl

    r.url = 'www.AAAA.BBBB:443'
    assert r.host == 'www.AAAA.BBBB'
    assert r.port == 443
    assert r.is_ssl
    
def test_request_set_url_params():
    r = http.Request('GET / HTTP/1.1\r\n')
    r.url = 'www.AAAA.BBBB?a=b&c=d#foo'
    assert r.url_params.all_pairs() == [('a','b'), ('c','d')]
    assert r.fragment == 'foo'
    assert r.url == 'http://www.AAAA.BBBB?a=b&c=d#foo'
    r.port = 400
    assert r.url == 'http://www.AAAA.BBBB:400?a=b&c=d#foo'
    r.is_ssl = True
    assert r.url == 'https://www.AAAA.BBBB:400?a=b&c=d#foo'
    
def test_request_copy():
    r = http.Request(('GET / HTTP/1.1\r\n'
                      'Content-Length: 4\r\n\r\n'
                      'AAAA'))
    r2 = copy.copy(r)
    assert r2.full_request == ('GET / HTTP/1.1\r\n'
                               'Content-Length: 4\r\n\r\n'
                               'AAAA')
    
def test_request_url_blankpath():
    r = http.Request()
    r.start_line = 'GET / HTTP/1.1'
    r.url = 'https://www.google.com'
    r.headers['Host'] = r.host
    r.url_params.from_dict({'foo': 'bar'})
    assert r.full_path == '/?foo=bar'
    assert r.url == 'https://www.google.com?foo=bar'
    

####################
## Response tests

def test_response_simple():
    header_lines = [
        'HTTP/1.1 200 OK',
        'Date: Thu, 22 Oct 2015 00:37:17 GMT',
        'Cache-Control: private, max-age=0',
        'Content-Type: text/html; charset=UTF-8',
        'Server: gws',
        'Content-Length: 100',
        '',
        ]
    data = 'A'*100
    rf, rl, ru, rj = rsp_by_lines_and_full(header_lines, data)
    def test(r):
        assert r.complete
        assert r.body == data
        assert r.response_code == 200
        assert r.response_text == 'OK'
        assert r.start_line == 'HTTP/1.1 200 OK'
        assert r.version == 'HTTP/1.1'

        assert r.headers['Date'] == 'Thu, 22 Oct 2015 00:37:17 GMT'
        assert r.headers['Cache-Control'] == 'private, max-age=0'
        assert r.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert r.headers['Server'] == 'gws'
        assert r.headers['Content-Length'] == '100'
        assert r.headers['CoNTEnT-leNGTH'] == '100'

    test(rf)
    test(rl)
    test(ru)
    test(rj)

def test_response_chunked():
    header_lines = [
        'HTTP/1.1 200 OK',
        'Date: Thu, 22 Oct 2015 00:37:17 GMT',
        'Cache-Control: private, max-age=0',
        'Content-Type: text/html; charset=UTF-8',
        'Server: gws',
        'Transfer-Encoding: chunked',
        '',
        ]
    data = 'af\r\n'
    data += 'A'*0xAF + '\r\n'
    data += 'BF\r\n'
    data += 'B'*0xBF + '\r\n'
    data += '0\r\n\r\n'

    rf, rl, ru, rj = rsp_by_lines_and_full(header_lines, data)
    def test(r):
        assert r.complete
        assert r.body == 'A'*0xAF + 'B'*0xBF

    test(rf)
    test(rl)
    test(ru)
    test(rj)

def test_response_gzip():
    data_decomp = 'Hello woru!'
    data_comp = gzip_string(data_decomp)
    
    header_lines = [
        'HTTP/1.1 200 OK',
        'Date: Thu, 22 Oct 2015 00:37:17 GMT',
        'Cache-Control: private, max-age=0',
        'Content-Type: text/html; charset=UTF-8',
        'Server: gws',
        'Content-Encoding: gzip',
        'Content-Length: %d' % len(data_comp),
        '',
        ]

    rf, rl, ru, rj = rsp_by_lines_and_full(header_lines, data_comp)
    def test(r):
        assert r.complete
        assert r.body == data_decomp

    test(rf)
    test(rl)
    test(ru)
    test(rj)

def test_response_deflate():
    data_decomp = 'Hello woru!'
    data_comp = deflate_string(data_decomp)
    
    header_lines = [
        'HTTP/1.1 200 OK',
        'Date: Thu, 22 Oct 2015 00:37:17 GMT',
        'Cache-Control: private, max-age=0',
        'Content-Type: text/html; charset=UTF-8',
        'Server: gws',
        'Content-Encoding: deflate',
        'Content-Length: %d' % len(data_comp),
        '',
        ]

    rf, rl, ru, rj = rsp_by_lines_and_full(header_lines, data_comp)
    def test(r):
        assert r.complete
        assert r.body == data_decomp

    test(rf)
    test(rl)
    test(ru)
    test(rj)

def test_response_chunked_gzip():
    data_decomp = 'Hello world!'
    data_comp = gzip_string(data_decomp)
    assert len(data_comp) > 3
    data_chunked = '3\r\n'
    data_chunked += data_comp[:3]
    data_chunked += '\r\n%x\r\n' % (len(data_comp[3:]))
    data_chunked += data_comp[3:]
    data_chunked += '\r\n0\r\n'
    
    header_lines = [
        'HTTP/1.1 200 OK',
        'Date: Thu, 22 Oct 2015 00:37:17 GMT',
        'Cache-Control: private, max-age=0',
        'Content-Type: text/html; charset=UTF-8',
        'Server: gws',
        'Content-Encoding: gzip',
        'Transfer-Encoding: chunked',
        '',
        ]

    rf, rl, ru, rj = rsp_by_lines_and_full(header_lines, data_chunked)
    def test(r):
        assert r.complete
        assert r.body == data_decomp
        assert r.headers['Content-Length'] == str(len(data_decomp))
        assert r.full_response == ('HTTP/1.1 200 OK\r\n'
                                   'Date: Thu, 22 Oct 2015 00:37:17 GMT\r\n'
                                   'Cache-Control: private, max-age=0\r\n'
                                   'Content-Type: text/html; charset=UTF-8\r\n'
                                   'Server: gws\r\n'
                                   'Content-Length: %d\r\n\r\n'
                                   '%s') % (len(data_decomp), data_decomp)

    test(rf)
    test(rl)
    test(ru)
    test(rj)

def test_response_early_completion():
    r = http.Response()
    r.start_line = 'HTTP/1.1 200 OK'
    r.add_line('Content-Length: 0')
    assert not r.complete
    r.add_line('')
    assert r.complete

def test_response_cookies():
    header_lines = [
        'HTTP/1.1 200 OK',
        'Content-Length: 0',
        'Set-Cookie: ck=1234=567;Expires=Wed, 09 Jun 2021 10:18:14 GMT;secure;httponly;path=/;max-age=12;domain=.foo.bar',
        'Set-Cookie: abc=123',
        'Set-Cookie: def=456',
        '',
        ]

    rf, rl, ru, rj = rsp_by_lines_and_full(header_lines)
    def test(r):
        assert r.complete
        assert r.cookies['ck'].key == 'ck'
        assert r.cookies['ck'].val == '1234=567'
        assert r.cookies['ck'].domain == '.foo.bar'
        assert r.cookies['ck'].expires == 'Wed, 09 Jun 2021 10:18:14 GMT'
        assert r.cookies['ck'].http_only
        assert r.cookies['ck'].max_age == 12
        assert r.cookies['ck'].path == '/'
        assert r.cookies['ck'].secure

        assert r.cookies['abc'].val == '123'
        assert r.cookies['def'].val == '456'

    test(rf)
    test(rl)
    test(ru)
    test(rj)

def test_response_repeated_cookies():
    r = http.Response(('HTTP/1.1 200 OK\r\n'
                       'Set-Cookie: foo=bar\r\n'
                       'Set-Cookie: baz=buzz\r\n'
                       'Set-Cookie: foo=buzz\r\n'
                       '\r\n'))
    expected_pairs = [('foo', 'bar'), ('baz', 'buzz'), ('foo', 'buzz')]
    check_response_cookies(expected_pairs, r)

def test_repeated_response_headers():
    # Repeated headers can be used for attacks, so ironically we have to handle
    # them well. We always use the last header as the correct one.
    header_lines = [
        'HTTP/1.1 200 OK',
        'Content-Length: 0',
        'Test-Head: WRONG',
        'Test-Head: RIGHTish',
        '',
        ]

    rf, rl, ru, rj = rsp_by_lines_and_full(header_lines)
    def test(r):
        assert r.complete
        assert r.headers['test-head'] == 'RIGHTish'

    test(rf)
    test(rl)
    test(ru)
    test(rj)

def test_response_update_statusline():
    r = http.Response()
    r.start_line = 'HTTP/1.1 200 OK'
    assert r.version == 'HTTP/1.1'
    assert r.response_code == 200
    assert r.response_text == 'OK'
    assert not r.complete

    assert r.full_response == 'HTTP/1.1 200 OK\r\n\r\n'

def test_response_update_headers():
    r = http.Response()
    r.start_line = 'HTTP/1.1 200 OK'
    r.headers['Test-Header'] = 'Test Value'
    r.headers['Other-Header'] = 'Other Value'

    assert r.full_response == ('HTTP/1.1 200 OK\r\n'
                               'Test-Header: Test Value\r\n'
                               'Other-Header: Other Value\r\n\r\n')

    r.headers.append('Test-Header', 'Other Test Value')
    assert r.full_response == ('HTTP/1.1 200 OK\r\n'
                               'Test-Header: Test Value\r\n'
                               'Other-Header: Other Value\r\n'
                               'Test-Header: Other Test Value\r\n\r\n')

def test_response_update_modified_headers():
    r = http.Response()
    r.start_line = 'HTTP/1.1 200 OK'
    r.headers['content-length'] = '500'
    r.body = 'AAAA'
    assert r.full_response == ('HTTP/1.1 200 OK\r\n'
                               'content-length: 4\r\n\r\n'
                               'AAAA')
    assert r.headers['content-length'] == '4'

def test_response_update_cookies():
    r = http.Response()
    r.start_line = 'HTTP/1.1 200 OK'
    # Test by adding headers
    r.headers['Set-Cookie'] = 'abc=123'
    assert r.full_response == ('HTTP/1.1 200 OK\r\n'
                               'Set-Cookie: abc=123\r\n\r\n')
    assert r.cookies['abc'].val == '123'
    r.headers.append('Set-Cookie', 'abc=456')
    assert r.full_response == ('HTTP/1.1 200 OK\r\n'
                               'Set-Cookie: abc=123\r\n'
                               'Set-Cookie: abc=456\r\n\r\n'
                              )
    assert r.cookies['abc'].val == '456'

    r = http.Response()
    r.start_line = 'HTTP/1.1 200 OK'
    # Test by adding cookie objects
    c = http.ResponseCookie('abc=123; secure')
    r.cookies['abc'] = c
    assert r.full_response == ('HTTP/1.1 200 OK\r\n'
                               'Set-Cookie: abc=123; secure\r\n\r\n')

def test_response_update_content_length():
    r = http.Response(('HTTP/1.1 200 OK\r\n'
                       'Content-Length: 4\r\n\r\n'
                       'AAAAAAAAAA'), update_content_length=True)

    assert r.full_response == (('HTTP/1.1 200 OK\r\n'
                               'Content-Length: 10\r\n\r\n'
                               'AAAAAAAAAA'))

def test_response_to_json():
    rsp = http.Response()
    rsp.start_line = 'HTTP/1.1 200 OK'
    rsp.rspid = 2

    expected_reqdata = {'full_message': base64.b64encode(rsp.full_response),
                        'rspid': rsp.rspid,
                        #'tag': r.tag,
                       }

    assert json.loads(rsp.to_json()) == expected_reqdata

def test_response_update_from_objects_cookies():
    r = http.Response(('HTTP/1.1 200 OK\r\n'
                       'Set-Cookie: foo=bar\r\n'
                       'Set-Cookie: baz=buzz\r\n'
                       'Header: out of fucking nowhere\r\n'
                       'Set-Cookie: foo=buzz\r\n'
                       '\r\n'))
    expected_pairs = [('foo', 'bar'), ('baz', 'buzz'), ('foo', 'buzz')]
    check_response_cookies(expected_pairs, r)

    new_pairs = [('foo', http.ResponseCookie('foo=banana')),
                 ('baz', http.ResponseCookie('baz=buzz')),
                 ('scooby', http.ResponseCookie('scooby=doo')),
                 ('foo', http.ResponseCookie('foo=boo'))]
    r.cookies.clear()
    r.cookies.add_pairs(new_pairs)

    assert r.full_response == ('HTTP/1.1 200 OK\r\n'
                               'Header: out of fucking nowhere\r\n'
                               'Set-Cookie: foo=banana\r\n'
                               'Set-Cookie: baz=buzz\r\n'
                               'Set-Cookie: scooby=doo\r\n'
                               'Set-Cookie: foo=boo\r\n'
                               '\r\n')
    expected_pairs = [('foo', 'banana'), ('baz', 'buzz'), ('scooby', 'doo'), ('foo', 'boo')]
    check_response_cookies(expected_pairs, r)

def test_response_update_from_objects_cookies_replace():
    r = http.Response(('HTTP/1.1 200 OK\r\n'
                       'Set-Cookie: foo=bar\r\n'
                       'Set-Cookie: baz=buzz\r\n'
                       'Header: out of fucking nowhere\r\n'
                       'Set-Cookie: foo=buzz\r\n'
                       '\r\n'))
    expected_pairs = [('foo', 'bar'), ('baz', 'buzz'), ('foo', 'buzz')]
    check_response_cookies(expected_pairs, r)


    r.cookies['foo'] = http.ResponseCookie('foo=banana')

    assert r.full_response == ('HTTP/1.1 200 OK\r\n'
                               'Set-Cookie: foo=banana\r\n'
                               'Set-Cookie: baz=buzz\r\n'
                               'Header: out of fucking nowhere\r\n'
                               '\r\n')

def test_response_blank():
    r = http.Response('\r\n\n\n')
    assert r.full_response == ''

def test_response_blank_headers():
    r = http.Response(('HTTP/1.1 200 OK\r\n'
                      'Header: \r\n'
                      'Header2:\r\n'))

    assert r.headers['header'] == ''
    assert r.headers['header2'] == ''

def test_response_newlines():
    r = http.Response(('HTTP/1.1 200 OK\n'
                       'Content-Length: 4\n\r\n'
                       'AAAA'))
    assert r.full_response == ('HTTP/1.1 200 OK\r\n'
                               'Content-Length: 4\r\n\r\n'
                               'AAAA')

def test_copy_response():
    r = http.Response(('HTTP/1.1 200 OK\r\n'
                       'Content-Length: 4\r\n\r\n'
                       'AAAA'))
    assert r.full_response == ('HTTP/1.1 200 OK\r\n'
                               'Content-Length: 4\r\n\r\n'
                               'AAAA')

    r2 = copy.copy(r)
    assert r.full_response == ('HTTP/1.1 200 OK\r\n'
                               'Content-Length: 4\r\n\r\n'
                               'AAAA')

def test_response_add_cookie():
    r = http.Response(('HTTP/1.1 200 OK\r\n'
                       'Content-Length: 0\r\n'
                       'Set-Cookie: foo=bar\r\n\r\n'))
    r.add_cookie(http.ResponseCookie('foo=baz'))
    assert r.full_response == ('HTTP/1.1 200 OK\r\n'
                               'Content-Length: 0\r\n'
                               'Set-Cookie: foo=bar\r\n'
                               'Set-Cookie: foo=baz\r\n\r\n')

def test_response_set_cookie():
    r = http.Response(('HTTP/1.1 200 OK\r\n'
                       'Content-Length: 0\r\n'))
    r.set_cookie(http.ResponseCookie('foo=bar'))
    assert r.full_response == ('HTTP/1.1 200 OK\r\n'
                               'Content-Length: 0\r\n'
                               'Set-Cookie: foo=bar\r\n\r\n')

    r.set_cookie(http.ResponseCookie('foo=baz'))
    assert r.full_response == ('HTTP/1.1 200 OK\r\n'
                               'Content-Length: 0\r\n'
                               'Set-Cookie: foo=baz\r\n\r\n')

def test_response_delete_cookie():
    r = http.Response(('HTTP/1.1 200 OK\r\n'
                       'Content-Length: 0\r\n'
                       'Set-Cookie: foo=bar\r\n\r\n'))
    r.delete_cookie('foo')
    assert r.full_response == ('HTTP/1.1 200 OK\r\n'
                               'Content-Length: 0\r\n\r\n')

    r = http.Response(('HTTP/1.1 200 OK\r\n'
                       'Content-Length: 0\r\n'
                       'Set-Cookie: foo=bar\r\n'
                       'Set-Cookie: foo=baz\r\n\r\n'))
    r.delete_cookie('foo')
    assert r.full_response == ('HTTP/1.1 200 OK\r\n'
                               'Content-Length: 0\r\n\r\n')
