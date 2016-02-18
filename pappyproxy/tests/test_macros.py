import pytest
import string
import mock

from collections import OrderedDict
from testutil import mock_deferred, func_deleted, TLSStringTransport, freeze, mock_int_macro, no_tcp
from pappyproxy.http import Request, Response
from pappyproxy import macros

class CloudToButtMacro(macros.InterceptMacro):

    def __init__(self):
        macros.InterceptMacro.__init__(self)
        self.intercept_requests = True
        self.intercept_responses = True
    
    def mangle_request(self, request):
        return Request(string.replace(request.full_message, 'cloud', 'butt'))

    def mangle_response(self, response):
        return Response(string.replace(response.full_message, 'cloud', 'butt'))

@pytest.fixture
def httprequest():
    return Request(('POST /test-request HTTP/1.1\r\n'
                    'Content-Length: 4\r\n'
                    '\r\n'
                    'AAAA'))

@pytest.inlineCallbacks
def test_mangle_request_simple(httprequest):
    orig_req = httprequest.copy() # in case it gets mangled
    (new_req, mangled) = yield macros.mangle_request(orig_req, {})
    assert new_req == orig_req
    assert httprequest == orig_req
    assert not mangled

@pytest.inlineCallbacks
def test_mangle_request_single(httprequest):
    orig_req = httprequest.copy() # in case it gets mangled
    macro = mock_int_macro(modified_req=('GET /modified HTTP/1.1\r\n\r\n'))
    expected_req = Request('GET /modified HTTP/1.1\r\n\r\n')
    (new_req, mangled) = yield macros.mangle_request(orig_req, {'testmacro': macro})
    assert new_req == expected_req
    assert httprequest == orig_req
    assert httprequest.unmangled is None
    assert new_req.unmangled == orig_req
    assert mangled

@pytest.inlineCallbacks
def test_mangle_request_multiple(httprequest):
    orig_req = httprequest.copy() # in case it gets mangled
    macro = mock_int_macro(modified_req=('GET /cloud HTTP/1.1\r\n\r\n'))
    macro2 = CloudToButtMacro()
    intmacros = OrderedDict()
    intmacros['testmacro'] = macro
    intmacros['testmacro2'] = macro2
    (new_req, mangled) = yield macros.mangle_request(orig_req, intmacros)

    expected_req = Request('GET /butt HTTP/1.1\r\n\r\n')
    assert new_req == expected_req
    assert httprequest == orig_req
    assert httprequest.unmangled is None
    assert new_req.unmangled == orig_req
    assert mangled
