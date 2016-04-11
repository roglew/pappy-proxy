import pytest
import mock
import random
import datetime
import pappyproxy
import base64
import collections

from pappyproxy import http
from pappyproxy.proxy import ProxyClientFactory, ProxyServerFactory, UpstreamHTTPProxyClient
from pappyproxy.http import Request, Response
from pappyproxy.macros import InterceptMacro
from testutil import mock_deferred, func_deleted, TLSStringTransport, freeze, mock_int_macro, no_tcp
from twisted.internet import defer

class InterceptMacroTest(InterceptMacro):

    def __init__(self, new_req=None, new_rsp=None):
        InterceptMacro.__init__(self)

        self.new_req = None
        self.new_rsp = None
        if new_req:
            self.intercept_requests = True
            self.new_req = new_req
        if new_rsp:
            self.intercept_responses = True
            self.new_rsp = new_rsp

    def mangle_request(self, request):
        if self.intercept_requests:
            return self.new_req
        else:
            return request

    def mangle_response(self, request):
        if self.intercept_responses:
            return self.new_rsp
        else:
            return request.response

class TestProxyConnection(object):

    @property
    def client_protocol(self):
        if 'protocol' not in self.conn_info:
            raise Exception('Connection to server not made. Cannot write data as server.')
        return self.conn_info['protocol']

    @property
    def client_factory(self):
        if 'protocol' not in self.conn_info:
            raise Exception('Connection to server not made. Cannot write data as server.')
        return self.conn_info['factory']
    
    def setUp(self, mocker, int_macros={}, socks_config=None, http_config=None, in_scope=True):
        self.mocker = mocker
        self.conn_info = {}

        # Mock config
        self.mock_config = pappyproxy.config.PappyConfig()
        self.mock_config.socks_proxy = socks_config
        self.mock_config.http_proxy = http_config
        self.mock_session = pappyproxy.pappy.PappySession(self.mock_config)
        mocker.patch.object(pappyproxy.pappy, 'session', new=self.mock_session)
        mocker.patch("pappyproxy.proxy.load_certs_from_dir", new=mock_generate_cert)

        # Listening server
        self.server_factory = ProxyServerFactory()
        self.server_factory.save_all = True
        self.server_factory.intercepting_macros = int_macros

        self.server_protocol = self.server_factory.buildProtocol(('127.0.0.1', 0))
        self.server_transport = TLSStringTransport()
        self.server_protocol.makeConnection(self.server_transport)

        # Other mocks
        self.req_save = mocker.patch.object(pappyproxy.http.Request, 'async_deep_save', autospec=True, side_effect=mock_req_async_save)
        self.submit_request = mocker.patch('pappyproxy.http.Request.submit_request',
                                           new=self.gen_mock_submit_request())
        self.get_endpoint = mocker.patch('pappyproxy.proxy.get_endpoint')
        self.in_scope = mocker.patch('pappyproxy.context.in_scope').return_value = in_scope

    def gen_mock_submit_request(self):
        orig = Request.submit_request
        def f(request, save_request=False, intercepting_macros={}, stream_transport=None):
            return orig(request, save_request=save_request,
                        intercepting_macros=intercepting_macros,
                        stream_transport=stream_transport,
                        _factory_string_transport=True,
                        _conn_info=self.conn_info)
        return f
    
    def perform_connect_request(self):
        self.write_as_browser('CONNECT https://www.AAAA.BBBB:443 HTTP/1.1\r\n\r\n')
        assert self.read_as_browser() == 'HTTP/1.1 200 Connection established\r\n\r\n'

    def write_as_browser(self, data):
        self.server_protocol.dataReceived(data)

    def read_as_browser(self):
        s = self.server_protocol.transport.value()
        self.server_protocol.transport.clear()
        return s

    def write_as_server(self, data):
        self.client_protocol.dataReceived(data)

    def read_as_server(self):
        s = self.client_protocol.transport.value()
        self.client_protocol.transport.clear()
        return s

    
def mock_req_async_save(req):
    req.reqid = str(random.randint(1,1000000))
    return mock_deferred()

def mock_mangle_response_side_effect(new_rsp):
    def f(request, mangle_macros):
        request.response = new_rsp
        return mock_deferred(True)
    return f

def mock_generate_cert(cert_dir):
    private_key = ('-----BEGIN PRIVATE KEY-----\n'
                   'MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQDAoClrYUEB7lM0\n'
                   'zQaKkXZVG2d1Bu9hV8urpx0gNXMbyZ2m3xb+sKZju/FHPuWenA4KaN5gRUT+oLfv\n'
                   'tnF6Ia0jpRNWnX0Fyn/irdg1BWGJn7k7mJ2D0NXZQczn2+xxY05599NfGWqNKCYy\n'
                   'jhSwPsUK+sGJqi7aSDdlS97ZTjrQVTTFsC0+kSu4lS5fsWXxqrKLa6Ao8W7abVRO\n'
                   'JHazh/cxM4UKpgWU+E6yD4o4ZgHY+SMTVUh/IOM8DuOVyLEWtx4oLNiLMlpWT3qy\n'
                   '4IMpOF6VuU6JF2HGV13SoJfhsLXsPRbLVTAnZvJcZwtgDm6NfKapU8W8olkDV1Bf\n'
                   'YQEMSNX7AgMBAAECggEBAII0wUrAdrzjaIMsg9tu8FofKBPHGFDok9f4Iov/FUwX\n'
                   'QOXnrxeCOTb5d+L89SH9ws/ui0LwD+8+nJcA8DvqP6r0jtnhov0jIMcNVDSi6oeo\n'
                   '3AEY7ICJzcQJ4oRn+K+8vPNdPhfuikPYe9l4iSuJgpAlaGWyD/GlFyz12DFz2/Wu\n'
                   'NIcqR1ucvezRHn3eGMtvDv2WGaN4ifUc30k8XgSUesmwSI6beb5+hxq7wXfsurnP\n'
                   'EUrPY9ts3lfiAgxzTKOuj1VR5hn7cJyLN8jF0mZs4D6eSSHorIddhmaNiCq5ZbMd\n'
                   'QdlDiPvnXHT41OoXOb7tDEt7SGoiRh2noCZ1aZiSziECgYEA+tuPPLYWU6JRB6EW\n'
                   'PhbcXQbh3vML7eT1q7DOz0jYCojgT2+k7EWSI8T830oQyjbpe3Z86XEgH7UBjUgq\n'
                   '27nJ4E6dQDYGbYCKEklOoCGLE7A60i1feIz8otOQRrbQ4jcpibEgscA6gzHmunYf\n'
                   'De5euUgYW+Rq2Vmr6/NzUaUgui8CgYEAxJMDwPOGgiLM1cczlaSIU9Obz+cVnwWn\n'
                   'nsdKYMto2V3yKLydDfjsgOgzxHOxxy+5L645TPxK6CkiISuhJ93kAFFtx+1sCBCT\n'
                   'tVzY5robVAekxA9tlPIxtsn3+/axx3n6HnV0oA/XtxkuOS5JImgEdXqFwJZkerGE\n'
                   'waftIU2FCfUCgYEArl8+ErJzlJEIiCgWIPSdGuD00pfZW/TCPCT7rKRy3+fDHBR7\n'
                   '7Gxzp/9+0utV/mnrJBH5w/8JmGCmgoF+oRtk01FyBzdGgolN8GYajD6kwPvH917o\n'
                   'tRAzcC9lY3IigoxbiEWid0wqoBVoz4XaEkH2gA44OG/vQcQOOEYSi9cfh6sCgYBg\n'
                   'KLaOXdJvuIxRCzgNvMW/k+VFh3pJJx//COg2f2qT4mQCT3nYiutOh8hDEoFluc+y\n'
                   'Jlz7bvNJrE14wnn8IYxWJ383bMoLC+jlsDyeaW3S5kZQbmehk/SDwTrg86W1udKD\n'
                   'sdtSLU3N0LCO4jh+bzm3Ki9hrXALoOkbPoU+ZEhvPQKBgQDf79XQ3RNxZSk+eFyq\n'
                   'qD8ytVqxEoD+smPDflXXseVH6o+pNWrF8+A0KqmO8c+8KVzWj/OfULO6UbKd3E+x\n'
                   '4JGkWu9yF1lEgtHgibF2ER8zCSIL4ikOEasPCkrKj5SrS4Q+j4u5ha76dIc2CVu1\n'
                   'hkX2PQ1xU4ocu06k373sf73A4Q==\n'
                   '-----END PRIVATE KEY-----')
    ca_key = ('-----BEGIN CERTIFICATE-----\n'
              'MIIDjzCCAncCFQCjC8r+I4xa7JoGUJYGOTcqDROA0DANBgkqhkiG9w0BAQsFADBg\n'
              'MQswCQYDVQQGEwJVUzERMA8GA1UECBMITWljaGlnYW4xEjAQBgNVBAcTCUFubiBB\n'
              'cmJvcjEUMBIGA1UEChMLUGFwcHkgUHJveHkxFDASBgNVBAMTC1BhcHB5IFByb3h5\n'
              'MB4XDTE1MTEyMDIxMTEzOVoXDTI1MTExNzIxMTEzOVowYDELMAkGA1UEBhMCVVMx\n'
              'ETAPBgNVBAgTCE1pY2hpZ2FuMRIwEAYDVQQHEwlBbm4gQXJib3IxFDASBgNVBAoT\n'
              'C1BhcHB5IFByb3h5MRQwEgYDVQQDEwtQYXBweSBQcm94eTCCASIwDQYJKoZIhvcN\n'
              'AQEBBQADggEPADCCAQoCggEBAMCgKWthQQHuUzTNBoqRdlUbZ3UG72FXy6unHSA1\n'
              'cxvJnabfFv6wpmO78Uc+5Z6cDgpo3mBFRP6gt++2cXohrSOlE1adfQXKf+Kt2DUF\n'
              'YYmfuTuYnYPQ1dlBzOfb7HFjTnn3018Zao0oJjKOFLA+xQr6wYmqLtpIN2VL3tlO\n'
              'OtBVNMWwLT6RK7iVLl+xZfGqsotroCjxbtptVE4kdrOH9zEzhQqmBZT4TrIPijhm\n'
              'Adj5IxNVSH8g4zwO45XIsRa3Higs2IsyWlZPerLggyk4XpW5TokXYcZXXdKgl+Gw\n'
              'tew9FstVMCdm8lxnC2AObo18pqlTxbyiWQNXUF9hAQxI1fsCAwEAAaNFMEMwEgYD\n'
              'VR0TAQH/BAgwBgEB/wIBADAOBgNVHQ8BAf8EBAMCAQYwHQYDVR0OBBYEFNo5o+5e\n'
              'a0sNMlW/75VgGJCv2AcJMA0GCSqGSIb3DQEBCwUAA4IBAQBdJDhxbmoEe27bD8me\n'
              'YTcLGjs/StKkSil7rLbX+tBCwtkm5UEEejBuAhKk2FuAXW8yR1FqKJSZwVCAocBT\n'
              'Bo/+97Ee+h7ywrRFhATEr9D/TbbHKOjCjDzOMl9yLZa2DKErZjbI30ZD6NafWS/X\n'
              'hx5X1cGohHcVVzT4jIgUEU70vvYfNn8CTZm4oJ7qqRe/uQPUYy0rwvbd60oprtGg\n'
              'jNv1H5R4ODHUMBXAI9H7ft9cWrd0fBQjxhoj8pvgJXEZ52flXSqQc7qHLg1wO/zC\n'
              'RUgpTcNAb2qCssBKbj+c1vKEPRUJfw6UYb0s1462rQNc8BgZiKaNbwokFmkAnjUg\n'
              'AvnX\n'
              '-----END CERTIFICATE-----')
    return (ca_key, private_key)

########
## Tests

def test_no_tcp():
    from twisted.internet.endpoints import SSL4ClientEndpoint, TCP4ClientEndpoint
    from txsocksx.client import SOCKS5ClientEndpoint
    from txsocksx.tls import TLSWrapClientEndpoint
    with pytest.raises(NotImplementedError):
        SSL4ClientEndpoint('aasdfasdf.sdfwerqwer')
    with pytest.raises(NotImplementedError):
        TCP4ClientEndpoint('aasdfasdf.sdfwerqwer')
    with pytest.raises(NotImplementedError):
        SOCKS5ClientEndpoint('aasdfasdf.sdfwerqwer')
    with pytest.raises(NotImplementedError):
        TLSWrapClientEndpoint('asdf.2341')
        
def test_proxy_server_connect(mocker):
    proxy = TestProxyConnection()
    proxy.setUp(mocker)
    proxy.write_as_browser('CONNECT https://www.AAAA.BBBB:443 HTTP/1.1\r\n\r\n')
    rsp = proxy.read_as_browser()
    print rsp
    assert rsp == 'HTTP/1.1 200 Connection established\r\n\r\n'

def test_proxy_server_forward_basic(mocker):
    proxy = TestProxyConnection()
    proxy.setUp(mocker)
    req_contents = ('POST /fooo HTTP/1.1\r\n'
                    'Test-Header: foo\r\n'
                    'Content-Length: 4\r\n'
                    'Host: www.AAAA.BBBB\r\n'
                    '\r\n'
                    'ABCD')
    rsp_contents = ('HTTP/1.1 200 OK\r\n\r\n')
    proxy.write_as_browser(req_contents)
    assert proxy.read_as_server() == req_contents
    proxy.write_as_server(rsp_contents)
    assert proxy.read_as_browser() == rsp_contents
    proxy.get_endpoint.assert_called_with('www.AAAA.BBBB', 80, False, socks_config=None, use_http_proxy=True)
    assert proxy.req_save.called

def test_proxy_server_forward_basic_ssl(mocker):
    proxy = TestProxyConnection()
    proxy.setUp(mocker)
    proxy.perform_connect_request()
    req_contents = ('POST /fooo HTTP/1.1\r\n'
                    'Test-Header: foo\r\n'
                    'Content-Length: 4\r\n'
                    '\r\n'
                    'ABCD')
    rsp_contents = ('HTTP/1.1 200 OK\r\n\r\n')
    proxy.write_as_browser(req_contents)
    assert proxy.read_as_server() == req_contents
    proxy.write_as_server(rsp_contents)
    assert proxy.read_as_browser() == rsp_contents
    assert proxy.req_save.called
    proxy.get_endpoint.assert_called_with('www.AAAA.BBBB', 443, True, socks_config=None, use_http_proxy=True)

def test_proxy_server_connect_uri(mocker):
    proxy = TestProxyConnection()
    proxy.setUp(mocker)
    proxy.write_as_browser('CONNECT https://www.AAAA.BBBB:443 HTTP/1.1\r\n\r\n')
    proxy.read_as_browser()
    req_contents = ('POST /fooo HTTP/1.1\r\n'
                    'Test-Header: foo\r\n'
                    'Content-Length: 4\r\n'
                    '\r\n'
                    'ABCD')
    proxy.write_as_browser(req_contents)
    assert proxy.client_protocol.transport.startTLS.called
    assert proxy.client_factory.request.host == 'www.AAAA.BBBB'
    assert proxy.client_factory.request.port == 443
    assert proxy.client_factory.request.is_ssl == True
    assert proxy.read_as_server() == req_contents
    assert proxy.client_protocol.transport.startTLS.called
    assert proxy.req_save.called
    proxy.get_endpoint.assert_called_with('www.AAAA.BBBB', 443, True, socks_config=None, use_http_proxy=True)

def test_proxy_server_connect_uri_alt_port(mocker):
    proxy = TestProxyConnection()
    proxy.setUp(mocker)
    proxy.write_as_browser('CONNECT https://www.AAAA.BBBB:80085 HTTP/1.1\r\n\r\n')
    proxy.read_as_browser()
    req_contents = ('POST /fooo HTTP/1.1\r\n'
                    'Test-Header: foo\r\n'
                    'Content-Length: 4\r\n'
                    '\r\n'
                    'ABCD')
    proxy.write_as_browser(req_contents)
    assert proxy.client_factory.request.host == 'www.AAAA.BBBB'
    assert proxy.client_factory.request.port == 80085
    assert proxy.client_factory.request.is_ssl == True
    assert proxy.req_save.called
    proxy.get_endpoint.assert_called_with('www.AAAA.BBBB', 80085, True, socks_config=None, use_http_proxy=True)

def test_proxy_server_socks_basic(mocker):
    proxy = TestProxyConnection()
    proxy.setUp(mocker, socks_config={'host': 'www.banana.faketld', 'port': 1337})
    proxy.write_as_browser('CONNECT https://www.AAAA.BBBB:80085 HTTP/1.1\r\n\r\n')
    proxy.read_as_browser()
    req_contents = ('POST /fooo HTTP/1.1\r\n'
                    'Test-Header: foo\r\n'
                    'Content-Length: 4\r\n'
                    '\r\n'
                    'ABCD')
    proxy.write_as_browser(req_contents)
    proxy.get_endpoint.assert_called_with('www.AAAA.BBBB', 80085, True,
                                          socks_config={'host':'www.banana.faketld', 'port':1337},
                                          use_http_proxy=True)

def test_proxy_server_http_basic(mocker):
    proxy = TestProxyConnection()
    proxy.setUp(mocker, http_config={'host': 'www.banana.faketld', 'port': 1337})
    proxy.write_as_browser('CONNECT https://www.AAAA.BBBB:80085 HTTP/1.1\r\n\r\n')
    proxy.read_as_browser()
    req_contents = ('POST /fooo HTTP/1.1\r\n'
                    'Test-Header: foo\r\n'
                    'Content-Length: 4\r\n'
                    '\r\n'
                    'ABCD')
    proxy.write_as_browser(req_contents)
    assert proxy.req_save.called
    proxy.get_endpoint.assert_called_with('www.AAAA.BBBB', 80085, True,
                                          socks_config=None,
                                          use_http_proxy=True)

def test_proxy_server_360_noscope(mocker):
    proxy = TestProxyConnection()
    proxy.setUp(mocker, in_scope=False, socks_config={'host': 'www.banana.faketld', 'port': 1337})
    proxy.write_as_browser('CONNECT https://www.AAAA.BBBB:80085 HTTP/1.1\r\n\r\n')
    proxy.read_as_browser()
    req_contents = ('POST /fooo HTTP/1.1\r\n'
                    'Test-Header: foo\r\n'
                    'Content-Length: 4\r\n'
                    '\r\n'
                    'ABCD')
    proxy.write_as_browser(req_contents)
    assert not proxy.req_save.called
    proxy.get_endpoint.assert_called_with('www.AAAA.BBBB', 80085, True,
                                          socks_config=None,
                                          use_http_proxy=False)
    
def test_proxy_server_macro_simple(mocker):
    proxy = TestProxyConnection()

    new_req_contents = 'GET / HTTP/1.1\r\nMangled: Very yes\r\n\r\n'
    new_rsp_contents = 'HTTP/1.1 200 OKILIE DOKILIE\r\nMangled: Very yes\r\n\r\n'
    new_req = Request(new_req_contents)
    new_rsp = Response(new_rsp_contents)
    test_macro = InterceptMacroTest(new_req=new_req, new_rsp=new_rsp)
    proxy.setUp(mocker, int_macros={'test_macro': test_macro})
    proxy.write_as_browser('GET /serious.php HTTP/1.1\r\n\r\n')
    assert proxy.read_as_server() == new_req_contents
    proxy.write_as_server('HTTP/1.1 404 NOT FOUND\r\n\r\n')
    assert proxy.read_as_browser() == new_rsp_contents

def test_proxy_server_macro_multiple(mocker):
    proxy = TestProxyConnection()

    new_req_contents1 = 'GET / HTTP/1.1\r\nMangled: Very yes\r\n\r\n'
    new_rsp_contents1 = 'HTTP/1.1 200 OKILIE DOKILIE\r\nMangled: Very yes\r\n\r\n'
    new_req1 = Request(new_req_contents1)
    new_rsp1 = Response(new_rsp_contents1)

    new_req_contents2 = 'GET / HTTP/1.1\r\nMangled: Very very yes\r\n\r\n'
    new_rsp_contents2 = 'HTTP/1.1 200 OKILIE DOKILIE\r\nMangled: Very very yes\r\n\r\n'
    new_req2 = Request(new_req_contents2)
    new_rsp2 = Response(new_rsp_contents2)

    test_macro1 = InterceptMacroTest(new_req=new_req1, new_rsp=new_rsp1)
    test_macro2 = InterceptMacroTest(new_req=new_req2, new_rsp=new_rsp2)

    macros = collections.OrderedDict()
    macros['macro1'] = test_macro1
    macros['macro2'] = test_macro2

    proxy.setUp(mocker, int_macros=macros)
    proxy.write_as_browser('GET /serious.php HTTP/1.1\r\n\r\n')
    assert proxy.read_as_server() == new_req_contents2
    proxy.write_as_server('HTTP/1.1 404 NOT FOUND\r\n\r\n')
    assert proxy.read_as_browser() == new_rsp_contents2

def test_proxy_server_macro_360_noscope(mocker):
    proxy = TestProxyConnection()

    new_req_contents = 'GET / HTTP/1.1\r\nMangled: Very yes\r\n\r\n'
    new_rsp_contents = 'HTTP/1.1 200 OKILIE DOKILIE\r\nMangled: Very yes\r\n\r\n'
    new_req = Request(new_req_contents)
    new_rsp = Response(new_rsp_contents)
    test_macro = InterceptMacroTest(new_req=new_req, new_rsp=new_rsp)
    proxy.setUp(mocker, int_macros={'test_macro': test_macro}, in_scope=False)
    proxy.write_as_browser('GET /serious.php HTTP/1.1\r\n\r\n')
    assert proxy.read_as_server() == 'GET /serious.php HTTP/1.1\r\n\r\n'
    proxy.write_as_server('HTTP/1.1 404 NOT FOUND\r\n\r\n')
    assert proxy.read_as_browser() == 'HTTP/1.1 404 NOT FOUND\r\n\r\n'

def test_proxy_server_stream_simple(mocker):
    proxy = TestProxyConnection()
    proxy.setUp(mocker)
    req_contents = ('POST /fooo HTTP/1.1\r\n'
                    'Test-Header: foo\r\n'
                    'Content-Length: 4\r\n'
                    'Host: www.AAAA.BBBB\r\n'
                    '\r\n'
                    'ABCD')
    rsp_contents = ('HTTP/1.1 200 OK\r\n\r\n')
    proxy.write_as_browser(req_contents)
    assert proxy.read_as_server() == req_contents
    proxy.write_as_server(rsp_contents[:20])
    assert proxy.read_as_browser() == rsp_contents[:20]
    proxy.write_as_server(rsp_contents[20:])
    assert proxy.read_as_browser() == rsp_contents[20:]

def test_proxy_server_macro_stream(mocker):
    proxy = TestProxyConnection()

    new_req_contents = 'GET / HTTP/1.1\r\nMangled: Very yes\r\n\r\n'
    new_rsp_contents = 'HTTP/1.1 200 OKILIE DOKILIE\r\nMangled: Very yes\r\n\r\n'
    new_req = Request(new_req_contents)
    new_rsp = Response(new_rsp_contents)
    test_macro = InterceptMacroTest(new_req=new_req, new_rsp=new_rsp)
    proxy.setUp(mocker, int_macros={'test_macro': test_macro})
    proxy.write_as_browser('GET /serious.php HTTP/1.1\r\n\r\n')
    assert proxy.read_as_server() == new_req_contents
    proxy.write_as_server('HTTP/1.1 404 ')
    assert proxy.read_as_browser() == ''
    proxy.write_as_server('NOT FOUND\r\n\r\n')
    assert proxy.read_as_browser() == new_rsp_contents

# It doesn't stream if out of scope and macros are active, but whatever.
# def test_proxy_server_macro_stream_360_noscope(mocker):
#     proxy = TestProxyConnection()

#     new_req_contents = 'GET / HTTP/1.1\r\nMangled: Very yes\r\n\r\n'
#     new_rsp_contents = 'HTTP/1.1 200 OKILIE DOKILIE\r\nMangled: Very yes\r\n\r\n'
#     new_req = Request(new_req_contents)
#     new_rsp = Response(new_rsp_contents)
#     test_macro = InterceptMacroTest(new_req=new_req, new_rsp=new_rsp)
#     proxy.setUp(mocker, int_macros={'test_macro': test_macro}, in_scope=False)
#     proxy.write_as_browser('GET /serious.php HTTP/1.1\r\n\r\n')
#     assert proxy.read_as_server() == 'GET /serious.php HTTP/1.1\r\n\r\n'
#     proxy.write_as_server('HTTP/1.1 404 ')
#     assert proxy.read_as_browser() == 'HTTP/1.1 404 '
#     proxy.write_as_server('NOT FOUND\r\n\r\n')
#     assert proxy.read_as_browser() == 'NOT FOUND\r\n\r\n'
