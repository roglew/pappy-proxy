import glob
import imp
import os
import random
import re

from pappyproxy import http
from pappyproxy import config
from twisted.internet import defer
from jinja2 import Environment, FileSystemLoader

class Macro(object):
    """
    A class representing a macro that can perform a series of requests and add
    data to storage.
    """

    def __init__(self, filename=''):
        self.name = ''
        self.short_name = None
        self.file_name = '' # name from the file
        self.filename = filename or '' # filename we load from
        self.source = None

        if self.filename:
            self.load()

    def __repr__(self):
        s = self.name
        names = []
        if hasattr(self.source, 'SHORT_NAME'):
            if self.source.SHORT_NAME:
                names.append(self.source.SHORT_NAME)
        names.append(self.file_name)
        s += ' (%s)' % ('/'.join(names))
        return "<Macro %s>" % s
        
    def load(self):
        if self.filename:
            match = re.findall('.*macro_(.*).py$', self.filename)
            self.file_name = match[0]
            module_name = os.path.basename(os.path.splitext(self.filename)[0])
            self.source = imp.load_source('%s'%module_name, self.filename)
            if not hasattr(self.source, 'MACRO_NAME'):
                raise PappyException('Macro in %s does not define MACRO_NAME' % self.filename)
            self.name = self.source.MACRO_NAME
            if self.name == '':
                raise PappyException('Macro in %s cannot have a blank name' % self.filename)
            if hasattr(self.source, 'SHORT_NAME'):
                self.short_name = self.source.SHORT_NAME
            else:
                self.short_name = None
        else:
            self.source = None

    def execute(self, args):
        # Execute the macro
        if self.source:
            self.source.run_macro(args)
            
class InterceptMacro(object):
    """
    A class representing a macro that modifies requests as they pass through the
    proxy
    """
    def __init__(self, filename=''):
        self.name = ''
        self.short_name = None
        self.intercept_requests = True
        self.intercept_responses = True
        self.file_name = '' # name from the file
        self.filename = filename or '' # filename we load from
        self.source = None

        if self.filename:
            self.load()

    def __repr__(self):
        s = self.name
        names = []
        if hasattr(self.source, 'SHORT_NAME'):
            if self.source.SHORT_NAME:
                names.append(self.source.SHORT_NAME)
        names.append(self.file_name)
        s += ' (%s)' % ('/'.join(names))
        return "<InterceptingMacro %s>" % s

    @property
    def do_req(self):
        if (self.source and hasattr(self.source, 'async_mangle_request') or \
           self.source and hasattr(self.source, 'mangle_request')) and \
           self.intercept_requests:
           return True
        return False

    @property
    def do_rsp(self):
        if (self.source and hasattr(self.source, 'async_mangle_response') or \
           self.source and hasattr(self.source, 'mangle_response')) and \
           self.intercept_responses:
           return True
        return False
    
    @property
    def async_req(self):
        if self.source and hasattr(self.source, 'async_mangle_request'):
            return True
        else:
            return False

    @property
    def async_rsp(self):
        if self.source and hasattr(self.source, 'async_mangle_response'):
            return True
        else:
            return False
        
    def load(self):
        if self.filename:
            match = re.findall('.*int_(.*).py$', self.filename)
            if len(match) > 0:
                self.file_name = match[0]
            else:
                self.file_name = self.filename
            module_name = os.path.basename(os.path.splitext(self.filename)[0])
            self.source = imp.load_source('%s'%module_name, self.filename)
            self.name = self.source.MACRO_NAME
            if self.name == '':
                raise PappyException('Macro in %s cannot have a blank name' % self.filename)
            if hasattr(self.source, 'SHORT_NAME'):
                self.short_name = self.source.SHORT_NAME
            else:
                self.short_name = None

            if hasattr(self.source, 'mangle_request') and \
               hasattr(self.source, 'async_mangle_request'):
                raise PappyException('Intercepting macro in %s cannot define both mangle_request and async_mangle_request' % self.filename)
            if hasattr(self.source, 'mangle_response') and \
               hasattr(self.source, 'async_mangle_response'):
                raise PappyException('Intercepting macro in %s cannot define both mangle_response and async_mangle_response' % self.filename)
        else:
            self.source = None

    def init(self, line):
        if hasattr(self.source, 'init'):
            self.source.init(line)

    def mangle_request(self, request):
        if hasattr(self.source, 'mangle_request'):
            req = self.source.mangle_request(request)
            return req
        return request

    def mangle_response(self, request):
        if hasattr(self.source, 'mangle_response'):
            rsp = self.source.mangle_response(request)
            return rsp
        return request.response

    @defer.inlineCallbacks
    def async_mangle_request(self, request):
        if hasattr(self.source, 'async_mangle_request'):
            req = yield self.source.async_mangle_request(request)
            defer.returnValue(req)
        defer.returnValue(request)

    @defer.inlineCallbacks
    def async_mangle_response(self, request):
        if hasattr(self.source, 'async_mangle_response'):
            rsp = yield self.source.async_mangle_response(request)
            defer.returnValue(rsp)
        defer.returnValue(request.response)

def load_macros(loc):
    """
    Loads the macros stored in the location and returns a list of Macro objects
    """
    macro_files = glob.glob(loc + "/macro_*.py")
    macro_objs = []
    for f in macro_files:
        macro_objs.append(Macro(f))

    int_macro_files = glob.glob(loc + "/int_*.py")
    int_macro_objs = []
    for f in int_macro_files:
        int_macro_objs.append(InterceptMacro(f))
    return (macro_objs, int_macro_objs)

def req_obj_def(req):
    lines = req.full_request.splitlines(True)
    esclines = [line.encode('string_escape') for line in lines]

    params = []
    if req.is_ssl:
        params.append('is_ssl=True')
        if req.port != 443:
            params.append('port=%d'%req.port)
    else:
        if req.port != 80:
            params.append('port=%d'%req.port)
    if params:
        req_params = ', '+', '.join(params)
    else:
        req_params = ''

    ret = 'Request (('
    for line in esclines:
        ret += "'%s'\n" % line
    ret += ')'
    ret += req_params
    ret += ')'
    return ret

def macro_from_requests(reqs, short_name='', long_name=''):
    # Generates a macro that defines request objects for each of the requests
    # in reqs
    subs = {}
    if long_name:
        subs['macro_name'] = long_name
    else:
        random.seed()
        subs['macro_name'] = 'Macro %d' % random.randint(1,99999999)

    subs['short_name'] = short_name

    n = 0
    req_lines = []
    req_params = []
    for req in reqs:
        lines = req.full_request.splitlines(True)
        esclines = [line.encode('string_escape') for line in lines]
        req_lines.append(esclines)

        params = []
        if req.is_ssl:
            params.append('is_ssl=True')
            if req.port != 443:
                params.append('port=%d'%req.port)
        else:
            if req.port != 80:
                params.append('port=%d'%req.port)
        if params:
            req_params.append(', '+', '.join(params))
        else:
            req_params.append('')
    subs['req_lines'] = req_lines
    subs['req_params'] = req_params

    loader = FileSystemLoader(config.PAPPY_DIR+'/templates')
    env = Environment(loader=loader)
    template = env.get_template('macro.py')
    return template.render(zip=zip, **subs)

def gen_imacro(short_name='', long_name=''):
    subs = {}
    if long_name:
        subs['macro_name'] = long_name
    else:
        random.seed()
        subs['macro_name'] = 'Macro %d' % random.randint(1,99999999)

    subs['short_name'] = short_name

    loader = FileSystemLoader(config.PAPPY_DIR+'/templates')
    env = Environment(loader=loader)
    template = env.get_template('intmacro.py')
    return template.render(**subs)
    
