import pytest
from twisted.internet import defer

class ClassDeleted():
    pass

def func_deleted(*args, **kwargs):
    raise NotImplementedError()

def func_ignored(*args, **kwargs):
    pass

@pytest.fixture
def mock_deferred():
    # Generates a function that can be used to make a deferred that can be used
    # to mock out deferred-returning responses
    def f(value):
        def g(data):
            return value
        d = defer.Deferred()
        d.addCallback(g)
        d.callback(None)
        return d
    return f

@pytest.fixture(autouse=True)
def no_tcp(monkeypatch):
    # Don't make tcp connections
    monkeypatch.setattr("twisted.internet.reactor.connectTCP", func_deleted)
    monkeypatch.setattr("twisted.internet.reactor.connectSSL", func_deleted)

@pytest.fixture
def ignore_tcp(monkeypatch):
    # Don't make tcp connections
    monkeypatch.setattr("twisted.internet.reactor.connectTCP", func_ignored)
    monkeypatch.setattr("twisted.internet.reactor.connectSSL", func_ignored)

@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    # Don't make database queries
    monkeypatch.setattr("twisted.enterprise.adbapi.ConnectionPool",
                        ClassDeleted)
