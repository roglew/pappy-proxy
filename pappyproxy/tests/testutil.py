import __builtin__
import mock
import pytest
import StringIO
from twisted.internet import defer

next_mock_id = 0

class ClassDeleted():
    pass

def func_deleted(*args, **kwargs):
    raise NotImplementedError()

def func_ignored(*args, **kwargs):
    pass

def func_ignored_deferred(*args, **kwargs):
    return mock_deferred(None)

def mock_deferred(value):
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

