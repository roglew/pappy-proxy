import collections
import copy
import datetime
import os
import random

from OpenSSL import SSL
from OpenSSL import crypto
from pappyproxy.util import PappyException, printable_data, short_data
from twisted.internet import defer
from twisted.internet import reactor, ssl
from twisted.internet.protocol import ClientFactory, ServerFactory, Protocol
from twisted.protocols.basic import LineReceiver
from twisted.python.failure import Failure
#from twisted.web.client import BrowserLikePolicyForHTTPS
from pappyproxy.util import hexdump

next_connection_id = 1

cached_certs = {}

def get_next_connection_id():
    global next_connection_id
    ret_id = next_connection_id
    next_connection_id += 1
    return ret_id

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
            
def is_wildcardable_domain_name(domain):
    """
    Guesses if this is a domain that can have a wildcard CN
    """
    parts = domain.split('.')
    if len(parts) <= 2:
        # can't wildcard single names or root domains
        return False
    if len(parts) != 4:
        return True
    for part in parts:
        try:
            v = int(part)
            if v < 0 or v > 255:
                return True
        except ValueError:
            return True
    return False

def get_wildcard_cn(domain):
    """
    Returns a wildcard CN for the domain given
    """
    top_parts = domain.split('.')[1:] # Wildcards the first subdomain
    return '*.' + '.'.join(top_parts) # convert to *.example.com

def get_most_general_cn(domain):
    if is_wildcardable_domain_name(domain):
        return get_wildcard_cn(domain)
    else:
        return domain
        
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

def generate_tls_context(cert_host):
    from pappyproxy.pappy import session

    # Generate a cert for the hostname and start tls
    host = cert_host
    cn_host = get_most_general_cn(host)
    if not host in cached_certs:
        log("Generating cert for '%s'" % cn_host,
            verbosity_level=3)
        (pkey, cert) = generate_cert(cn_host,
                                     session.config.cert_dir)
        cached_certs[cn_host] = (pkey, cert)
    else:
        log("Using cached cert for %s" % cn_host, verbosity_level=3)
        (pkey, cert) = cached_certs[cn_host]
    ctx = ServerTLSContext(
        private_key=pkey,
        certificate=cert,
    )
    return ctx


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
    
def make_proxied_connection(protocol_factory, target_host, target_port, use_ssl,
                            socks_config=None, log_id=None, http_error_transport=None):
    from twisted.internet.endpoints import SSL4ClientEndpoint, TCP4ClientEndpoint
    from txsocksx.client import SOCKS5ClientEndpoint
    from txsocksx.tls import TLSWrapClientEndpoint
    from pappyproxy.pappy import session

    if socks_config is not None:
        log("Connecting to socks proxy", id=log_id)
        sock_host = socks_config['host']
        sock_port = int(socks_config['port'])
        methods = {'anonymous': ()}
        if 'username' in socks_config and 'password' in socks_config:
            methods['login'] = (socks_config['username'], socks_config['password'])
        tcp_endpoint = TCP4ClientEndpoint(reactor, sock_host, sock_port)
        socks_endpoint = SOCKS5ClientEndpoint(target_host, target_port, tcp_endpoint, methods=methods)
        if use_ssl:
            log("Using SSL over proxy to connect to %s:%d ssl=%s" % (target_host, target_port, use_ssl), id=log_id)
            endpoint = TLSWrapClientEndpoint(ssl.ClientContextFactory(), socks_endpoint)
        else:
            log("Using TCP over proxy to connect to %s:%d ssl=%s" % (target_host, target_port, use_ssl), id=log_id)
            endpoint = socks_endpoint
    else:
        log("Connecting directly to host", id=log_id)
        if use_ssl:
            log("Using SSL to connect to %s:%d ssl=%s" % (target_host, target_port, use_ssl), id=log_id)
            #context = BrowserLikePolicyForHTTPS().creatorForNetloc(target_host, target_port)
            context = ssl.ClientContextFactory()
            endpoint = SSL4ClientEndpoint(reactor, target_host, target_port, context)
        else:
            log("Using TCP to connect to %s:%d ssl=%s" % (target_host, target_port, use_ssl), id=log_id)
            endpoint = TCP4ClientEndpoint(reactor, target_host, target_port)

    connection_deferred = endpoint.connect(protocol_factory)
    if http_error_transport:
        connection_deferred.addErrback(connection_error_http_response,
                                       http_error_transport, log_id)
        
def connection_error_http_response(error, transport, log_id):
    from .http import Response
    from .util import html_escape
    rsp = Response(('HTTP/1.1 200 OK\r\n'
                    'Connection: close\r\n'
                    'Cache-control: no-cache\r\n'
                    'Pragma: no-cache\r\n'
                    'Cache-control: no-store\r\n'
                    'X-Frame-Options: DENY\r\n\r\n'))
    rsp.body = ('<html><head><title>Pappy Error</title></head>'
                '<body>'
                '<h1>Pappy Error</h1><h2>Pappy could not connect to the remote host:</h2><p>{0}</p>'
                '</body>'
                '</html>').format(html_escape(error.getErrorMessage()))
    log("Error connecting to remote host. Sending error response.", id=log_id,
        verbosity_level=3)
    log("pc< %s" % rsp.full_message, id=log_id, verbosity_level=3)
    transport.write(rsp.full_message)

def get_http_proxy_addr():
    """
    Returns the main session's 
    """
    from pappyproxy import pappy

    if not pappy.session.config.http_proxy:
        return None
    host = pappy.session.config.http_proxy['host']
    port = pappy.session.config.http_proxy['port']
    return (host, port)

def start_maybe_tls(transport, tls_host, start_tls_callback=None):
    
    newprot = MaybeTLSProtocol(transport.protocol,
            tls_host=tls_host,
            start_tls_callback=start_tls_callback)
    newprot.transport = transport
    transport.protocol = newprot

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


class ProtocolProxy(object):
    """
    A base object to be used to implement a proxy for an object.
    Responsible for taking in data from the client and the server.
    Base class contains minimum for the protocol to hook into the
    listener.
    """

    def __init__(self):
        self.client_transport = None
        self.client_connected = False
        self.client_buffer = ''
        self.client_start_tls = False
        self.client_tls_host = ''
        self.client_protocol = None
        self.client_do_maybe_tls = False

        self.server_transport = None
        self.server_connected = False
        self.server_buffer = ''
        self.server_start_tls = False
        self.conn_is_maybe_ssl = False
        self.server_protocol = None

        self.conn_host = None
        self.conn_port = None
        self.conn_is_ssl = False
        self.connection_id = get_next_connection_id()

    def log(self, message, symbol='*', verbosity_level=3):
        if self.client_protocol:
            log(message, id=self.connection_id, symbol=symbol, verbosity_level=verbosity_level)
        else:
            log(message, symbol=symbol, verbosity_level=verbosity_level)

    def connect(self, host, port, use_ssl, use_socks=False):
        from pappyproxy.pappy import session

        self.connecting = True

        connect_with_ssl = use_ssl
        if self.conn_is_maybe_ssl:
            connect_with_ssl = False

        self.log("Connecting to %s:%d ssl=%s (maybe_ssl=%s)" % (host, port, connect_with_ssl, self.conn_is_maybe_ssl))
        factory = PassthroughProtocolFactory(self.server_data_received,
                                             self.server_connection_made,
                                             self.server_connection_lost)
        self.conn_host = host
        self.conn_port = port
        if self.conn_is_maybe_ssl:
            self.conn_is_ssl = False
        else:
            self.conn_is_ssl = use_ssl
        if use_socks:
            socks_config = session.config.socks_proxy
        else:
            socks_config = None

        make_proxied_connection(factory, host, port, connect_with_ssl, socks_config=socks_config,
                                log_id=self.connection_id, http_error_transport=self.client_transport)

    ## Client interactions

    def client_data_received(self, data):
        """
        Implemented by child class
        """
        pass

    def send_client_data(self, data):
        self.log("pc< %s" % short_data(data))
        if self.client_connected:
            self.client_transport.write(data)
        else:
            self.client_buffer += data

    def client_connection_made(self, protocol):
        self.log("Client connection made")
        self.client_protocol = protocol
        self.client_transport = self.client_protocol.transport
        self.client_connected = True
        self.connecting = False

        if self.client_start_tls:
            if self.client_do_maybe_tls:
                self.start_client_maybe_tls(self.client_tls_host)
            else:
                self.start_client_tls(self.client_tls_host)
        if self.client_buffer != '':
            self.client_transport.write(self.client_buffer)
            self.client_buffer = ''

    def client_connection_lost(self, reason):
        self.client_connected = False

    def add_client_data(self, data):
        """
        Called when data is received from the client.
        """
        pass

    def start_server_tls(self):
        if self.server_connected:
            self.log("Starting TLS on server transport")
            self.conn_is_ssl = True
            self.server_transport.startTLS(ssl.ClientContextFactory())
        else:
            self.log("Server not yet connected, will start TLS on connect")
            self.server_start_tls = True

    def start_client_maybe_tls(self, cert_host):
        ctx = generate_tls_context(cert_host)
        if self.client_connected:
            self.log("Starting maybe TLS on client transport")
            self.conn_is_maybe_ssl = True
            start_maybe_tls(self.client_transport,
                            tls_host=cert_host,
                            start_tls_callback=self.start_server_tls)
        else:
            self.log("Client not yet connected, will start maybe TLS on connect")
            self.client_do_maybe_tls = True
            self.client_start_tls = True
            self.client_tls_host = cert_host

    def start_client_tls(self, cert_host):
        if self.client_connected:
            self.log("Starting TLS on client transport")
            ctx = generate_tls_context(cert_host)
            self.client_transport.startTLS(ctx)
        else:
            self.log("Client not yet connected, will start TLS on connect")
            self.client_start_tls = True
            self.client_tls_host = cert_host

    ## Server interactions

    def server_data_received(self, data):
        """
        Implemented by child class
        """
        pass

    def send_server_data(self, data):
        if self.server_connected:
            self.log("ps> %s" % short_data(data))
            self.server_transport.write(data)
        else:
            self.log("Buffering...")
            self.log("pb> %s" % short_data(data))
            self.server_buffer += data

    def server_connection_made(self, protocol):
        """
        self.server_protocol must be set before calling
        """
        self.log("Server connection made")
        self.server_protocol = protocol
        self.server_transport = protocol.transport
        self.server_connected = True

        if self.server_start_tls:
            self.start_server_tls()
        if self.server_buffer != '':
            self.log("Writing buffer to server")
            self.log("ps> %s" % short_data(self.server_buffer))
            self.server_transport.write(self.server_buffer)
            self.server_buffer = ''

    def server_connection_lost(self, reason):
        self.server_connected = False

    def add_server_data(self, data):
        """
        Called when data is received from the server.
        """
        pass

    def close_server_connection(self):
        if self.server_transport:
            self.log("Manually closing server connection")
            self.server_transport.loseConnection()
            self.server_transport = None
            self.server_connected = False
            self.server_buffer = ''
            self.server_start_tls = False
            self.server_protocol = None

    def close_client_connection(self):
        if self.client_transport:
            self.log("Manually closing client connection")
            self.client_transport.loseConnection()
            self.client_transport = None
            self.client_connected = False
            self.client_buffer = ''
            self.client_start_tls = False
            self.client_tls_host = ''
            self.client_protocol = None
            self.client_do_maybe_tls = False

    def close_connections(self):
        self.close_server_connection()
        self.close_client_connection()
        

class PassthroughProtocolFactory(ClientFactory):

    def __init__(self,
                 data_callback,
                 connection_made_callback,
                 connection_lost_callback):
        self.data_callback = data_callback
        self.connection_made_callback = connection_made_callback
        self.connection_lost_callback = connection_lost_callback
        self.protocol = None

    def buildProtocol(self, addr):
        prot = PassthroughProtocol(self.data_callback,
                                   self.connection_made_callback,
                                   self.connection_lost_callback)
        self.protocol = prot
        prot.factory = self
        log("addr: %s" % str(addr))
        return prot
        
    def clientConnectionFailed(self, connector, reason):
        pass
        
    def clientConnectionLost(self, connector, reason):
        pass
        
class PassthroughProtocol(Protocol):
    """
    A protocol that makes a connection to a remote server and makes callbacks to
    functions to handle network events
    """
    def __init__(self, data_callback, connection_made_callback, connection_lost_callback):
        self.data_callback = data_callback
        self.connection_made_callback = connection_made_callback
        self.connection_lost_callback = connection_lost_callback
        self.connected = False

    def dataReceived(self, data):
        self.data_callback(data)

    def connectionMade(self):
        self.connected = True
        self.connection_made_callback(self)

    def connectionLost(self, reason):
        self.connected = False
        self.connection_lost_callback(reason)

class ProxyProtocolFactory(ServerFactory):

    next_int_macro_id = 0

    def __init__(self):
        self._int_macros = {}
        self._macro_order = []
        self._macro_names = {}

    def add_intercepting_macro(self, macro, name=None):
        new_id = self._get_int_macro_id()
        self._int_macros[new_id] = macro
        self._macro_order.append(new_id)
        self._macro_names[new_id] = name

    def remove_intercepting_macro(self, macro_id=None, name=None):
        if macro_id is None and name is None:
            raise PappyException("Either macro_id or name must be given")

        ids_to_remove = []
        if macro_id:
            ids_to_remove.append(macro_id)
        if name:
            for k, v in self._macro_names.iteritems():
                if v == name:
                    ids_to_remove.append(k)

        for i in ids_to_remove:
            if i in self._macro_order:
                self._macro_order.remove(i)
            if i in self._macro_names:
                del self._macro_names[i]
            if i in self._int_macros:
                del self._int_macros[i]

    def get_macro_list(self):
        return [self._int_macros[i] for i in self._macro_order]

    @staticmethod
    def _get_int_macro_id():
        i = ProxyProtocolFactory.next_int_macro_id
        ProxyProtocolFactory.next_int_macro_id += 1
        return i
    
    def buildProtocol(self, addr):
        prot = ProxyProtocol()
        prot.factory = self
        return prot

class ProxyProtocol(Protocol):
    """
    The protocol hooked on to a listening port.
    """

    protocol = "http"

    def __init__(self):
        from pappyproxy.http import HTTPProtocolProxy
        self.protocol_proxy = HTTPProtocolProxy()
        self.protocol_proxy.client_protocol = self

    def dataReceived(self, data):
        self.protocol_proxy.client_data_received(data)

    def connectionMade(self):
        self.protocol_proxy.client_connection_made(self)

    def connectionLost(self, reason):
        self.protocol_proxy.client_connection_lost(reason)

class MaybeTLSProtocol(Protocol):
    """
    A protocol that wraps another protocol and will guess whether the incoming
    data is TLS and if it is, attempts to strip the TLS before passing it to
    the protocol
    """

    STATE_DECIDING = 0
    STATE_PASSTHROUGH = 1

    def __init__(self, protocol, tls_host, start_tls_callback=None):
        self.protocol = protocol
        self.state = MaybeTLSProtocol.STATE_DECIDING
        self._data_buffer = ''
        self.start_tls_callback = start_tls_callback
        self.tls_host = tls_host

    def log(self, message, symbol='*', verbosity_level=3):
        if hasattr(self, "connection_id"):
            log(message, id=self.connection_id, symbol=symbol, verbosity_level=verbosity_level)
        else:
            log(message, symbol=symbol, verbosity_level=verbosity_level)

    def decide_plaintext(self):
        self.protocol.dataReceived(self._data_buffer)
        self._data_buffer = ''
        self.state = MaybeTLSProtocol.STATE_PASSTHROUGH

    def decide_tls(self):
        # Store the original transport. I think that startTLS changes self.transport
        transport = self.transport

        # Calling startTLS wraps whatever protocol is currently associated with the
        # transport in another protocol that handles TLS. We want to send the data
        # we already received to that protocol since the data we received is part
        # of the TLS handshake
        self.transport.startTLS(generate_tls_context(self.tls_host))
        transport.protocol.dataReceived(self._data_buffer)

        # The TLS protocol wrapper will send us the decrypted data so we should go
        # into passthrough mode
        self._data_buffer = ''
        self.state = MaybeTLSProtocol.STATE_PASSTHROUGH

        # Make the callback
        if self.start_tls_callback is not None:
            self.start_tls_callback()

    def guess_if_tls(self):
        if self._data_buffer == '':
            return

        # Is the first byte the byte of a ClientHello?
        if ord(self._data_buffer[0]) == 0x16:
            # Yes! Assume TLS
            self.decide_tls()
        else:
            # Nope! It's plaintext
            self.decide_plaintext()

    def dataReceived(self, data):
        if self.state == MaybeTLSProtocol.STATE_DECIDING:
            self._data_buffer += data
            self.guess_if_tls()
        elif self.state == MaybeTLSProtocol.STATE_PASSTHROUGH:
            self.protocol.dataReceived(data)
        else:
            raise Exception("Protocol in invalid state")
