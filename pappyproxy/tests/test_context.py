import pytest

from pappyproxy import context
from pappyproxy.http import Request, Response, ResponseCookie

@pytest.fixture
def http_request():
    return Request('GET / HTTP/1.1\r\n')

def test_filter_reqs():
    pass

def test_gen_filter_by_all_request():
    f = context.gen_filter_by_all(['ct', 'hello'])
    fn = context.gen_filter_by_all(['nct', 'hello'])

    # Nowhere
    r = Request('GET / HTTP/1.1\r\n')
    assert not f(r)
    assert fn(r)

    # Verb
    r = Request('hello / HTTP/1.1\r\n')
    assert f(r)
    assert not fn(r)

    # Path
    r = Request('GET /hello HTTP/1.1\r\n')
    assert f(r)
    assert not fn(r)

    # Data
    r = Request('GET / HTTP/1.1\r\n')
    r.body = 'hello'
    assert f(r)
    assert not fn(r)

    # Header key
    r = Request('GET / HTTP/1.1\r\n')
    r.headers['hello'] = 'goodbye'
    assert f(r)
    assert not fn(r)

    # Header value
    r = Request('GET / HTTP/1.1\r\n')
    r.headers['goodbye'] = 'hello'
    assert f(r)
    assert not fn(r)

    # Nowhere in headers
    r = Request('GET / HTTP/1.1\r\n')
    r.headers['goodbye'] = 'for real'
    assert not f(r)
    assert fn(r)

    # Cookie key
    r = Request('GET / HTTP/1.1\r\n')
    r.cookies['hello'] = 'world'
    assert f(r)
    assert not fn(r)

    # Cookie value
    r = Request('GET / HTTP/1.1\r\n')
    r.cookies['world'] = 'hello'
    assert f(r)
    assert not fn(r)

    # Nowhere in cookie
    r = Request('GET / HTTP/1.1\r\n')
    r.cookies['world'] = 'sucks'
    assert not f(r)
    assert fn(r)


def test_gen_filter_by_all_response(http_request):
    f = context.gen_filter_by_all(['ct', 'hello'])
    fn = context.gen_filter_by_all(['nct', 'hello'])

    # Nowhere
    r = Response('HTTP/1.1 200 OK\r\n')
    http_request.response = r
    assert not f(http_request)
    assert fn(http_request)

    # Response text
    r = Response('HTTP/1.1 200 hello\r\n')
    http_request.response = r
    assert f(http_request)
    assert not fn(http_request)

    # Data
    r = Response('HTTP/1.1 200 OK\r\n')
    http_request.response = r
    r.body = 'hello'
    assert f(http_request)
    assert not fn(http_request)

    # Header key
    r = Response('HTTP/1.1 200 OK\r\n')
    http_request.response = r
    r.headers['hello'] = 'goodbye'
    assert f(http_request)
    assert not fn(http_request)

    # Header value
    r = Response('HTTP/1.1 200 OK\r\n')
    http_request.response = r
    r.headers['goodbye'] = 'hello'
    assert f(http_request)
    assert not fn(http_request)

    # Nowhere in headers
    r = Response('HTTP/1.1 200 OK\r\n')
    http_request.response = r
    r.headers['goodbye'] = 'for real'
    assert not f(http_request)
    assert fn(http_request)

    # Cookie key
    r = Response('HTTP/1.1 200 OK\r\n')
    http_request.response = r
    r.add_cookie(ResponseCookie('hello=goodbye'))
    assert f(http_request)
    assert not fn(http_request)

    # Cookie value
    r = Response('HTTP/1.1 200 OK\r\n')
    http_request.response = r
    r.add_cookie(ResponseCookie('goodbye=hello'))
    assert f(http_request)
    assert not fn(http_request)

    # Nowhere in cookie
    r = Response('HTTP/1.1 200 OK\r\n')
    http_request.response = r
    r.add_cookie(ResponseCookie('goodbye=for real'))
    assert not f(http_request)
    assert fn(http_request)

def test_filter_by_host(http_request):
    f = context.gen_filter_by_host(['ct', 'sexy'])
    fn = context.gen_filter_by_host(['nct', 'sexy'])
    
    http_request.headers['Host'] = 'google.com'
    http_request.headers['MiscHeader'] = 'vim.sexy'
    assert not f(http_request)
    assert fn(http_request)

    http_request.headers['Host'] = 'vim.sexy'
    assert http_request.host == 'vim.sexy'
    assert f(http_request)
    assert not fn(http_request)
    
def test_filter_by_body():
    f = context.gen_filter_by_body(['ct', 'sexy'])
    fn = context.gen_filter_by_body(['nct', 'sexy'])
    
    # Test request bodies
    r = Request()
    r.start_line = 'GET /sexy HTTP/1.1'
    r.headers['Header'] = 'sexy'
    r.body = 'foo'
    assert not f(r)
    assert fn(r)

    r.body = 'sexy'
    assert f(r)
    assert not fn(r)

    # Test response bodies
    r = Request()
    rsp = Response()
    rsp.start_line = 'HTTP/1.1 200 OK'
    rsp.headers['sexy'] = 'sexy'
    r.start_line = 'GET /sexy HTTP/1.1'
    r.headers['Header'] = 'sexy'
    r.response = rsp
    assert not f(r)
    assert fn(r)

    rsp.body = 'sexy'
    assert f(r)
    assert not fn(r)

def test_filter_by_response_code(http_request):
    f = context.gen_filter_by_response_code(['eq', '200'])
    fn = context.gen_filter_by_response_code(['neq', '200'])

    r = Response()
    http_request.response = r
    r.start_line = 'HTTP/1.1 404 Not Found'
    assert not f(http_request)
    assert fn(http_request)

    r.start_line = 'HTTP/1.1 200 OK'
    assert f(http_request)
    assert not fn(http_request)
    
def test_filter_by_raw_headers_request():
    f1 = context.gen_filter_by_raw_headers(['ct', 'Sexy:'])
    fn1 = context.gen_filter_by_raw_headers(['nct', 'Sexy:'])
    f2 = context.gen_filter_by_raw_headers(['ct', 'sexy\r\nHeader'])
    fn2 = context.gen_filter_by_raw_headers(['nct', 'sexy\r\nHeader'])

    r = Request('GET / HTTP/1.1\r\n')
    rsp = Response('HTTP/1.1 200 OK\r\n')
    r.response = rsp
    r.headers['Header'] = 'Sexy'
    assert not f1(r)
    assert fn1(r)
    assert not f2(r)
    assert fn2(r)

    r = Request('GET / HTTP/1.1\r\n')
    rsp = Response('HTTP/1.1 200 OK\r\n')
    r.response = rsp
    r.headers['Sexy'] = 'sexy'
    assert f1(r)
    assert not fn1(r)
    assert not f2(r)
    assert fn2(r)

    r.headers['OtherHeader'] = 'sexy'
    r.headers['Header'] = 'foo'
    assert f1(r)
    assert not fn1(r)
    assert f2(r)
    assert not fn2(r)
    
def test_filter_by_raw_headers_response():
    f1 = context.gen_filter_by_raw_headers(['ct', 'Sexy:'])
    fn1 = context.gen_filter_by_raw_headers(['nct', 'Sexy:'])
    f2 = context.gen_filter_by_raw_headers(['ct', 'sexy\r\nHeader'])
    fn2 = context.gen_filter_by_raw_headers(['nct', 'sexy\r\nHeader'])

    r = Request('GET / HTTP/1.1\r\n')
    rsp = Response('HTTP/1.1 200 OK\r\n')
    r.response = rsp
    rsp.headers['Header'] = 'Sexy'
    assert not f1(r)
    assert fn1(r)
    assert not f2(r)
    assert fn2(r)

    r = Request('GET / HTTP/1.1\r\n')
    rsp = Response('HTTP/1.1 200 OK\r\n')
    r.response = rsp
    rsp.headers['Sexy'] = 'sexy'
    assert f1(r)
    assert not fn1(r)
    assert not f2(r)
    assert fn2(r)

    rsp.headers['OtherHeader'] = 'sexy'
    rsp.headers['Header'] = 'foo'
    assert f1(r)
    assert not fn1(r)
    assert f2(r)
    assert not fn2(r)

def test_filter_by_path(http_request):
    f = context.gen_filter_by_path(['ct', 'porn']) # find the fun websites
    fn = context.gen_filter_by_path(['nct', 'porn']) # find the boring websites
    
    http_request.start_line = 'GET / HTTP/1.1'
    assert not f(http_request)
    assert fn(http_request)

    http_request.start_line = 'GET /path/to/great/porn HTTP/1.1'
    assert f(http_request)
    assert not fn(http_request)

    http_request.start_line = 'GET /path/to/porn/great HTTP/1.1'
    assert f(http_request)
    assert not fn(http_request)

def test_gen_filter_by_submitted_cookies():
    f1 = context.gen_filter_by_submitted_cookies(['ct', 'Session'])
    f2 = context.gen_filter_by_submitted_cookies(['ct', 'Cookie', 'nct', 'CookieVal'])
    r = Request(('GET / HTTP/1.1\r\n'
                 'Cookie: foo=bar\r\n'
                 '\r\n'))
    assert not f1(r)
    assert not f2(r)

    r = Request(('GET / HTTP/1.1\r\n'
                 'Cookie: Session=bar\r\n'
                 '\r\n'))
    assert f1(r)
    assert not f2(r)

    r = Request(('GET / HTTP/1.1\r\n'
                 'Cookie: Session=bar; CookieThing=NoMatch\r\n'
                 '\r\n'))
    assert f1(r)
    assert f2(r)

    r = Request(('GET / HTTP/1.1\r\n'
                 'Cookie: Session=bar; CookieThing=CookieValue\r\n'
                 '\r\n'))
    assert f1(r)
    assert not f2(r)

def test_gen_filter_by_set_cookies():
    f1 = context.gen_filter_by_set_cookies(['ct', 'Session'])
    f2 = context.gen_filter_by_set_cookies(['ct', 'Cookie', 'ct', 'CookieVal'])

    r = Request('GET / HTTP/1.1\r\n\r\n')
    rsp = Response(('HTTP/1.1 200 OK\r\n'
                    'Set-Cookie: foo=bar\r\n'
                    '\r\n'))
    r.response = rsp
    assert not f1(r)
    assert not f2(r)

    r = Request('GET / HTTP/1.1\r\n\r\n')
    rsp = Response(('HTTP/1.1 200 OK\r\n'
                    'Set-Cookie: foo=bar\r\n'
                    'Set-Cookie: Session=Banana\r\n'
                    '\r\n'))
    r.response = rsp
    assert f1(r)
    assert not f2(r)

    r = Request('GET / HTTP/1.1\r\n\r\n')
    rsp = Response(('HTTP/1.1 200 OK\r\n'
                    'Set-Cookie: foo=bar\r\n'
                    'Set-Cookie: Session=Banana\r\n'
                    'Set-Cookie: CookieThing=NoMatch\r\n'
                    '\r\n'))
    r.response = rsp
    assert f1(r)
    assert not f2(r)

    r = Request('GET / HTTP/1.1\r\n\r\n')
    rsp = Response(('HTTP/1.1 200 OK\r\n'
                    'Set-Cookie: foo=bar\r\n'
                    'Set-Cookie: Session=Banana\r\n'
                    'Set-Cookie: CookieThing=CookieValue\r\n'
                    '\r\n'))
    r.response = rsp
    assert f1(r)
    assert f2(r)

def test_filter_by_params_get():
    f1 = context.gen_filter_by_params(['ct', 'Session'])
    f2 = context.gen_filter_by_params(['ct', 'Cookie', 'ct', 'CookieVal'])

    r = Request('GET / HTTP/1.1\r\n\r\n')
    assert not f1(r)
    assert not f2(r)

    r = Request('GET /?Session=foo HTTP/1.1\r\n\r\n')
    assert f1(r)
    assert not f2(r)

    r = Request('GET /?Session=foo&CookieThing=Fail HTTP/1.1\r\n\r\n')
    assert f1(r)
    assert not f2(r)

    r = Request('GET /?Session=foo&CookieThing=CookieValue HTTP/1.1\r\n\r\n')
    assert f1(r)
    assert f2(r)

def test_filter_by_params_post():
    f1 = context.gen_filter_by_params(['ct', 'Session'])
    f2 = context.gen_filter_by_params(['ct', 'Cookie', 'ct', 'CookieVal'])

    r = Request(('GET / HTTP/1.1\r\n'
                 'Content-Type: application/x-www-form-urlencoded\r\n\r\n'))
    r.body = 'foo=bar'
    assert not f1(r)
    assert not f2(r)

    r = Request(('GET / HTTP/1.1\r\n'
                 'Content-Type: application/x-www-form-urlencoded\r\n\r\n'))
    r.body = 'Session=bar'
    assert f1(r)
    assert not f2(r)

    r = Request(('GET / HTTP/1.1\r\n'
                 'Content-Type: application/x-www-form-urlencoded\r\n\r\n'))
    r.body = 'Session=bar&Cookie=foo'
    assert f1(r)
    assert not f2(r)

    r = Request(('GET / HTTP/1.1\r\n'
                 'Content-Type: application/x-www-form-urlencoded\r\n\r\n'))
    r.body = 'Session=bar&CookieThing=CookieValue'
    assert f1(r)
    assert f2(r)
