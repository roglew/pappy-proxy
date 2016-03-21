import collections
import copy
import datetime
import os
import random

from OpenSSL import SSL
from OpenSSL import crypto
from pappyproxy import context
from pappyproxy import http
from pappyproxy import macros
from pappyproxy.util import PappyException, printable_data
from twisted.internet import defer
from twisted.internet import reactor, ssl
from twisted.internet.protocol import ClientFactory, ServerFactory
from twisted.protocols.basic import LineReceiver

next_connection_id = 1

cached_certs = {}

def get_next_connection_id():
    global next_connection_id
    ret_id = next_connection_id
    next_connection_id += 1
    return ret_id

def add_intercepting_macro(key, macro, int_macro_dict):
    if key in int_macro_dict:
        raise PappyException('Macro with key %s already exists' % key)
    int_macro_dict[key] = macro

def remove_intercepting_macro(key, int_macro_dict):
    if not key in int_macro_dict:
        raise PappyException('Macro with key %s not currently running' % key)
    del int_macro_dict[key]

def log(message, id=None, symbol='*', verbosity_level=1):
    from pappyproxy.pappy import session

    if session.config.debug_to_file or session.config.debug_verbosity > 0:
        if session.config.debug_to_file and not os.path.exists(session.config.debug_dir):
            os.makedirs(session.config.debug_dir)
        if id:
            debug_str = '[%s](%d) %s' % (symbol, id, message)
            if session.config.debug_to_file:
                with open(session.config.debug_dir+'/connection_%d.log' % id, 'a') as f:
                    f.write(debug_str+'\n')
        else:
            debug_str = '[%s] %s' % (symbol, message)
            if session.config.debug_to_file:
                with open(session.config.debug_dir+'/debug.log', 'a') as f:
                    f.write(debug_str+'\n')
        if session.config.debug_verbosity >= verbosity_level:
            print debug_str
    
def log_request(request, id=None, symbol='*', verbosity_level=3):
    from pappyproxy.pappy import session

    if session.config.debug_to_file or session.config.debug_verbosity > 0:
        r_split = request.split('\r\n')
        for l in r_split:
            log(l, id, symbol, verbosity_level)
            
def get_endpoint(target_host, target_port, target_ssl, socks_config=None, use_http_proxy=False, debugid=None):
    # Imports go here to allow mocking for tests
    from twisted.internet.endpoints import SSL4ClientEndpoint, TCP4ClientEndpoint
    from txsocksx.client import SOCKS5ClientEndpoint
    from txsocksx.tls import TLSWrapClientEndpoint
    from pappyproxy.pappy import session

    log("Getting endpoint for host '%s' on port %d ssl=%s, socks_config=%s, use_http_proxy=%s" % (target_host, target_port, target_ssl, str(socks_config), use_http_proxy), id=debugid, verbosity_level=3)

    if session.config.http_proxy and use_http_proxy:
        target_host = session.config.http_proxy['host']
        target_port = session.config.http_proxy['port']
        target_ssl = False # We turn on ssl after CONNECT request if needed
        log("Connecting to http proxy at %s:%d" % (target_host, target_port), id=debugid, verbosity_level=3)

    if socks_config is not None:
        sock_host = socks_config['host']
        sock_port = int(socks_config['port'])
        methods = {'anonymous': ()}
        if 'username' in socks_config and 'password' in socks_config:
            methods['login'] = (socks_config['username'], socks_config['password'])
        tcp_endpoint = TCP4ClientEndpoint(reactor, sock_host, sock_port)
        socks_endpoint = SOCKS5ClientEndpoint(target_host, target_port, tcp_endpoint, methods=methods)
        if target_ssl:
            endpoint = TLSWrapClientEndpoint(ClientTLSContext(), socks_endpoint)
        else:
            endpoint = socks_endpoint
    else:
        if target_ssl:
            endpoint = SSL4ClientEndpoint(reactor, target_host, target_port,
                                          ClientTLSContext())
        else:
            endpoint = TCP4ClientEndpoint(reactor, target_host, target_port)
    return endpoint
        
class ClientTLSContext(ssl.ClientContextFactory):
    isClient = 1
    def getContext(self):
        return SSL.Context(SSL.TLSv1_METHOD)


class ProxyClient(LineReceiver):

    def __init__(self, request):
        self.factory = None
        self._response_sent = False
        self._sent = False
        self.request = request
        self.data_defer = defer.Deferred()
        self.completed = False
        self.stream_response = True # used so child classes can temporarily turn off response streaming

        self._response_obj = http.Response()

    def log(self, message, symbol='*', verbosity_level=1):
        log(message, id=self.factory.connection_id, symbol=symbol, verbosity_level=verbosity_level)

    def lineReceived(self, *args, **kwargs):
        line = args[0]
        if line is None:
            line = ''
        self.log(line, symbol='r<', verbosity_level=3)
        self._response_obj.add_line(line)
        if self._response_obj.headers_complete:
            self.setRawMode()

    def rawDataReceived(self, *args, **kwargs):
        from pappyproxy.pappy import session

        data = args[0]
        self.log('Returning data back through stream')
        if not self._response_obj.complete:
            if data:
                if session.config.debug_to_file or session.config.debug_verbosity > 0:
                    s = printable_data(data)
                    dlines = s.split('\n')
                    for l in dlines:
                        self.log(l, symbol='<rd', verbosity_level=3)
            self._response_obj.add_data(data)

    def dataReceived(self, data):
        if self.factory.stream_response and self.stream_response:
            self.factory.return_transport.write(data)
        LineReceiver.dataReceived(self, data)
        if not self.completed:
            if self._response_obj.complete:
                self.completed = True
                self.handle_response_end()
        
    def connectionMade(self):
        self.log("Connection made, sending request", verbosity_level=3)
        lines = self.request.full_request.splitlines()
        for l in lines:
            self.log(l, symbol='>r', verbosity_level=3)
        self.transport.write(self.request.full_request)
        
    def handle_response_end(self, *args, **kwargs):
        self.log("Remote response finished, returning data to original stream")
        self.request.response = self._response_obj
        self.log('Response ended, losing connection')
        self.transport.loseConnection()
        assert self._response_obj.full_response
        self.data_defer.callback(self.request)

    def clientConnectionFailed(self, connector, reason):
        self.log("Connection with remote server failed: %s" % reason)

    def clientConnectionLost(self, connector, reason):
        self.log("Connection with remote server lost: %s" % reason)

class UpstreamHTTPProxyClient(ProxyClient):

    def __init__(self, request):
        ProxyClient.__init__(self, request)
        self.connect_response = False
        self.proxy_connected = False
        self.stream_response = False
        self.creds = None

    def write_proxied_request(self, request):
        """
        Takes an unencrypted request and sends it to the proxy server to be
        forwarded.
        """
        sendreq = request.copy()
        sendreq.path_type = http.PATH_ABSOLUTE
        if self.creds is not None:
            sendreq.proxy_creds = self.creds
        lines = sendreq.full_request.splitlines()
        for l in lines:
            self.log(l, symbol='>rp', verbosity_level=3)
        self.transport.write(sendreq.full_message)

    def connectionMade(self):
        self.log("Connection made to http proxy", verbosity_level=3)
        if not self.proxy_connected:
            if self.request.is_ssl:
                connreq = self.request.connect_request
                self.connect_response = True
                if self.creds is not None:
                    connreq.proxy_creds = self.creds
                lines = connreq.full_message.splitlines()
                for l in lines:
                    self.log(l, symbol='>p', verbosity_level=3)
                self.transport.write(connreq.full_message)
            else:
                self.proxy_connected = True
                self.stream_response = True
                lines = self.request.full_message.splitlines()
                for l in lines:
                    self.log(l, symbol='>p', verbosity_level=3)
                self.write_proxied_request(self.request)

    def handle_response_end(self, *args, **kwargs):
        if self._response_obj.response_code == 407:
            print "Incorrect credentials for HTTP proxy. Please check your username and password."
            self.transport.loseConnection()
            return
        if self.proxy_connected:
            self.log("Received request while connected, forwarding to http proxy", verbosity_level=3)
            self.request.response = self._response_obj
            self.transport.loseConnection()
            assert self._response_obj.full_response
            self.data_defer.callback(self.request)
        elif self._response_obj.response_code != 200:
            print "Error establishing connection to proxy"
            self.transport.loseConnection()
            return
        elif self.connect_response:
            self.log("Response to CONNECT request recieved from http proxy", verbosity_level=3)
            self.proxy_connected = True
            self.stream_response = True
            self._response_obj = http.Response()
            self.setLineMode()
            self.completed = False
            self._sent = False

            self.log("Starting TLS", verbosity_level=3)
            self.transport.startTLS(ClientTLSContext())
            self.log("TLS started", verbosity_level=3)
            lines = self.request.full_message.splitlines()
            for l in lines:
                self.log(l, symbol='>rpr', verbosity_level=3)
            self.transport.write(self.request.full_message)

class ProxyClientFactory(ClientFactory):

    def __init__(self, request, save_all=False, stream_response=False,
                 return_transport=None):
        self.request = request
        self.connection_id = -1
        self.data_defer = defer.Deferred()
        self.start_time = datetime.datetime.utcnow()
        self.end_time = None
        self.save_all = save_all
        self.stream_response = stream_response
        self.return_transport = return_transport
        self.intercepting_macros = {}
        self.use_as_proxy = False
        self.sendback_function = None

    def log(self, message, symbol='*', verbosity_level=1):
        log(message, id=self.connection_id, symbol=symbol, verbosity_level=verbosity_level)

    def buildProtocol(self, addr, _do_callback=True):
        from pappyproxy.pappy import session
        # _do_callback is intended to help with testing and should not be modified
        if self.use_as_proxy and context.in_scope(self.request):
            p = UpstreamHTTPProxyClient(self.request)
            if 'username' in session.config.http_proxy and 'password' in session.config.http_proxy:
                username = session.config.http_proxy['username']
                password = session.config.http_proxy['password']
                p.creds = (username, password)
        else:
            p = ProxyClient(self.request)
        p.factory = self
        self.log("Building protocol", verbosity_level=3)
        if _do_callback:
            p.data_defer.addCallback(self.return_request_pair)
        return p

    def clientConnectionFailed(self, connector, reason):
        self.log("Connection failed with remote server: %s" % reason.getErrorMessage())

    def clientConnectionLost(self, connector, reason):
        self.log("Connection lost with remote server: %s" % reason.getErrorMessage())

    @defer.inlineCallbacks
    def prepare_request(self):
        """
        Prepares request for submitting
        
        Saves the associated request with a temporary start time, mangles it, then
        saves the mangled version with an update start time. Also updates flags
        and values needed for submitting the request.
        """
        from pappyproxy.pappy import session

        sendreq = self.request
        if context.in_scope(sendreq):
            mangle_macros = copy.copy(self.intercepting_macros)
            self.request.time_start = datetime.datetime.utcnow()
            if self.save_all:
                if self.stream_response and not mangle_macros:
                    self.request.async_deep_save()
                else:
                    yield self.request.async_deep_save()

            (sendreq, mangled) = yield macros.mangle_request(sendreq, mangle_macros)

            if sendreq and mangled and self.save_all:
                self.start_time = datetime.datetime.utcnow()
                sendreq.time_start = self.start_time
                yield sendreq.async_deep_save()

            if session.config.http_proxy:
                self.use_as_proxy = True
                if (not self.stream_response) and self.sendback_function:
                    self.data_defer.addCallback(self.sendback_function)
        else:
            self.log("Request out of scope, passing along unmangled")
        self.request = sendreq
        defer.returnValue(self.request)

    @defer.inlineCallbacks
    def return_request_pair(self, request):
        """
        If the request is in scope, it saves the completed request,
        sets the start/end time, mangles the response, saves the
        mangled version, then calls back data_defer with the mangled
        request
        """
        from pappyproxy.pappy import session

        self.end_time = datetime.datetime.utcnow()
        if session.config.debug_to_file or session.config.debug_verbosity > 0:
            log_request(printable_data(request.response.full_response), id=self.connection_id, symbol='<m', verbosity_level=3)

        request.time_start = self.start_time
        request.time_end = self.end_time
        if context.in_scope(request):
            mangle_macros = copy.copy(self.intercepting_macros)

            if self.save_all:
                if self.stream_response and not mangle_macros:
                    request.async_deep_save()
                else:
                    yield request.async_deep_save()

            mangled = yield macros.mangle_response(request, mangle_macros)

            if mangled and self.save_all:
                yield request.async_deep_save()

            if request.response and (session.config.debug_to_file or session.config.debug_verbosity > 0):
                log_request(printable_data(request.response.full_response),
                            id=self.connection_id, symbol='<', verbosity_level=3)
        else:
            self.log("Response out of scope, passing along unmangled")
        self.data_defer.callback(request)
        defer.returnValue(None)

    @defer.inlineCallbacks
    def connect(self):
        from pappyproxy.pappy import session

        yield self.prepare_request()
        if context.in_scope(self.request):
            # Get connection using config
            endpoint = get_endpoint(self.request.host,
                                    self.request.port,
                                    self.request.is_ssl,
                                    socks_config=session.config.socks_proxy,
                                    use_http_proxy=True)
        else:
            # Just forward it normally
            endpoint = get_endpoint(self.request.host,
                                    self.request.port,
                                    self.request.is_ssl)

        # Connect via the endpoint
        self.log("Accessing using endpoint")
        yield endpoint.connect(self)
        self.log("Connected")

class ProxyServerFactory(ServerFactory):

    def __init__(self, save_all=False):
        from pappyproxy.site import PappyWebServer
        
        self.intercepting_macros = collections.OrderedDict()
        self.save_all = save_all
        self.force_ssl = False
        self.web_server = PappyWebServer()
        self.forward_host = None

    def buildProtocol(self, addr):
        prot = ProxyServer()
        prot.factory = self
        return prot

class ProxyServer(LineReceiver):

    def log(self, message, symbol='*', verbosity_level=1):
        log(message, id=self.connection_id, symbol=symbol, verbosity_level=verbosity_level)

    def __init__(self, *args, **kwargs):
        global next_connection_id
        self.connection_id = get_next_connection_id()

        self._request_obj = http.Request()
        self._connect_response = False
        self._forward = True
        self._connect_uri = None
        self._connect_host = None
        self._connect_ssl = None
        self._connect_port = None
        self._client_factory = None

    def lineReceived(self, *args, **kwargs):
        line = args[0]
        self.log(line, symbol='>', verbosity_level=3)
        self._request_obj.add_line(line)

        if self._request_obj.headers_complete:
            self.setRawMode()
            
    def rawDataReceived(self, *args, **kwargs):
        data = args[0]
        self._request_obj.add_data(data)
        self.log(data, symbol='d>', verbosity_level=3)

    def dataReceived(self, *args, **kwargs):
        # receives the data then checks if the request is complete.
        # if it is, it calls full_Request_received
        LineReceiver.dataReceived(self, *args, **kwargs)

        if self._request_obj.complete:
            self.full_request_received()
        
    def _start_tls(self, cert_host=None):
        from pappyproxy.pappy import session

        # Generate a cert for the hostname and start tls
        if cert_host is None:
            host = self._request_obj.host
        else:
            host = cert_host
        if not host in cached_certs:
            log("Generating cert for '%s'" % host,
                verbosity_level=3)
            (pkey, cert) = generate_cert(host,
                                         session.config.cert_dir)
            cached_certs[host] = (pkey, cert)
        else:
            log("Using cached cert for %s" % host, verbosity_level=3)
            (pkey, cert) = cached_certs[host]
        ctx = ServerTLSContext(
            private_key=pkey,
            certificate=cert,
        )
        self.transport.startTLS(ctx, self.factory)

    def _connect_okay(self):
        self.log('Responding to browser CONNECT request', verbosity_level=3)
        okay_str = 'HTTP/1.1 200 Connection established\r\n\r\n'
        self.transport.write(okay_str)
                
    @defer.inlineCallbacks
    def full_request_received(self):
        from pappyproxy.http import Request

        global cached_certs
        
        self.log('End of request', verbosity_level=3)

        forward = True
        if self._request_obj.verb.upper() == 'CONNECT':
            self._connect_okay()
            self._start_tls()
            self._connect_uri = self._request_obj.url
            self._connect_host = self._request_obj.host
            self._connect_ssl = True # do we just assume connect means ssl?
            self._connect_port = self._request_obj.port
            self.log('uri=%s, ssl=%s, connect_port=%s' % (self._connect_uri, self._connect_ssl, self._connect_port), verbosity_level=3)
            forward = False

        if self._request_obj.host == 'pappy':
            yield self.factory.web_server.handle_request(self._request_obj)
            self.transport.write(self._request_obj.response.full_message)
            forward = False

        # if _request_obj.host is a listener, forward = False

        if self.factory.intercepting_macros:
            return_transport = None
        else:
            return_transport = self.transport

        if forward:
            d = Request.submit_request(self._request_obj,
                                       save_request=True,
                                       intercepting_macros=self.factory.intercepting_macros,
                                       stream_transport=return_transport)
            if return_transport is None:
                d.addCallback(self.send_response_back)
        self._reset()
        
    def _reset(self):
        # Reset per-request variables and have the request default to using
        # some parameters from the connect request
        self.log("Resetting per-request data", verbosity_level=3)
        self._connect_response = False
        self._request_obj = http.Request()
        if self._connect_uri:
            self._request_obj.url = self._connect_uri
        if self._connect_host:
            self._request_obj._host = self._connect_host
        if self._connect_ssl:
            self._request_obj.is_ssl = self._connect_ssl
        if self._connect_port:
            self._request_obj.port = self._connect_port
        self.setLineMode()

    def send_response_back(self, request):
        if request.response is not None:
            self.transport.write(request.response.full_response)
        self.log("Response sent back, losing connection")
        self.transport.loseConnection()
        
    def connectionMade(self):
        if self.factory.force_ssl:
            self._start_tls(self.factory.forward_host)
                
    def connectionLost(self, reason):
        self.log('Connection lost with browser: %s' % reason.getErrorMessage())
        
        
class ServerTLSContext(ssl.ContextFactory):
    def __init__(self, private_key, certificate):
        self.private_key = private_key
        self.certificate = certificate
        self.sslmethod = SSL.TLSv1_METHOD
        self.cacheContext()

    def cacheContext(self):
        ctx = SSL.Context(self.sslmethod)
        ctx.use_certificate(self.certificate)
        ctx.use_privatekey(self.private_key)
        self._context = ctx
   
    def __getstate__(self):
        d = self.__dict__.copy()
        del d['_context']
        return d
   
    def __setstate__(self, state):
        self.__dict__ = state
        self.cacheContext()
   
    def getContext(self):
        """Create an SSL context.
        """
        return self._context

        
def generate_cert_serial():
    # Generates a random serial to be used for the cert
    return random.getrandbits(8*20)

def load_certs_from_dir(cert_dir):
    from pappyproxy.pappy import session
    try:
        with open(cert_dir+'/'+session.config.ssl_ca_file, 'rt') as f:
            ca_raw = f.read()
    except IOError:
        raise PappyException("Could not load CA cert! Generate certs using the `gencerts` command then add the .crt file to your browser.")

    try:
        with open(cert_dir+'/'+session.config.ssl_pkey_file, 'rt') as f:
            ca_key_raw = f.read()
    except IOError:
        raise PappyException("Could not load CA private key!")

    return (ca_raw, ca_key_raw)
        
def generate_cert(hostname, cert_dir):
    (ca_raw, ca_key_raw) = load_certs_from_dir(cert_dir)

    ca_cert = crypto.load_certificate(crypto.FILETYPE_PEM, ca_raw)
    ca_key = crypto.load_privatekey(crypto.FILETYPE_PEM, ca_key_raw)

    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)

    cert = crypto.X509()
    cert.get_subject().CN = hostname
    cert.set_serial_number(generate_cert_serial())
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10*365*24*60*60)
    cert.set_issuer(ca_cert.get_subject())
    cert.set_pubkey(key)
    cert.sign(ca_key, "sha256")

    return (key, cert)


def generate_ca_certs(cert_dir):
    from pappyproxy.pappy import session

    # Make directory if necessary
    if not os.path.exists(cert_dir):
        os.makedirs(cert_dir)
    
    # Private key
    print "Generating private key... ",
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)
    with os.fdopen(os.open(cert_dir+'/'+session.config.ssl_pkey_file, os.O_WRONLY | os.O_CREAT, 0o0600), 'w') as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
    print "Done!"

    # Hostname doesn't matter since it's a client cert
    print "Generating client cert... ",
    cert = crypto.X509()
    cert.get_subject().C  = 'US' # Country name
    cert.get_subject().ST = 'Michigan' # State or province name
    cert.get_subject().L  = 'Ann Arbor' # Locality name
    cert.get_subject().O  = 'Pappy Proxy' # Organization name
    #cert.get_subject().OU = '' # Organizational unit name
    cert.get_subject().CN = 'Pappy Proxy' # Common name

    cert.set_serial_number(generate_cert_serial())
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10*365*24*60*60)
    cert.set_issuer(cert.get_subject())
    cert.add_extensions([
        crypto.X509Extension("basicConstraints", True,
                                "CA:TRUE, pathlen:0"),
        crypto.X509Extension("keyUsage", True,
                                "keyCertSign, cRLSign"),
        crypto.X509Extension("subjectKeyIdentifier", False, "hash",
                                        subject=cert),
    ])
    cert.set_pubkey(key)
    cert.sign(key, 'sha256')
    with os.fdopen(os.open(cert_dir+'/'+session.config.ssl_ca_file, os.O_WRONLY | os.O_CREAT, 0o0600), 'w') as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    print "Done!"

