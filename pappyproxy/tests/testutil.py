import __builtin__
import mock
import pytest
import StringIO
from twisted.internet import defer
from twisted.test.proto_helpers import StringTransport
from pappyproxy import http

next_mock_id = 0

class ClassDeleted():
    pass

class TLSStringTransport(StringTransport):

    def startTLS(self, context, factory):
        pass

def func_deleted(*args, **kwargs):
    raise NotImplementedError()

def func_ignored(*args, **kwargs):
    pass

def func_ignored_deferred(*args, **kwargs):
    return mock_deferred(None)

def mock_deferred(value=None):
    # Generates a function that can be used to make a deferred that can be used
    # to mock out deferred-returning responses
    def g(data):
        return value
    d = defer.Deferred()
    d.addCallback(g)
    d.callback(None)
    return d

@pytest.fixture(autouse=True)
def no_tcp(mocker):
    # Don't make tcp connections
    mocker.patch("twisted.internet.reactor.connectTCP", new=func_deleted)
    mocker.patch("twisted.internet.reactor.connectSSL", new=func_deleted)
    mocker.patch("twisted.internet.endpoints.SSL4ClientEndpoint", new=func_deleted)
    mocker.patch("twisted.internet.endpoints.TCP4ClientEndpoint", new=func_deleted)
    mocker.patch("txsocksx.client.SOCKS5ClientEndpoint", new=func_deleted)
    mocker.patch("txsocksx.tls.TLSWrapClientEndpoint", new=func_deleted)

@pytest.fixture
def ignore_tcp(mocker):
    # Don't make tcp connections
    mocker.patch("twisted.internet.reactor.connectTCP", new=func_ignored)
    mocker.patch("twisted.internet.reactor.connectSSL", new=func_ignored)

@pytest.fixture(autouse=True)
def no_database(mocker):
    # Don't make database queries
    mocker.patch("twisted.enterprise.adbapi.ConnectionPool",
                 new=ClassDeleted)
    
def fake_save_request(r):
    global next_mock_id
    r.reqid = next_mock_id
    next_mock_id += 1
    return mock_deferred(None)

def fake_save_response(r):
    global next_mock_id
    r.rspid = next_mock_id
    next_mock_id += 1
    return mock_deferred(None)

@pytest.fixture
def fake_saving(mocker):
    mocker.patch("pappyproxy.http.Request.async_save", new=fake_save_request)
    mocker.patch("pappyproxy.http.Response.async_save", new=fake_save_response)

@pytest.fixture
def mock_deep_save(mocker, fake_saving):
    new_deep_save = mock.MagicMock()
    new_deep_save.return_value = mock_deferred(None)
    mocker.patch("pappyproxy.http.Request.async_deep_save", new=new_deep_save)
    return new_deep_save

def print_fuck(*args, **kwargs):
    print 'fuck'

@pytest.fixture
def freeze(monkeypatch):
    """ Now() manager patches datetime return a fixed, settable, value
        (freezes time)
    stolen from http://stackoverflow.com/a/28073449
    """
    import datetime
    original = datetime.datetime

    class FreezeMeta(type):
        def __instancecheck__(self, instance):
            if type(instance) == original or type(instance) == Freeze:
                return True

    class Freeze(datetime.datetime):
        __metaclass__ = FreezeMeta

        @classmethod
        def freeze(cls, val, utcval=None):
            cls.utcfrozen = utcval
            cls.frozen = val

        @classmethod
        def now(cls):
            return cls.frozen

        @classmethod
        def utcnow(cls):
            # added since requests use utcnow
            return cls.utcfrozen or cls.frozen

        @classmethod
        def delta(cls, timedelta=None, **kwargs):
            """ Moves time fwd/bwd by the delta"""
            from datetime import timedelta as td
            if not timedelta:
                timedelta = td(**kwargs)
            cls.frozen += timedelta

    monkeypatch.setattr(datetime, 'datetime', Freeze)
    Freeze.freeze(original.now())
    return Freeze

def mock_int_macro(modified_req=None, modified_rsp=None,
                   drop_req=False, drop_rsp=False):
    macro = mock.MagicMock()
    if modified_req or drop_req:
        macro.async_req = True
        macro.intercept_requests = True
        if drop_req:
            newreq = None
        else:
            newreq = http.Request(modified_req)
        macro.async_mangle_request.return_value = mock_deferred(newreq)
    else:
        macro.intercept_requests = False

    if modified_rsp or drop_rsp:
        macro.async_rsp = True
        macro.intercept_responses = True
        if drop_rsp:
            newrsp = None
        else:
            newrsp = http.Response(modified_rsp)
        macro.async_mangle_response.return_value = mock_deferred(newrsp)
    else:
        macro.intercept_responses = False
    return macro
