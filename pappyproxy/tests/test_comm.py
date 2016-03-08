import base64
import pytest
import mock
import json
import datetime
import pappyproxy

from pappyproxy.util import PappyException
from pappyproxy.comm import CommServer
from pappyproxy.http import Request, Response
from testutil import mock_deferred, func_deleted, TLSStringTransport, freeze, mock_int_macro, no_tcp

@pytest.fixture
def http_request():
    req = Request('GET / HTTP/1.1\r\n\r\n')
    req.host = 'www.foo.faketld'
    req.port = '1337'
    req.is_ssl = True
    req.reqid = 123

    rsp = Response('HTTP/1.1 200 OK\r\n\r\n')
    req.response = rsp
    return req

def perform_comm(line):
    serv = CommServer()
    serv.transport = TLSStringTransport()
    serv.lineReceived(line)
    n = datetime.datetime.now()
    while serv.transport.value() == '':
        t = datetime.datetime.now()
        if (t-n).total_seconds() > 5:
            raise Exception("Request timed out")
    return serv.transport.value()
    
def test_simple():
    v = perform_comm('{"action": "ping"}')
    assert json.loads(v) == {'ping': 'pong', 'success': True}
    
def mock_loader(rsp):
    def f(*args, **kwargs):
        return rsp
    return classmethod(f)

def mock_loader_fail():
    def f(*args, **kwargs):
        raise PappyException("lololo message don't exist dawg")
    return classmethod(f)
    
def test_get_request(mocker, http_request):
    mocker.patch.object(pappyproxy.http.Request, 'load_request', new=mock_loader(http_request))
    v = perform_comm('{"action": "get_request", "reqid": "1"}')

    expected_data = json.loads(http_request.to_json())
    expected_data['success'] = True
    assert json.loads(v) == expected_data

def test_get_request_fail(mocker, http_request):
    mocker.patch.object(pappyproxy.http.Request, 'load_request', new=mock_loader_fail())
    v = json.loads(perform_comm('{"action": "get_request", "reqid": "1"}'))

    assert v['success'] == False
    assert 'message' in v
    
def test_get_response(mocker, http_request):
    mocker.patch.object(pappyproxy.http.Request, 'load_request', new=mock_loader(http_request))
    mocker.patch.object(pappyproxy.http.Response, 'load_response', new=mock_loader(http_request.response))
    v = perform_comm('{"action": "get_response", "reqid": "1"}')

    expected_data = json.loads(http_request.response.to_json())
    expected_data['success'] = True
    assert json.loads(v) == expected_data

def test_get_response_fail(mocker, http_request):
    mocker.patch.object(pappyproxy.http.Request, 'load_request', new=mock_loader(http_request))
    mocker.patch.object(pappyproxy.http.Response, 'load_response', new=mock_loader_fail())
    v = json.loads(perform_comm('{"action": "get_response", "reqid": "1"}'))

    assert v['success'] == False
    assert 'message' in v

def test_submit_request(mocker, http_request):
    mocker.patch.object(pappyproxy.http.Request, 'submit_new', new=mock_loader(http_request))
    mocker.patch('pappyproxy.http.Request.async_deep_save').return_value = mock_deferred()

    comm_data = {"action": "submit"}
    comm_data['host'] = http_request.host
    comm_data['port'] = http_request.port
    comm_data['is_ssl'] = http_request.is_ssl
    comm_data['full_message'] = base64.b64encode(http_request.full_message)
    comm_data['tags'] = ['footag']
    v = perform_comm(json.dumps(comm_data))

    expected_data = {}
    expected_data['request'] = json.loads(http_request.to_json())
    expected_data['response'] = json.loads(http_request.response.to_json())
    expected_data['success'] = True
    expected_data['request']['tags'] = ['footag']
    assert json.loads(v) == expected_data

def test_submit_request_fail(mocker, http_request):
    mocker.patch.object(pappyproxy.http.Request, 'submit_new', new=mock_loader_fail())
    mocker.patch('pappyproxy.http.Request.async_deep_save').return_value = mock_deferred()

    comm_data = {"action": "submit"}
    comm_data['full_message'] = base64.b64encode('HELLO THIS IS REQUEST\r\nWHAT IS HEADER FORMAT\r\n')
    v = json.loads(perform_comm(json.dumps(comm_data)))
    print v

    assert v['success'] == False
    assert 'message' in v

