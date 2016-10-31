import mock
import pytest
import twisted.internet.endpoints

from pappyproxy import http
from pappyproxy.proxy import MaybeTLSProtocol, start_maybe_tls, PassthroughProtocolFactory, make_proxied_connection
from testutil import mock_deferred, func_deleted, TLSStringTransport, freeze, mock_int_macro, no_tcp, mock_config
from pappyproxy.util import PappyStringTransport
from twisted.internet import defer, ssl

###############################
## Helper functions and classes

def gen_debug_protocol(mocker):
    def fake_start_tls(transport, context):
        transport.protocol = mock.MagicMock()
    mocker.patch("pappyproxy.util.PappyStringTransport.startTLS", new=fake_start_tls)
    mocker.patch("pappyproxy.proxy.generate_tls_context")

    t = PappyStringTransport()
    def server_data_received(s):
        t.write(s)
    factory = PassthroughProtocolFactory(server_data_received, None, None)
    p = factory.buildProtocol(None)
    p.transport = t
    t.protocol= p
    return p, t

def mock_protocol_proxy(mocker):
    from pappyproxy import proxy
    mock_make_proxied_connection = mocker.patch("pappyproxy.proxy.make_proxied_connection")
    p = proxy.ProtocolProxy()
    p.client_transport = PappyStringTransport()
    p.server_transport = PappyStringTransport()

    client_protocol, _ = gen_debug_protocol(mocker)
    server_protocol, _ = gen_debug_protocol(mocker)

    return p, client_protocol, server_protocol, mock_make_proxied_connection

##########################
## Tests for ProtocolProxy

def test_simple(mocker):
    mock_config(mocker)
    proxy, _, _, _ = mock_protocol_proxy(mocker)
    proxy.send_client_data("foobar")
    assert proxy.client_buffer == "foobar"
    proxy.send_server_data("barfoo")
    assert proxy.server_buffer == "barfoo"

def test_connect(mocker):
    mock_config(mocker)
    proxy, _, _, mock_make_proxied_connection = mock_protocol_proxy(mocker)
    proxy.send_client_data("foobar")
    proxy.send_server_data("barfoo")
    proxy.connect("fakehost", 1337, False)
    assert len(mock_make_proxied_connection.mock_calls) == 1
    callargs = mock_make_proxied_connection.mock_calls[0][1]
    assert callargs[1] == "fakehost"
    assert callargs[2] == 1337
    assert callargs[3] == False
    
def test_send_before_connect(mocker):
    mock_config(mocker)
    proxy, client_protocol, server_protocol, mock_make_proxied_connection = mock_protocol_proxy(mocker)
    proxy.send_client_data("foobar")
    proxy.send_server_data("barfoo")

    proxy.connect("fakehost", 1337, False)

    proxy.client_connection_made(client_protocol)
    assert proxy.client_buffer == ''
    assert client_protocol.transport.pop_value() == 'foobar'

    assert proxy.server_buffer == 'barfoo'

    proxy.server_connection_made(server_protocol)
    assert proxy.server_buffer == ''
    assert server_protocol.transport.pop_value() == 'barfoo'

def test_send_after_connect(mocker):
    mock_config(mocker)
    proxy, client_protocol, server_protocol, mock_make_proxied_connection = mock_protocol_proxy(mocker)

    proxy.connect("fakehost", 1337, False)

    proxy.client_connection_made(client_protocol)
    proxy.send_client_data("foobar")
    assert client_protocol.transport.pop_value() == 'foobar'

    proxy.server_connection_made(server_protocol)
    proxy.send_server_data("barfoo")
    assert server_protocol.transport.pop_value() == 'barfoo'
    
def test_start_tls_before_connect(mocker):
    mock_config(mocker)
    proxy, client_protocol, server_protocol, mock_make_proxied_connection = mock_protocol_proxy(mocker)
    client_protocol.transport.startTLS = mock.MagicMock()
    server_protocol.transport.startTLS = mock.MagicMock()

    server_protocol.transport.startTLS.assert_not_called()
    client_protocol.transport.startTLS.assert_not_called()
    proxy.start_server_tls()
    proxy.start_client_tls("fakehost")

    server_protocol.transport.startTLS.assert_not_called()
    client_protocol.transport.startTLS.assert_not_called()
    proxy.connect("fakehost", 1337, False)
    server_protocol.transport.startTLS.assert_not_called()
    client_protocol.transport.startTLS.assert_not_called()

    proxy.server_connection_made(server_protocol)
    assert len(server_protocol.transport.startTLS.mock_calls) == 1
    client_protocol.transport.startTLS.assert_not_called()

    proxy.client_connection_made(client_protocol)
    assert len(client_protocol.transport.startTLS.mock_calls) == 1

def test_start_tls_after_connect(mocker):
    mock_config(mocker)
    proxy, client_protocol, server_protocol, mock_make_proxied_connection = mock_protocol_proxy(mocker)
    client_protocol.transport.startTLS = mock.MagicMock()
    server_protocol.transport.startTLS = mock.MagicMock()

    server_protocol.transport.startTLS.assert_not_called()
    client_protocol.transport.startTLS.assert_not_called()

    proxy.connect("fakehost", 1337, False)

    server_protocol.transport.startTLS.assert_not_called()
    client_protocol.transport.startTLS.assert_not_called()

    proxy.server_connection_made(server_protocol)
    proxy.start_server_tls()
    assert len(server_protocol.transport.startTLS.mock_calls) == 1

    proxy.client_connection_made(client_protocol)
    proxy.start_client_tls("fakehost")
    assert len(client_protocol.transport.startTLS.mock_calls) == 1

def test_start_maybe_tls_before_connect(mocker):
    mock_config(mocker)
    proxy, client_protocol, server_protocol, mock_make_proxied_connection = mock_protocol_proxy(mocker)
    mock_maybe_tls = mocker.patch("pappyproxy.proxy.start_maybe_tls")
    client_protocol.transport.startTLS = mock.MagicMock()
    server_protocol.transport.startTLS = mock.MagicMock()

    proxy.start_client_maybe_tls("fakehost")

    client_protocol.transport.startTLS.assert_not_called()
    proxy.connect("fakehost", 1337, False)
    client_protocol.transport.startTLS.assert_not_called()

    proxy.client_connection_made(client_protocol)
    client_protocol.transport.startTLS.assert_not_called()
    assert len(mock_maybe_tls.mock_calls) == 1

    callargs = mock_maybe_tls.mock_calls[0][2]
    assert callargs['tls_host'] == 'fakehost'
    assert callargs['start_tls_callback'] == proxy.start_server_tls

def test_start_maybe_tls_before_connect(mocker):
    mock_config(mocker)
    proxy, client_protocol, server_protocol, mock_make_proxied_connection = mock_protocol_proxy(mocker)
    mock_maybe_tls = mocker.patch("pappyproxy.proxy.start_maybe_tls")
    client_protocol.transport.startTLS = mock.MagicMock()
    server_protocol.transport.startTLS = mock.MagicMock()


    client_protocol.transport.startTLS.assert_not_called()
    proxy.connect("fakehost", 1337, False)
    client_protocol.transport.startTLS.assert_not_called()

    proxy.client_connection_made(client_protocol)
    proxy.start_client_maybe_tls("fakehost")
    client_protocol.transport.startTLS.assert_not_called()
    assert len(mock_maybe_tls.mock_calls) == 1

    callargs = mock_maybe_tls.mock_calls[0][2]
    assert callargs['tls_host'] == 'fakehost'
    assert callargs['start_tls_callback'] == proxy.start_server_tls
    

#############################
## Tests for MaybeTLSProtocol
def test_maybe_tls_plaintext(mocker):
    mock_config(mocker)
    tls_callback = mock.MagicMock()
    p, t = gen_debug_protocol(mocker)
    start_maybe_tls(p.transport, 'www.foo.faketld')
    p.dataReceived("Hello world!")
    assert p.transport.pop_value() == "Hello world!"

def test_maybe_tls_use_tls(mocker):
    mock_config(mocker)
    tls_callback = mock.MagicMock()
    p, t = gen_debug_protocol(mocker)
    start_maybe_tls(p.transport, 'www.foo.faketld')
    maybe_tls_prot = t.protocol
    assert isinstance(maybe_tls_prot, MaybeTLSProtocol)
    assert maybe_tls_prot.state == MaybeTLSProtocol.STATE_DECIDING
    t.protocol.dataReceived("\x16")
    assert not isinstance(t.protocol, MaybeTLSProtocol)
    assert maybe_tls_prot.state == MaybeTLSProtocol.STATE_PASSTHROUGH

####################################
## Tests for make_proxied_connection
def test_mpc_simple(mocker):
    mock_config(mocker)
    endpoint_instance = mock.MagicMock()
    endpoint = mocker.patch('twisted.internet.endpoints.TCP4ClientEndpoint', return_value=endpoint_instance)

    make_proxied_connection('fakefactory', 'fakehost', 1337, False)

    endpointcalls = endpoint.mock_calls[0]
    assert endpointcalls[1][1] == 'fakehost'
    assert endpointcalls[1][2] == 1337

    connectcall = endpoint_instance.connect
    assert len(connectcall.mock_calls) == 1

def test_mpc_ssl(mocker):
    mock_config(mocker)
    endpoint_instance = mock.MagicMock()
    endpoint = mocker.patch('twisted.internet.endpoints.SSL4ClientEndpoint', return_value=endpoint_instance)

    make_proxied_connection('fakefactory', 'fakehost', 1337, True)

    endpointcalls = endpoint.mock_calls[0]
    assert endpointcalls[1][1] == 'fakehost'
    assert endpointcalls[1][2] == 1337
    assert isinstance(endpointcalls[1][3], ssl.ClientContextFactory)

    connectcall = endpoint_instance.connect
    assert len(connectcall.mock_calls) == 1

def test_mpc_socks(mocker):
    mock_config(mocker)
    tcp_endpoint_instance = mock.MagicMock()
    socks_endpoint_instance = mock.MagicMock()
    tcp_endpoint = mocker.patch('twisted.internet.endpoints.TCP4ClientEndpoint', return_value=tcp_endpoint_instance)
    socks_endpoint = mocker.patch('txsocksx.client.SOCKS5ClientEndpoint', return_value=socks_endpoint_instance)

    target_host = 'fakehost'
    target_port = 1337

    socks_host = 'fakesockshost'
    socks_port = 1447
    socks_config = {'host':socks_host, 'port':socks_port}

    make_proxied_connection('fakefactory', target_host, target_port, False, socks_config=socks_config)

    tcp_ep_calls = tcp_endpoint.mock_calls[0]
    assert tcp_ep_calls[1][1] == socks_host
    assert tcp_ep_calls[1][2] == socks_port

    socks_ep_calls = socks_endpoint.mock_calls[0]
    assert socks_ep_calls[1][0] == target_host
    assert socks_ep_calls[1][1] == target_port
    assert socks_ep_calls[1][2] is tcp_endpoint_instance
    assert socks_ep_calls[2]['methods'] == {'anonymous': ()}

    connectcall = socks_endpoint_instance.connect
    assert len(connectcall.mock_calls) == 1

def test_mpc_socks_creds(mocker):
    mock_config(mocker)
    tcp_endpoint_instance = mock.MagicMock()
    socks_endpoint_instance = mock.MagicMock()
    tcp_endpoint = mocker.patch('twisted.internet.endpoints.TCP4ClientEndpoint', return_value=tcp_endpoint_instance)
    socks_endpoint = mocker.patch('txsocksx.client.SOCKS5ClientEndpoint', return_value=socks_endpoint_instance)

    target_host = 'fakehost'
    target_port = 1337

    socks_host = 'fakesockshost'
    socks_port = 1447
    socks_user = 'username'
    socks_password = 'password'
    socks_config = {'host':socks_host, 'port':socks_port,
                    'username':socks_user, 'password':socks_password}

    make_proxied_connection('fakefactory', target_host, target_port, False, socks_config=socks_config)

    tcp_ep_calls = tcp_endpoint.mock_calls[0]
    assert tcp_ep_calls[1][1] == socks_host
    assert tcp_ep_calls[1][2] == socks_port

    socks_ep_calls = socks_endpoint.mock_calls[0]
    assert socks_ep_calls[1][0] == target_host
    assert socks_ep_calls[1][1] == target_port
    assert socks_ep_calls[1][2] is tcp_endpoint_instance
    assert socks_ep_calls[2]['methods'] == {'login': (socks_user, socks_password), 'anonymous': ()}

    connectcall = socks_endpoint_instance.connect
    assert len(connectcall.mock_calls) == 1

def test_mpc_socks_ssl(mocker):
    mock_config(mocker)
    tcp_endpoint_instance = mock.MagicMock()
    socks_endpoint_instance = mock.MagicMock()
    wrapper_instance = mock.MagicMock()
    tcp_endpoint = mocker.patch('twisted.internet.endpoints.TCP4ClientEndpoint', return_value=tcp_endpoint_instance)
    socks_endpoint = mocker.patch('txsocksx.client.SOCKS5ClientEndpoint', return_value=socks_endpoint_instance)
    wrapper_endpoint = mocker.patch('txsocksx.tls.TLSWrapClientEndpoint', return_value=wrapper_instance)

    target_host = 'fakehost'
    target_port = 1337

    socks_host = 'fakesockshost'
    socks_port = 1447
    socks_config = {'host':socks_host, 'port':socks_port}

    make_proxied_connection('fakefactory', target_host, target_port, True, socks_config=socks_config)

    tcp_ep_calls = tcp_endpoint.mock_calls[0]
    assert tcp_ep_calls[1][1] == socks_host
    assert tcp_ep_calls[1][2] == socks_port

    socks_ep_calls = socks_endpoint.mock_calls[0]
    assert socks_ep_calls[1][0] == target_host
    assert socks_ep_calls[1][1] == target_port
    assert socks_ep_calls[1][2] is tcp_endpoint_instance
    assert socks_ep_calls[2]['methods'] == {'anonymous': ()}

    wrapper_calls = wrapper_endpoint.mock_calls[0]
    assert isinstance(wrapper_calls[1][0], ssl.ClientContextFactory)
    assert wrapper_calls[1][1] is socks_endpoint_instance

    connectcall = wrapper_instance.connect
    assert len(connectcall.mock_calls) == 1

def test_mpc_socks_ssl_creds(mocker):
    mock_config(mocker)
    tcp_endpoint_instance = mock.MagicMock()
    socks_endpoint_instance = mock.MagicMock()
    wrapper_instance = mock.MagicMock()
    tcp_endpoint = mocker.patch('twisted.internet.endpoints.TCP4ClientEndpoint', return_value=tcp_endpoint_instance)
    socks_endpoint = mocker.patch('txsocksx.client.SOCKS5ClientEndpoint', return_value=socks_endpoint_instance)
    wrapper_endpoint = mocker.patch('txsocksx.tls.TLSWrapClientEndpoint', return_value=wrapper_instance)

    target_host = 'fakehost'
    target_port = 1337

    socks_host = 'fakesockshost'
    socks_port = 1447
    socks_user = 'username'
    socks_password = 'password'
    socks_config = {'host':socks_host, 'port':socks_port,
                    'username':socks_user, 'password':socks_password}

    make_proxied_connection('fakefactory', target_host, target_port, True, socks_config=socks_config)

    tcp_ep_calls = tcp_endpoint.mock_calls[0]
    assert tcp_ep_calls[1][1] == socks_host
    assert tcp_ep_calls[1][2] == socks_port

    socks_ep_calls = socks_endpoint.mock_calls[0]
    assert socks_ep_calls[1][0] == target_host
    assert socks_ep_calls[1][1] == target_port
    assert socks_ep_calls[1][2] is tcp_endpoint_instance
    assert socks_ep_calls[2]['methods'] == {'login': (socks_user, socks_password), 'anonymous': ()}

    wrapper_calls = wrapper_endpoint.mock_calls[0]
    assert isinstance(wrapper_calls[1][0], ssl.ClientContextFactory)
    assert wrapper_calls[1][1] is socks_endpoint_instance

    connectcall = wrapper_instance.connect
    assert len(connectcall.mock_calls) == 1
