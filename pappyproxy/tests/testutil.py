import __builtin__
import mock
import pytest
import StringIO
from twisted.internet import defer
from twisted.test.proto_helpers import StringTransport
from pappyproxy import http, config, pappy

next_mock_id = 0

class ClassDeleted():
    pass

class TLSStringTransport(StringTransport):
    startTLS = mock.MagicMock()
    
class PappySession(object):
    
    def setup():
        """
        Sets up a console session with a connection to a temporary datafile
        """
        pass
    
    def cleanup():
        """
        Closes connections, deletes temporary datafile
        """
        pass

    def run_command(command):
        """
        Runs the command then returns the non-colorized output
        """
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
    #mocker.patch("twisted.internet.reactor.connectTCP", new=func_deleted)
    #mocker.patch("twisted.internet.reactor.connectSSL", new=func_deleted)
    #mocker.patch("twisted.internet.endpoints.SSL4ClientEndpoint", new=func_deleted)
    #mocker.patch("twisted.internet.endpoints.TCP4ClientEndpoint", new=func_deleted)
    #mocker.patch("txsocksx.client.SOCKS5ClientEndpoint", new=func_deleted)
    #mocker.patch("txsocksx.tls.TLSWrapClientEndpoint", new=func_deleted)
    pass

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

def mock_config(mocker, http_config=None, socks_config=None):
    # Mock config
    mock_config = config.PappyConfig()
    mock_config.socks_proxy = socks_config
    mock_config.http_proxy = http_config
    mock_session = pappy.PappySession(mock_config)
    mocker.patch.object(pappy, 'session', new=mock_session)
    mocker.patch("pappyproxy.proxy.load_certs_from_dir", new=mock_generate_cert)
    
