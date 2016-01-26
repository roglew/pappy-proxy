import copy
import datetime
import os
import random

from OpenSSL import SSL
from OpenSSL import crypto
from pappyproxy import config
from pappyproxy import context
from pappyproxy import http
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

    if config.DEBUG_TO_FILE and not os.path.exists(config.DEBUG_DIR):
        os.makedirs(config.DEBUG_DIR)
    if id:
        debug_str = '[%s](%d) %s' % (symbol, id, message)
        if config.DEBUG_TO_FILE:
            with open(config.DEBUG_DIR+'/connection_%d.log' % id, 'a') as f:
                f.write(debug_str+'\n')
    else:
        debug_str = '[%s] %s' % (symbol, message)
        if config.DEBUG_TO_FILE:
            with open(config.DEBUG_DIR+'/debug.log', 'a') as f:
                f.write(debug_str+'\n')
    if config.DEBUG_VERBOSITY >= verbosity_level:
        print debug_str
    
def log_request(request, id=None, symbol='*', verbosity_level=3):
    r_split = request.split('\r\n')
    for l in r_split:
        log(l, id, symbol, verbosity_level)
        
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

        self._response_obj = http.Response()

    def log(self, message, symbol='*', verbosity_level=1):
        log(message, id=self.factory.connection_id, symbol=symbol, verbosity_level=verbosity_level)

    def lineReceived(self, *args, **kwargs):
        line = args[0]
        if line is None:
            line = ''
        self._response_obj.add_line(line)
        self.log(line, symbol='r<', verbosity_level=3)
        if self.factory.stream_response:
            self.log('Returning line back through stream')
            self.factory.return_transport.write(line+'\r\n')
        else:
            self.log('Not streaming, not returning')
            self.log(self.factory.stream_response)
        if self._response_obj.headers_complete:
            if self._response_obj.complete:
                self.handle_response_end()
                return
            self.log("Headers end, length given, waiting for data", verbosity_level=3)
            self.setRawMode()

    def rawDataReceived(self, *args, **kwargs):
        data = args[0]
        self.log('Returning data back through stream')
        if self.factory.stream_response:
            self.factory.return_transport.write(data)
        if not self._response_obj.complete:
            if data:
                s = printable_data(data)
                dlines = s.split('\n')
                for l in dlines:
                    self.log(l, symbol='<rd', verbosity_level=3)
            self._response_obj.add_data(data)

            if self._response_obj.complete:
                self.handle_response_end()
            
    def connectionMade(self):
        self._connection_made()

    @defer.inlineCallbacks
    def _connection_made(self):
        self.log('Connection established, sending request...', verbosity_level=3)
        # Make sure to add errback
        lines = self.request.full_request.splitlines()
        for l in lines:
            self.log(l, symbol='>r', verbosity_level=3)

        sendreq = self.request
        if context.in_scope(sendreq):
            to_mangle = copy.copy(self.factory.intercepting_macros).iteritems()
            if self.factory.save_all:
                # It isn't the actual time, but this should work in case
                # we do an 'ls' before it gets a real time saved
                self.request.time_start = datetime.datetime.now()
                if self.factory.stream_response and not to_mangle:
                    self.request.async_deep_save()
                else:
                    yield self.request.async_deep_save()

            ## Run intercepting macros
            # if we don't copy it, when we delete a macro from the console,
            # we get a crash. We do a shallow copy to keep the macro
            # instances the same.
            for k, macro in to_mangle:
                if macro.intercept_requests:
                    if macro.async_req:
                        sendreq = yield macro.async_mangle_request(sendreq)
                    else:
                        sendreq = macro.mangle_request(sendreq)

                    if sendreq is None:
                        self.log('Request dropped, losing connection')
                        self.transport.loseConnection()
                        self.request = None
                        self.data_defer.callback(None)
                        if self.factory.save_all:
                            yield sendreq.async_deep_save()
                        defer.returnValue(None)

            if sendreq != self.request:
                sendreq.unmangled = self.request
                if self.factory.save_all:
                    sendreq.time_start = datetime.datetime.now()
                    yield sendreq.async_deep_save()
        else:
            self.log("Request out of scope, passing along unmangled")
                
        if not self._sent:
            self.factory.start_time = datetime.datetime.now()
            self.transport.write(sendreq.full_request)
            self.request = sendreq
            self.request.submitted = True
            self._sent = True
            self.data_defer.callback(sendreq)
        defer.returnValue(None)

    def connectionLost(self, reason):
        pass
        
    def handle_response_end(self, *args, **kwargs):
        self.log("Remote response finished, returning data to original stream")
        self.request.response = self._response_obj
        self.log('Response ended, losing connection')
        self.transport.loseConnection()
        assert self._response_obj.full_response
        self.factory.return_request_pair(self.request)


class ProxyClientFactory(ClientFactory):

    def __init__(self, request, save_all=False, stream_response=False,
                 return_transport=None):
        self.request = request
        self.connection_id = -1
        self.data_defer = defer.Deferred()
        self.start_time = datetime.datetime.now()
        self.end_time = None
        self.save_all = save_all
        self.stream_response = stream_response
        self.return_transport = return_transport
        self.intercepting_macros = {}

    def log(self, message, symbol='*', verbosity_level=1):
        log(message, id=self.connection_id, symbol=symbol, verbosity_level=verbosity_level)

    def buildProtocol(self, addr):
        p = ProxyClient(self.request)
        p.factory = self
        return p

    def clientConnectionFailed(self, connector, reason):
        self.log("Connection failed with remote server: %s" % reason.getErrorMessage())

    def clientConnectionLost(self, connector, reason):
        self.log("Connection lost with remote server: %s" % reason.getErrorMessage())

    @defer.inlineCallbacks
    def return_request_pair(self, request):
        self.end_time = datetime.datetime.now()
        log_request(printable_data(request.response.full_response), id=self.connection_id, symbol='<m', verbosity_level=3)

        request.time_start = self.start_time
        request.time_end = self.end_time
        if context.in_scope(request):
            to_mangle = copy.copy(self.intercepting_macros).iteritems()
            if self.save_all:
                if self.stream_response and not to_mangle:
                    request.async_deep_save()
                else:
                    yield request.async_deep_save()

            # if we don't copy it, when we delete a macro from the console,
            # we get a crash. We do a shallow copy to keep the macro
            # instances the same.
            old_rsp = request.response
            for k, macro in to_mangle:
                if macro.intercept_responses:
                    if macro.async_rsp:
                        mangled_rsp = yield macro.async_mangle_response(request)
                    else:
                        mangled_rsp = macro.mangle_response(request)

                    if mangled_rsp is None:
                        request.response = None
                        self.data_defer.callback(request)
                        if self.save_all:
                            yield request.async_deep_save()
                        self.log("Response dropped, losing connection")
                        self.transport.loseConnection()
                        defer.returnValue(None)

                    request.response = mangled_rsp

            if request.response != old_rsp:
                request.response.unmangled = old_rsp
                if self.save_all:
                    yield request.async_deep_save()

            if request.response:
                log_request(printable_data(request.response.full_response),
                            id=self.connection_id, symbol='<', verbosity_level=3)
        else:
            self.log("Response out of scope, passing along unmangled")
        self.data_defer.callback(request)
        defer.returnValue(None)

class ProxyServerFactory(ServerFactory):

    def __init__(self, save_all=False):
        self.intercepting_macros = {}
        self.save_all = save_all

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

    def lineReceived(self, *args, **kwargs):
        line = args[0]
        self.log(line, symbol='>', verbosity_level=3)
        self._request_obj.add_line(line)

        if self._request_obj.verb.upper() == 'CONNECT':
            self._connect_response = True
            self._forward = False
            self._connect_uri = self._request_obj.url

        if self._request_obj.headers_complete:
            self.setRawMode()

        if self._request_obj.complete:
            self.setLineMode()
            try:
                self.full_request_received()
            except PappyException as e:
                print str(e)
            
    def rawDataReceived(self, *args, **kwargs):
        data = args[0]
        self._request_obj.add_data(data)
        self.log(data, symbol='d>', verbosity_level=3)

        if self._request_obj.complete:
            try:
                self.full_request_received()
            except PappyException as e:
                print str(e)
        
    def full_request_received(self, *args, **kwargs):
        global cached_certs
        
        self.log('End of request', verbosity_level=3)

        if self._connect_response:
            self.log('Responding to browser CONNECT request', verbosity_level=3)
            okay_str = 'HTTP/1.1 200 Connection established\r\n\r\n'
            self.transport.write(okay_str)

            # Generate a cert for the hostname
            if not self._request_obj.host in cached_certs:
                log("Generating cert for '%s'" % self._request_obj.host,
                    verbosity_level=3)
                (pkey, cert) = generate_cert(self._request_obj.host,
                                             config.CERT_DIR)
                cached_certs[self._request_obj.host] = (pkey, cert)
            else:
                log("Using cached cert for %s" % self._request_obj.host, verbosity_level=3)
                (pkey, cert) = cached_certs[self._request_obj.host]
            ctx = ServerTLSContext(
                private_key=pkey,
                certificate=cert,
            )
            self.transport.startTLS(ctx, self.factory)

        if self._forward:
            self.log("Forwarding to %s on %d" % (self._request_obj.host, self._request_obj.port))
            if not self.factory.intercepting_macros:
                stream = True
            else:
                # We only want to call send_response_back if we're not streaming
                stream = False
            self.log('Creating client factory, stream=%s' % stream)
            factory = ProxyClientFactory(self._request_obj,
                                         save_all=self.factory.save_all,
                                         stream_response=stream,
                                         return_transport=self.transport)
            factory.intercepting_macros = self.factory.intercepting_macros
            factory.connection_id = self.connection_id
            if not stream:
                factory.data_defer.addCallback(self.send_response_back)
            if self._request_obj.is_ssl:
                self.log("Accessing over SSL...", verbosity_level=3)
                reactor.connectSSL(self._request_obj.host, self._request_obj.port, factory, ClientTLSContext())
            else:
                self.log("Accessing over TCP...", verbosity_level=3)
                reactor.connectTCP(self._request_obj.host, self._request_obj.port, factory)
                
        # Reset per-request variables
        self.log("Resetting per-request data", verbosity_level=3)
        self._connect_response = False
        self._forward = True
        self._request_obj = http.Request()
        if self._connect_uri:
            self._request_obj.url = self._connect_uri
        self.setLineMode()

    def send_response_back(self, response):
        if response is not None:
            self.transport.write(response.response.full_response)
        self.log("Response sent back, losing connection")
        self.transport.loseConnection()
                
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
    try:
        with open(cert_dir+'/'+config.SSL_CA_FILE, 'rt') as f:
            ca_raw = f.read()
    except IOError:
        raise PappyException("Could not load CA cert!")

    try:
        with open(cert_dir+'/'+config.SSL_PKEY_FILE, 'rt') as f:
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
    # Make directory if necessary
    if not os.path.exists(cert_dir):
        os.makedirs(cert_dir)
    
    # Private key
    print "Generating private key... ",
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)
    with os.fdopen(os.open(cert_dir+'/'+config.SSL_PKEY_FILE, os.O_WRONLY | os.O_CREAT, 0o0600), 'w') as f:
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
    with os.fdopen(os.open(cert_dir+'/'+config.SSL_CA_FILE, os.O_WRONLY | os.O_CREAT, 0o0600), 'w') as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    print "Done!"

