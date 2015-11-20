import pytest
import mangle
import twisted.internet
import twisted.test

from proxy import ProxyClient, ProxyClientFactory, ProxyServer
from testutil import mock_deferred, func_deleted, no_tcp, ignore_tcp, no_database, func_ignored
from twisted.internet.protocol import ServerFactory
from twisted.test.iosim import FakeTransport
from twisted.internet import defer, reactor

####################
## Fixtures

@pytest.fixture
def proxyserver(monkeypatch):
    monkeypatch.setattr("twisted.test.iosim.FakeTransport.startTLS", func_ignored)
    factory = ServerFactory()
    factory.protocol = ProxyServer
    protocol = factory.buildProtocol(('127.0.0.1', 0))
    protocol.makeConnection(FakeTransport(protocol, True))
    return protocol

## Autorun fixtures
    
@pytest.fixture(autouse=True)
def no_mangle(monkeypatch):
    # Don't call anything in mangle.py
    monkeypatch.setattr("mangle.mangle_request", func_deleted)
    monkeypatch.setattr("mangle.mangle_response", func_deleted)

####################
## Unit test tests

def test_proxy_server_fixture(proxyserver):
    proxyserver.transport.write('hello')
    assert proxyserver.transport.getOutBuffer() == 'hello'
    
@pytest.inlineCallbacks
def test_mock_deferreds(mock_deferred):
    d = mock_deferred('Hello!')
    r = yield d
    assert r == 'Hello!'

def test_deleted():
    with pytest.raises(NotImplementedError):
        reactor.connectTCP("www.google.com", "80", ServerFactory)
    
####################
## Proxy Server Tests

def test_proxy_server_connect(proxyserver):
    proxyserver.lineReceived('CONNECT www.dddddd.fff:433 HTTP/1.1')
    proxyserver.lineReceived('')
    assert proxyserver.transport.getOutBuffer() == 'HTTP/1.1 200 Connection established\r\n\r\n'
    #assert starttls got called
