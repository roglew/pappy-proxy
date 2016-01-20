import pytest
from pappyproxy.session import Session
from pappyproxy.http import Request, Response, ResponseCookie

@pytest.fixture
def req():
    r = Request()
    r.start_line = 'GET / HTTP/1.1'
    return r

@pytest.fixture
def rsp():
    r = Response()
    r.start_line = 'HTTP/1.1 200 OK'
    return r

def test_session_basic(req, rsp):
    s = Session(
        cookie_vals={'session':'foo'},
        header_vals={'auth':'bar'},
    )

    assert 'session' not in req.cookies
    assert 'session' not in rsp.cookies
    assert 'auth' not in req.headers
    assert 'auth' not in rsp.headers
    s.apply_req(req)
    s.apply_rsp(rsp)
    assert req.cookies['session'] == 'foo'
    assert rsp.cookies['session'].cookie_str == 'session=foo'
    assert req.headers['auth'] == 'bar'
    assert 'auth' not in rsp.headers

def test_session_cookieobj_basic(req, rsp):
    s = Session(
        cookie_vals={'session':ResponseCookie('session=foo; secure; httponly; path=/')},
        header_vals={'auth':'bar'},
    )

    s.apply_req(req)
    s.apply_rsp(rsp)
    assert req.cookies['session'] == 'foo'
    assert rsp.cookies['session'].key == 'session'
    assert rsp.cookies['session'].val == 'foo'
    assert rsp.cookies['session'].secure
    assert rsp.cookies['session'].http_only
    assert rsp.cookies['session'].path == '/'
    assert req.headers['auth'] == 'bar'
    assert 'auth' not in rsp.headers

def test_session_get_req(req):
    req.headers['BasicAuth'] = 'asdfasdf'
    req.headers['Host'] = 'www.myfavoritecolor.foobar'
    req.cookies['session'] = 'foobar'
    req.cookies['favorite_color'] = 'blue'

    s = Session()
    s.get_req(req, ['session'], ['BasicAuth'])
    assert s.cookies == ['session']
    assert s.headers == ['BasicAuth']
    assert s.cookie_vals['session'].val == 'foobar'
    assert s.header_vals['BasicAuth'] == 'asdfasdf'
    assert 'Host' not in s.headers
    assert 'favorite_color' not in s.cookies

def test_session_get_rsp(rsp):
    rsp.headers['BasicAuth'] = 'asdfasdf'
    rsp.headers['Host'] = 'www.myfavoritecolor.foobar'
    rsp.set_cookie(ResponseCookie('session=foobar; secure; path=/'))
    rsp.set_cookie(ResponseCookie('favorite_color=blue; secure; path=/'))

    s = Session()
    s.get_rsp(rsp, ['session'])
    assert s.cookies == ['session']
    assert s.headers == []
    assert s.cookie_vals['session'].key == 'session'
    assert s.cookie_vals['session'].val == 'foobar'
    assert s.cookie_vals['session'].path == '/'
    assert s.cookie_vals['session'].secure

def test_session_mixed(req, rsp):
    s = Session(
        cookie_names=['session', 'state'],
        cookie_vals={'session':ResponseCookie('session=foo; secure; httponly; path=/')},
        header_vals={'auth':'bar'},
    )

    s.apply_req(req)
    s.apply_rsp(rsp)
    assert req.cookies['session'] == 'foo'
    assert rsp.cookies['session'].key == 'session'
    assert rsp.cookies['session'].val == 'foo'
    assert rsp.cookies['session'].secure
    assert rsp.cookies['session'].http_only
    assert rsp.cookies['session'].path == '/'
    assert 'auth' not in rsp.headers

    r = Response()
    r.start_line = 'HTTP/1.1 200 OK'
    r.set_cookie(ResponseCookie('state=bazzers'))
    r.set_cookie(ResponseCookie('session=buzzers'))
    s.get_rsp(r)
    assert s.cookie_vals['session'].val == 'buzzers'
    assert s.cookie_vals['state'].val == 'bazzers'
