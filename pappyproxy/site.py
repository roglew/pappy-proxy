import os
import mimetypes

from .http import Request, Response
from .util import PappyStringTransport, PappyException

from twisted.test.proto_helpers import StringTransport
from twisted.web.server import Site, NOT_DONE_YET
from twisted.web import static
from twisted.web.resource import Resource, NoResource
from jinja2 import Environment, FileSystemLoader
from twisted.internet import defer

## The web server class

class PappyWebServer(object):
    """
    A class that is used to serve pages for requests to http://pappy. It is a
    ghetto wrapper around a twisted web Site object. Give it a request object
    and it will add a response to it.

    NOINDEX
    """
    
    from pappyproxy.pappy import session
    site_dir = session.config.pappy_dir+'/site'
    loader = FileSystemLoader(site_dir)
    env = Environment(loader=loader)

    def __init__(self):
        root = RootResource(self.site_dir)
        self.site = Site(root)

    @staticmethod
    def render_template(*args, **kwargs):
        return PappyWebServer.env.get_template(args[0]).render(args[1:], **kwargs).encode('utf-8')

    @defer.inlineCallbacks
    def handle_request(self, req):
        protocol = self.site.buildProtocol(None)
        tr = PappyStringTransport()
        protocol.makeConnection(tr)
        protocol.dataReceived(req.full_request)
        tr.waitForProducers()
        ## WORKING HERE
        # use loading functions to load response
        yield tr.complete_deferred
        rsp_raw = tr.value()
        rsp = Response(rsp_raw)
        req.response = rsp
        
## functions
def blocking_string_request(func):
    """
    Wrapper for blocking request handlers in resources. The custom string
    transport has a deferred that must be called back when the messege is
    complete. If the message blocks though, you can just call it back right away
    
    NOINDEX
    """
    def f(self, request):
        request.transport.complete_deferred.callback(None)
        return func(self, request)
    return f

## Resources

class PappyResource(Resource):
    """
    Helper class for site resources.
    NOINDEX
    """

    def getChild(self, name, request):
        if name == '':
            return self
        return Resource.getChild(self, name, request)

class RootResource(PappyResource):

    def __init__(self, site_dir):
        PappyResource.__init__(self)
        self.site_dir = site_dir
        self.dirListing = False

        # Static resource
        self.static_resource = NoDirFile(self.site_dir + '/static')
        self.putChild('static', self.static_resource)

        # Cert download resource
        self.putChild('certs', CertResource())

        # Response viewing resource
        self.putChild('rsp', ResponseResource())

    @blocking_string_request
    def render_GET(self, request):
        return PappyWebServer.render_template('index.html')

class NoDirFile(static.File):

    def directoryListing(self):
        return NoResource()

    @blocking_string_request
    def render_GET(self, request):
        return static.File.render_GET(self, request)

## Cert resources
    
class CertResource(PappyResource):

    def __init__(self):
        PappyResource.__init__(self)

        self.putChild('download', CertDownload())

    @blocking_string_request
    def render_GET(self, request):
        return PappyWebServer.render_template('certs.html')

class CertDownload(PappyResource):

    @blocking_string_request
    def render_GET(self, request):
        from .pappy import session

        cert_dir = session.config.cert_dir
        ssl_ca_file = session.config.ssl_ca_file
        with open(os.path.join(cert_dir, ssl_ca_file), 'r') as f:
            ca_raw = f.read()
        request.responseHeaders.addRawHeader("Content-Type", "application/x-x509-ca-cert")
        return ca_raw

## View responses

class ResponseResource(PappyResource):

    def getChild(self, name, request):
        if name == '':
            return self
        return ViewResponseResource(name)

    @blocking_string_request
    def render_GET(self, request):
        return PappyWebServer.render_template('viewrsp.html')
    
class ViewResponseResource(PappyResource):

    def __init__(self, reqid):
        PappyResource.__init__(self)
        self.reqid = reqid

    def render_GET(self, request):
        d = Request.load_request(self.reqid)
        d.addCallback(self._render_response, request)
        d.addErrback(self._render_response_err, request)
        d.addCallback(lambda _: request.transport.complete_deferred.callback(None))
        return NOT_DONE_YET

    def _render_response(self, req, tw_request):
        if req.response:
            if not req.response.body:
                raise PappyException("Response has no body")
            if 'content-type' in req.response.headers:
                tw_request.responseHeaders.addRawHeader("Content-Type", req.response.headers['content-type'])
            else:
                guess = mimetypes.guess_type(req.url)
                if guess[0]:
                    tw_request.responseHeaders.addRawHeader("Content-Type", guess[0])
            tw_request.write(req.response.body)
        else:
            tw_request.write(PappyWebServer.render_template('norsp.html'))
        tw_request.finish()

    def _render_response_err(self, err, tw_request):
        tw_request.write(PappyWebServer.render_template('norsp.html', errmsg=err.getErrorMessage()))
        tw_request.finish()
        err.trap(Exception)
