import pytest
import mock
import random
import datetime
import pappyproxy

from pappyproxy import http
from pappyproxy.proxy import ProxyClientFactory, ProxyServerFactory
from testutil import mock_deferred, func_deleted, TLSStringTransport, freeze, mock_int_macro, no_tcp

@pytest.fixture(autouse=True)
def proxy_patches(mocker):
    #mocker.patch("twisted.test.iosim.FakeTransport.startTLS")
    mocker.patch("pappyproxy.proxy.load_certs_from_dir", new=mock_generate_cert)
    
@pytest.fixture
def server_factory():
    return gen_server_factory()

def socks_config(mocker, config):
    mocker.patch('pappyproxy.config.SOCKS_PROXY', new=config)

def gen_server_factory(int_macros={}):
    factory = ProxyServerFactory()
    factory.save_all = True
    factory.intercepting_macros = int_macros
    return factory

def gen_server_protocol(int_macros={}):
    server_factory = gen_server_factory(int_macros=int_macros)
    protocol = server_factory.buildProtocol(('127.0.0.1', 0))
    tr = TLSStringTransport()
    protocol.makeConnection(tr)
    return protocol

def gen_client_protocol(req, stream_response=False):
    return_transport = TLSStringTransport()
    factory = ProxyClientFactory(req,
                                 save_all=True,
                                 stream_response=stream_response,
                                 return_transport=return_transport)
    protocol = factory.buildProtocol(('127.0.0.1', 0), _do_callback=False)
    tr = TLSStringTransport()
    protocol.makeConnection(tr)
    return protocol

@pytest.fixture
def server_protocol():
    return gen_server_protocol()

def mock_req_async_save(req):
    req.reqid = str(random.randint(1,1000000))
    return mock_deferred()

####################
## Mock functions

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
        
################
### Proxy Server

def test_proxy_server_connect(mocker, server_protocol):
    mstarttls = mocker.patch('pappyproxy.tests.testutil.TLSStringTransport.startTLS')
    server_protocol.dataReceived('CONNECT https://www.AAAA.BBBB:443 HTTP/1.1\r\n\r\n')
    assert server_protocol.transport.value() == 'HTTP/1.1 200 Connection established\r\n\r\n'
    assert mstarttls.called

def test_proxy_server_forward_basic(mocker, server_protocol):
    mforward = mocker.patch('pappyproxy.proxy.ProxyServer._generate_and_submit_client')
    mreset = mocker.patch('pappyproxy.proxy.ProxyServer._reset')

    req_contents = ('POST /fooo HTTP/1.1\r\n'
                    'Test-Header: foo\r\n'
                    'Content-Length: 4\r\n'
                    '\r\n'
                    'ABCD')
    server_protocol.dataReceived(req_contents)

    assert mforward.called
    assert mreset.called
    assert server_protocol._request_obj.full_message == req_contents

def test_proxy_server_connect_uri(mocker, server_protocol):
    mforward = mocker.patch('pappyproxy.proxy.ProxyServer._generate_and_submit_client')
    server_protocol.dataReceived('CONNECT https://www.AAAA.BBBB:443 HTTP/1.1\r\n\r\n')
    server_protocol.dataReceived('GET /fooo HTTP/1.1\r\nTest-Header: foo\r\n\r\n')
    assert server_protocol._connect_uri == 'https://www.AAAA.BBBB'
    assert server_protocol._request_obj.url == 'https://www.AAAA.BBBB'
    assert server_protocol._request_obj.port == 443

## ProxyServer._generate_and_submit_client

def test_proxy_server_create_client_factory(mocker, server_protocol):
    mfactory = mock.MagicMock()
    mfactory_class = mocker.patch('pappyproxy.proxy.ProxyClientFactory')
    mfactory_class.return_value = mfactory

    mocker.patch('pappyproxy.proxy.ProxyServer._make_remote_connection')

    mfactory.prepare_request.return_value = mock_deferred(None)
    full_req = ('POST /fooo HTTP/1.1\r\n'
                'Test-Header: foo\r\n'
                'Content-Length: 4\r\n'
                '\r\n'
                'ABCD')
    server_protocol.connection_id = 100

    server_protocol.dataReceived(full_req)
    # Make sure we created a ClientFactory with the right arguments
    f_args, f_kwargs = mfactory_class.call_args
    assert len(f_args) == 1

    # Make sure the request got to the client class
    req = f_args[0]
    assert req.full_message == full_req

    # Make sure the correct settings got to the proxy
    assert f_kwargs['stream_response'] == True
    assert f_kwargs['save_all'] == True

    # Make sure we initialized the client factory
    assert mfactory.prepare_request.called
    assert mfactory.connection_id == 100
    assert server_protocol._make_remote_connection.called # should be immediately called because mock deferred
    
def test_proxy_server_no_streaming_with_int_macros(mocker):
    mfactory = mock.MagicMock()
    mfactory_class = mocker.patch('pappyproxy.proxy.ProxyClientFactory')
    mfactory_class.return_value = mfactory

    mocker.patch('pappyproxy.proxy.ProxyServer._make_remote_connection')

    mfactory.prepare_request.return_value = mock_deferred(None)
    full_req = ('POST /fooo HTTP/1.1\r\n'
                'Test-Header: foo\r\n'
                'Content-Length: 4\r\n'
                '\r\n'
                'ABCD')

    int_macros = [{'mockmacro': mock_int_macro(modified_req='GET / HTTP/1.1\r\n\r\n')}]
    server_protocol = gen_server_protocol(int_macros=int_macros)
    server_protocol.dataReceived(full_req)
    f_args, f_kwargs = mfactory_class.call_args
    assert f_kwargs['stream_response'] == False
    
## ProxyServer._make_remote_connection

@pytest.inlineCallbacks
def test_proxy_server_make_tcp_connection(mocker, server_protocol):
    mtcpe_class = mocker.patch("twisted.internet.endpoints.TCP4ClientEndpoint")
    mtcpe_class.return_value = mtcpe = mock.MagicMock()
    mtcpe.connect.return_value = mock_deferred()

    server_protocol._client_factory = mock.MagicMock() # We already tested that this gets set up correctly

    req = http.Request("GET / HTTP/1.1\r\n\r\n")
    req.host = 'Foo.Bar.Brazzers'
    req.port = 80085
    server_protocol._request_obj = req

    yield server_protocol._make_remote_connection(req)
    targs, tkwargs =  mtcpe_class.call_args
    assert targs[1] == 'Foo.Bar.Brazzers'
    assert targs[2] == 80085
    assert tkwargs == {}
    mtcpe.connect.assert_called_once_with(server_protocol._client_factory)

@pytest.inlineCallbacks
def test_proxy_server_make_ssl_connection(mocker, server_protocol):
    mssle_class = mocker.patch("twisted.internet.endpoints.SSL4ClientEndpoint")
    mssle_class.return_value = mssle = mock.MagicMock()
    mssle.connect.return_value = mock_deferred()

    server_protocol._client_factory = mock.MagicMock() # We already tested that this gets set up correctly

    req = http.Request("GET / HTTP/1.1\r\n\r\n", is_ssl=True)
    req.host = 'Foo.Bar.Brazzers'
    req.port = 80085
    server_protocol._request_obj = req

    yield server_protocol._make_remote_connection(req)
    targs, tkwargs =  mssle_class.call_args
    assert targs[1] == 'Foo.Bar.Brazzers'
    assert targs[2] == 80085
    assert tkwargs == {}
    mssle.connect.assert_called_once_with(server_protocol._client_factory)

@pytest.inlineCallbacks
def test_proxy_server_make_tcp_connection_socks(mocker):
    socks_config(mocker, {'host': '12345', 'port': 5555})

    tls_wrap_class = mocker.patch("txsocksx.tls.TLSWrapClientEndpoint")
    
    mtcpe_class = mocker.patch("twisted.internet.endpoints.TCP4ClientEndpoint")
    mtcpe_class.return_value = mtcpe = mock.MagicMock()

    socks_class = mocker.patch("txsocksx.client.SOCKS5ClientEndpoint")
    socks_class.return_value = sockse = mock.MagicMock()

    server_protocol = gen_server_protocol()
    server_protocol._client_factory = mock.MagicMock() # We already tested that this gets set up correctly

    req = http.Request("GET / HTTP/1.1\r\n\r\n")
    req.host = 'Foo.Bar.Brazzers'
    req.port = 80085
    server_protocol._request_obj = req

    yield server_protocol._make_remote_connection(req)
    sargs, skwargs =  socks_class.call_args
    targs, tkwargs =  mtcpe_class.call_args
    assert targs[1] == '12345'
    assert targs[2] == 5555
    assert sargs[0] == 'Foo.Bar.Brazzers'
    assert sargs[1] == 80085
    assert sargs[2] == mtcpe
    assert skwargs == {'methods': {'anonymous': ()}}
    assert not tls_wrap_class.called
    sockse.connect.assert_called_once_with(server_protocol._client_factory)

@pytest.inlineCallbacks
def test_proxy_server_make_ssl_connection_socks(mocker):
    socks_config(mocker, {'host': '12345', 'port': 5555})

    tls_wrap_class = mocker.patch("txsocksx.tls.TLSWrapClientEndpoint")
    tls_wrape = tls_wrap_class.return_value = mock.MagicMock()
    
    mtcpe_class = mocker.patch("twisted.internet.endpoints.TCP4ClientEndpoint")
    mtcpe_class.return_value = mtcpe = mock.MagicMock()

    socks_class = mocker.patch("txsocksx.client.SOCKS5ClientEndpoint")
    socks_class.return_value = sockse = mock.MagicMock()

    server_protocol = gen_server_protocol()
    server_protocol._client_factory = mock.MagicMock() # We already tested that this gets set up correctly

    req = http.Request("GET / HTTP/1.1\r\n\r\n")
    req.host = 'Foo.Bar.Brazzers'
    req.port = 80085
    req.is_ssl = True
    server_protocol._request_obj = req

    yield server_protocol._make_remote_connection(req)
    sargs, skwargs =  socks_class.call_args
    targs, tkwargs =  mtcpe_class.call_args
    assert targs[1] == '12345'
    assert targs[2] == 5555
    assert sargs[0] == 'Foo.Bar.Brazzers'
    assert sargs[1] == 80085
    assert sargs[2] == mtcpe
    assert skwargs == {'methods': {'anonymous': ()}}
    assert not sockse.called
    tls_wrape.connect.assert_called_once_with(server_protocol._client_factory)

@pytest.inlineCallbacks
def test_proxy_server_make_ssl_connection_socks_username_only(mocker):
    socks_config(mocker, {'host': '12345', 'port': 5555, 'username': 'foo'})

    tls_wrap_class = mocker.patch("txsocksx.tls.TLSWrapClientEndpoint")
    tls_wrape = tls_wrap_class.return_value = mock.MagicMock()
    
    mtcpe_class = mocker.patch("twisted.internet.endpoints.TCP4ClientEndpoint")
    mtcpe_class.return_value = mtcpe = mock.MagicMock()

    socks_class = mocker.patch("txsocksx.client.SOCKS5ClientEndpoint")
    socks_class.return_value = sockse = mock.MagicMock()

    server_protocol = gen_server_protocol()
    server_protocol._client_factory = mock.MagicMock() # We already tested that this gets set up correctly

    req = http.Request("GET / HTTP/1.1\r\n\r\n")
    req.host = 'Foo.Bar.Brazzers'
    req.port = 80085
    req.is_ssl = True
    server_protocol._request_obj = req

    yield server_protocol._make_remote_connection(req)
    sargs, skwargs =  socks_class.call_args
    targs, tkwargs =  mtcpe_class.call_args
    assert targs[1] == '12345'
    assert targs[2] == 5555
    assert sargs[0] == 'Foo.Bar.Brazzers'
    assert sargs[1] == 80085
    assert sargs[2] == mtcpe
    assert skwargs == {'methods': {'anonymous': ()}}
    assert not sockse.called
    tls_wrape.connect.assert_called_once_with(server_protocol._client_factory)

@pytest.inlineCallbacks
def test_proxy_server_make_ssl_connection_socks_username_password(mocker):
    socks_config(mocker, {'host': '12345', 'port': 5555, 'username': 'foo', 'password': 'password'})

    tls_wrap_class = mocker.patch("txsocksx.tls.TLSWrapClientEndpoint")
    tls_wrape = tls_wrap_class.return_value = mock.MagicMock()
    
    mtcpe_class = mocker.patch("twisted.internet.endpoints.TCP4ClientEndpoint")
    mtcpe_class.return_value = mtcpe = mock.MagicMock()

    socks_class = mocker.patch("txsocksx.client.SOCKS5ClientEndpoint")
    socks_class.return_value = sockse = mock.MagicMock()

    server_protocol = gen_server_protocol()
    server_protocol._client_factory = mock.MagicMock() # We already tested that this gets set up correctly

    req = http.Request("GET / HTTP/1.1\r\n\r\n")
    req.host = 'Foo.Bar.Brazzers'
    req.port = 80085
    req.is_ssl = True
    server_protocol._request_obj = req

    yield server_protocol._make_remote_connection(req)
    sargs, skwargs =  socks_class.call_args
    targs, tkwargs =  mtcpe_class.call_args
    assert targs[1] == '12345'
    assert targs[2] == 5555
    assert sargs[0] == 'Foo.Bar.Brazzers'
    assert sargs[1] == 80085
    assert sargs[2] == mtcpe
    assert skwargs == {'methods': {'login': ('foo','password'), 'anonymous': ()}}
    assert not sockse.called
    tls_wrape.connect.assert_called_once_with(server_protocol._client_factory)

    
########################
### Proxy Client Factory

@pytest.inlineCallbacks
def test_proxy_client_factory_prepare_reqs_simple(mocker, freeze):
    import datetime
    freeze.freeze(datetime.datetime(2015, 1, 1, 3, 30, 15, 50))

    req = http.Request('GET / HTTP/1.1\r\n\r\n')

    rsave = mocker.patch.object(pappyproxy.http.Request, 'async_deep_save', autospec=True, side_effect=mock_req_async_save)
    rsave.return_value = mock_deferred()
    mocker.patch('pappyproxy.context.in_scope').return_value = True
    mocker.patch('pappyproxy.macros.mangle_request').return_value = mock_deferred((req, False))

    cf = ProxyClientFactory(req,
                            save_all=False,
                            stream_response=False,
                            return_transport=None)
    yield cf.prepare_request()
    assert req.time_start == datetime.datetime(2015, 1, 1, 3, 30, 15, 50)
    assert req.reqid is None
    assert not rsave.called
    assert len(rsave.mock_calls) == 0

@pytest.inlineCallbacks
def test_proxy_client_factory_prepare_reqs_360_noscope(mocker, freeze):
    import datetime
    freeze.freeze(datetime.datetime(2015, 1, 1, 3, 30, 15, 50))

    req = http.Request('GET / HTTP/1.1\r\n\r\n')

    rsave = mocker.patch('pappyproxy.http.Request.async_deep_save')
    rsave.return_value = mock_deferred()
    mocker.patch('pappyproxy.context.in_scope').return_value = False
    mocker.patch('pappyproxy.macros.mangle_request', new=func_deleted)

    cf = ProxyClientFactory(req,
                            save_all=True,
                            stream_response=False,
                            return_transport=None)
    yield cf.prepare_request()
    assert req.time_start == None
    assert req.reqid is None
    assert not rsave.called
    assert len(rsave.mock_calls) == 0

@pytest.inlineCallbacks
def test_proxy_client_factory_prepare_reqs_save(mocker, freeze):
    freeze.freeze(datetime.datetime(2015, 1, 1, 3, 30, 15, 50))

    req = http.Request('GET / HTTP/1.1\r\n\r\n')

    rsave = mocker.patch.object(pappyproxy.http.Request, 'async_deep_save', autospec=True, side_effect=mock_req_async_save)
    mocker.patch('pappyproxy.context.in_scope').return_value = True
    mocker.patch('pappyproxy.macros.mangle_request').return_value = mock_deferred((req, False))

    cf = ProxyClientFactory(req,
                            save_all=True,
                            stream_response=False,
                            return_transport=None)
    yield cf.prepare_request()
    assert req.time_start == datetime.datetime(2015, 1, 1, 3, 30, 15, 50)
    assert req.reqid is not None
    assert rsave.called
    assert len(rsave.mock_calls) == 1

@pytest.inlineCallbacks
def test_proxy_client_factory_prepare_reqs_360_noscope_save(mocker, freeze):
    freeze.freeze(datetime.datetime(2015, 1, 1, 3, 30, 15, 50))

    req = http.Request('GET / HTTP/1.1\r\n\r\n')
    mangreq = http.Request('BOOO / HTTP/1.1\r\n\r\n')

    rsave = mocker.patch.object(pappyproxy.http.Request, 'async_deep_save', autospec=True, side_effect=mock_req_async_save)
    mocker.patch('pappyproxy.context.in_scope').return_value = False
    mocker.patch('pappyproxy.macros.mangle_request', side_effect=func_deleted)

    cf = ProxyClientFactory(req,
                            save_all=True,
                            stream_response=False,
                            return_transport=None)
    yield cf.prepare_request()
    assert req.time_start == None
    assert req.reqid is None
    assert not rsave.called
    assert len(rsave.mock_calls) == 0

@pytest.inlineCallbacks
def test_proxy_client_factory_prepare_mangle_req(mocker, freeze):

    freeze.freeze(datetime.datetime(2015, 1, 1, 3, 30, 15, 50))

    req = http.Request('GET / HTTP/1.1\r\n\r\n')
    mangreq = http.Request('BOOO / HTTP/1.1\r\n\r\n')

    def inc_day_mangle(x, y):
        freeze.delta(days=1)
        return mock_deferred((mangreq, True))

    rsave = mocker.patch.object(pappyproxy.http.Request, 'async_deep_save', autospec=True, side_effect=mock_req_async_save)
    mocker.patch('pappyproxy.context.in_scope').return_value = True
    mocker.patch('pappyproxy.macros.mangle_request', side_effect=inc_day_mangle)

    cf = ProxyClientFactory(req,
                            save_all=True,
                            stream_response=False,
                            return_transport=None)
    yield cf.prepare_request()

    assert cf.request == mangreq
    assert req.time_start == datetime.datetime(2015, 1, 1, 3, 30, 15, 50)
    assert cf.request.time_start == datetime.datetime(2015, 1, 2, 3, 30, 15, 50)
    assert cf.request.reqid is not None
    assert len(rsave.mock_calls) == 2

@pytest.inlineCallbacks
def test_proxy_client_factory_prepare_mangle_req_drop(mocker, freeze):

    freeze.freeze(datetime.datetime(2015, 1, 1, 3, 30, 15, 50))

    def inc_day_mangle(x, y):
        freeze.delta(days=1)
        return mock_deferred((None, True))

    req = http.Request('GET / HTTP/1.1\r\n\r\n')

    rsave = mocker.patch.object(pappyproxy.http.Request, 'async_deep_save', autospec=True, side_effect=mock_req_async_save)
    mocker.patch('pappyproxy.context.in_scope').return_value = True
    mocker.patch('pappyproxy.macros.mangle_request', side_effect=inc_day_mangle)

    cf = ProxyClientFactory(req,
                            save_all=True,
                            stream_response=False,
                            return_transport=None)
    yield cf.prepare_request()

    assert cf.request is None
    assert req.time_start == datetime.datetime(2015, 1, 1, 3, 30, 15, 50)
    assert len(rsave.mock_calls) == 1

@pytest.inlineCallbacks
def test_proxy_client_factory_prepare_mangle_req(mocker, freeze):

    freeze.freeze(datetime.datetime(2015, 1, 1, 3, 30, 15, 50))

    req = http.Request('GET / HTTP/1.1\r\n\r\n')
    mangreq = http.Request('BOOO / HTTP/1.1\r\n\r\n')

    def inc_day_mangle(x, y):
        freeze.delta(days=1)
        return mock_deferred((mangreq, True))

    rsave = mocker.patch.object(pappyproxy.http.Request, 'async_deep_save', autospec=True, side_effect=mock_req_async_save)
    mocker.patch('pappyproxy.context.in_scope').return_value = True
    mocker.patch('pappyproxy.macros.mangle_request', side_effect=inc_day_mangle)

    cf = ProxyClientFactory(req,
                            save_all=True,
                            stream_response=False,
                            return_transport=None)
    yield cf.prepare_request()

    assert cf.request == mangreq
    assert req.time_start == datetime.datetime(2015, 1, 1, 3, 30, 15, 50)
    assert cf.request.time_start == datetime.datetime(2015, 1, 2, 3, 30, 15, 50)
    assert cf.request.reqid is not None
    assert len(rsave.mock_calls) == 2

### return_request_pair

# @pytest.inlineCallbacks
# def test_proxy_client_factory_prepare_mangle_rsp(mocker, freeze):

#     freeze.freeze(datetime.datetime(2015, 1, 1, 3, 30, 15, 50))
#     rsave = mocker.patch.object(pappyproxy.http.Request, 'async_deep_save', autospec=True, side_effect=mock_req_async_save)
#     mocker.patch('pappyproxy.context.in_scope').return_value = True

#     req = http.Request('GET / HTTP/1.1\r\n\r\n')
#     req.reqid = 1
#     rsp = http.Response('HTTP/1.1 200 OK\r\n\r\n')
#     req.response = rsp

#     mocker.patch('pappyproxy.macros.mangle_response').return_value = (req, False)

#     cf = ProxyClientFactory(req,
#                             save_all=False,
#                             stream_response=False,
#                             return_transport=None)
#     result = yield cf.return_request_pair(req)
#     assert result == req
#     assert req.time_start == datetime.datetime(2015, 1, 1, 3, 30, 15, 50)
#     assert len(rsave.mock_calls) == 0

    
### ProxyClient tests

@pytest.inlineCallbacks
def test_proxy_client_simple(mocker):
    rsave = mocker.patch.object(pappyproxy.http.Request, 'async_deep_save', autospec=True, side_effect=mock_req_async_save)
    req = http.Request('GET / HTTP/1.1\r\n\r\n')
    client = gen_client_protocol(req, stream_response=False)
    assert client.transport.value() == 'GET / HTTP/1.1\r\n\r\n'
    client.transport.clear()
    rsp = 'HTTP/1.1 200 OKILE DOKELY\r\n\r\n'
    client.dataReceived(rsp)
    retpair = yield client.data_defer
    assert retpair.response.full_message == rsp
    

@pytest.inlineCallbacks
def test_proxy_client_stream(mocker):
    rsave = mocker.patch.object(pappyproxy.http.Request, 'async_deep_save', autospec=True, side_effect=mock_req_async_save)
    req = http.Request('GET / HTTP/1.1\r\n\r\n')
    client = gen_client_protocol(req, stream_response=True)
    client.transport.clear()
    client.dataReceived('HTTP/1.1 404 GET FUCKE')
    assert client.factory.return_transport.value() == 'HTTP/1.1 404 GET FUCKE'
    client.factory.return_transport.clear()
    client.dataReceived('D ASSHOLE\r\nContent-Length: 4\r\n\r\nABCD')
    assert client.factory.return_transport.value() == 'D ASSHOLE\r\nContent-Length: 4\r\n\r\nABCD'
    retpair = yield client.data_defer
    assert retpair.response.full_message == 'HTTP/1.1 404 GET FUCKED ASSHOLE\r\nContent-Length: 4\r\n\r\nABCD'


@pytest.inlineCallbacks
def test_proxy_client_nostream(mocker):
    rsave = mocker.patch.object(pappyproxy.http.Request, 'async_deep_save', autospec=True, side_effect=mock_req_async_save)
    req = http.Request('GET / HTTP/1.1\r\n\r\n')
    client = gen_client_protocol(req, stream_response=False)
    client.transport.clear()
    client.dataReceived('HTTP/1.1 404 GET FUCKE')
    assert client.factory.return_transport.value() == ''
    client.factory.return_transport.clear()
    client.dataReceived('D ASSHOLE\r\nContent-Length: 4\r\n\r\nABCD')
    assert client.factory.return_transport.value() == ''
    retpair = yield client.data_defer
    assert retpair.response.full_message == 'HTTP/1.1 404 GET FUCKED ASSHOLE\r\nContent-Length: 4\r\n\r\nABCD'

