import pytest

from proxy import ProxyClient, ProxyClientFactory, ProxyServer
from testutil import mock_deferred
from twisted.internet.protocol import ServerFactory
from twisted.test import proto_helpers
from twisted.internet import defer

####################
## Fixtures

@pytest.fixture
def proxyserver():
    factory = ServerFactory()
    factory.protocol = ProxyServer
    protocol = factory.buildProtocol(('127.0.0.1', 0))
    transport = proto_helpers.StringTransport()
    protocol.makeConnection(transport)
    return (protocol, transport)

####################
## Basic tests

def test_proxy_server_fixture(proxyserver):
    prot = proxyserver[0]
    tr = proxyserver[1]
    prot.transport.write('hello')
    print tr.value()
    assert tr.value() == 'hello'
    
@pytest.inlineCallbacks
def test_mock_deferreds(mock_deferred):
    d = mock_deferred('Hello!')
    r = yield d
    assert r == 'Hello!'
    
