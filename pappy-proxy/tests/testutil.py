import pytest
from twisted.internet import defer

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
