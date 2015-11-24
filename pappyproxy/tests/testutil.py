import pytest
from twisted.internet import defer

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
