import glob
import imp
import os
import random
import re
import stat

from jinja2 import Environment, FileSystemLoader
from pappyproxy.pappy import session
from pappyproxy.util import PappyException, load_reqlist
from twisted.internet import defer

## Template generating functions
# Must be declared before MacroTemplate class
    
@defer.inlineCallbacks
def gen_template_args_macro(args):
    if len(args) > 0:
        reqids = args[0]
        reqs = yield load_reqlist(reqids)
    else:
        reqs = []
    defer.returnValue(macro_from_requests(reqs))

def gen_template_generator_noargs(name):
    def f(args):
        subs = {}
        subs['macro_name'] = 'Macro %d' % random.randint(1,99999999)
        subs['short_name'] = ''
        return MacroTemplate.fill_template(name, subs)
    return f

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
            st = os.stat(self.filename)
            if (st.st_mode & stat.S_IWOTH):
                raise PappyException("Refusing to load world-writable macro: %s" % self.filename)
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
    def __init__(self):
        self.name = ''
        self.short_name = None
        self.intercept_requests = False
        self.intercept_responses = False
        self.intercept_ws = False

        self.async_req = False
        self.async_rsp = False
        self.async_ws = False

    def __repr__(self):
        return "<InterceptingMacro (%s)>" % self.name

    def init(self, args):
        pass

    def mangle_request(self, request):
        return request

    def mangle_response(self, request):
        return request.response

    def mangle_ws(self, request, message):
        return message

    @defer.inlineCallbacks
    def async_mangle_request(self, request):
        defer.returnValue(request)

    @defer.inlineCallbacks
    def async_mangle_response(self, request):
        defer.returnValue(request.response)

    @defer.inlineCallbacks
    def async_mangle_ws(self, request, message):
        defer.returnValue(messsage)
            
class FileInterceptMacro(InterceptMacro):
    """
    An intercepting macro that loads a macro from a file.
    """
    def __init__(self, filename=''):
        InterceptMacro.__init__(self)
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

    def load(self):
        if self.filename:
            match = re.findall('.*int_(.*).py$', self.filename)
            if len(match) > 0:
                self.file_name = match[0]
            else:
                self.file_name = self.filename
            st = os.stat(self.filename)
            if (st.st_mode & stat.S_IWOTH):
                raise PappyException("Refusing to load world-writable macro: %s" % self.filename)
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
            if hasattr(self.source, 'mangle_ws') and \
               hasattr(self.source, 'async_mangle_ws'):
                raise PappyException('Intercepting macro in %s cannot define both mangle_ws and async_mangle_ws' % self.filename)
        else:
            self.source = None

        # Update what we can do
        if self.source and hasattr(self.source, 'mangle_request'):
           self.intercept_requests = True
           self.async_req = False
        elif self.source and hasattr(self.source, 'async_mangle_request'):
           self.intercept_requests = True
           self.async_req = True
        else:
           self.intercept_requests = True

        if self.source and hasattr(self.source, 'mangle_response'):
            self.intercept_responses = True
            self.async_rsp = False
        elif self.source and hasattr(self.source, 'async_mangle_response'):
            self.intercept_responses = True
            self.async_rsp = True
        else:
            self.intercept_responses = False

        if self.source and hasattr(self.source, 'mangle_ws'):
            self.intercept_ws = True
            self.async_ws = False
        elif self.source and hasattr(self.source, 'async_mangle_ws'):
            self.intercept_ws = True
            self.async_ws = True
        else:
            self.intercept_ws = False

    def init(self, args):
        if hasattr(self.source, 'init'):
            self.source.init(args)

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

    def mangle_ws(self, request, message):
        if hasattr(self.source, 'mangle_ws'):
            mangled_ws = self.source.mangle_ws(request, message)
            return mangled_ws
        return message

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
        
class MacroTemplate(object):
    _template_data = {
        'macro': ('macro.py.template',
                  'Generic macro template',
                  '[reqids]',
                  'macro_{fname}.py',
                  gen_template_args_macro),

        'intmacro': ('intmacro.py.template',
                     'Generic intercepting macro template',
                     '',
                     'int_{fname}.py',
                     gen_template_generator_noargs('intmacro')),

        'modheader': ('macro_header.py.template',
                      'Modify a header in the request and the response if it exists.',
                      '',
                      'int_{fname}.py',
                      gen_template_generator_noargs('modheader')),

        'resubmit': ('macro_resubmit.py.template',
                     'Resubmit all in-context requests',
                     '',
                     'macro_{fname}.py',
                     gen_template_generator_noargs('resubmit')),
    }

    @classmethod
    def fill_template(cls, template, subs):
        loader = FileSystemLoader(session.config.pappy_dir+'/templates')
        env = Environment(loader=loader)
        template = env.get_template(cls._template_data[template][0])
        return template.render(zip=zip, **subs)

    @classmethod
    @defer.inlineCallbacks
    def fill_template_args(cls, template, args=[]):
        ret = cls._template_data[template][4](args)
        if isinstance(ret, defer.Deferred):
            ret = yield ret
        defer.returnValue(ret)

    @classmethod
    def template_filename(cls, template, fname):
        return cls._template_data[template][3].format(fname=fname)

    @classmethod
    def template_list(cls):
        return [k for k, v in cls._template_data.iteritems()]
    
    @classmethod
    def template_description(cls, template):
        return cls._template_data[template][1]

    @classmethod
    def template_argstring(cls, template):
        return cls._template_data[template][2]

## Other functions

    @defer.inlineCallbacks
    def async_mangle_ws(self, request, message):
        if hasattr(self.source, 'async_mangle_ws'):
            mangled_ws = yield self.source.async_mangle_ws(request, message)
            defer.returnValue(mangled_ws)
        defer.returnValue(message)
        
class MacroTemplate(object):
    _template_data = {
        'macro': ('macro.py.template',
                  'Generic macro template',
                  '[reqids]',
                  'macro_{fname}.py',
                  gen_template_args_macro),

        'intmacro': ('intmacro.py.template',
                     'Generic intercepting macro template',
                     '',
                     'int_{fname}.py',
                     gen_template_generator_noargs('intmacro')),

        'modheader': ('macro_header.py.template',
                      'Modify a header in the request and the response if it exists.',
                      '',
                      'int_{fname}.py',
                      gen_template_generator_noargs('modheader')),

        'resubmit': ('macro_resubmit.py.template',
                     'Resubmit all in-context requests',
                     '',
                     'macro_{fname}.py',
                     gen_template_generator_noargs('resubmit')),
    }

    @classmethod
    def fill_template(cls, template, subs):
        loader = FileSystemLoader(session.config.pappy_dir+'/templates')
        env = Environment(loader=loader)
        template = env.get_template(cls._template_data[template][0])
        return template.render(zip=zip, **subs)

    @classmethod
    @defer.inlineCallbacks
    def fill_template_args(cls, template, args=[]):
        ret = cls._template_data[template][4](args)
        if isinstance(ret, defer.Deferred):
            ret = yield ret
        defer.returnValue(ret)

    @classmethod
    def template_filename(cls, template, fname):
        return cls._template_data[template][3].format(fname=fname)

    @classmethod
    def template_list(cls):
        return [k for k, v in cls._template_data.iteritems()]
    
    @classmethod
    def template_description(cls, template):
        return cls._template_data[template][1]

    @classmethod
    def template_argstring(cls, template):
        return cls._template_data[template][2]

## Other functions

    @defer.inlineCallbacks
    def async_mangle_ws(self, request, message):
        if hasattr(self.source, 'async_mangle_ws'):
            mangled_ws = yield self.source.async_mangle_ws(request, message)
            defer.returnValue(mangled_ws)
        defer.returnValue(message)
        
class MacroTemplate(object):
    _template_data = {
        'macro': ('macro.py.template',
                  'Generic macro template',
                  '[reqids]',
                  'macro_{fname}.py',
                  gen_template_args_macro),

        'intmacro': ('intmacro.py.template',
                     'Generic intercepting macro template',
                     '',
                     'int_{fname}.py',
                     gen_template_generator_noargs('intmacro')),

        'modheader': ('macro_header.py.template',
                      'Modify a header in the request and the response if it exists.',
                      '',
                      'int_{fname}.py',
                      gen_template_generator_noargs('modheader')),

        'resubmit': ('macro_resubmit.py.template',
                     'Resubmit all in-context requests',
                     '',
                     'macro_{fname}.py',
                     gen_template_generator_noargs('resubmit')),
    }

    @classmethod
    def fill_template(cls, template, subs):
        loader = FileSystemLoader(session.config.pappy_dir+'/templates')
        env = Environment(loader=loader)
        template = env.get_template(cls._template_data[template][0])
        return template.render(zip=zip, **subs)

    @classmethod
    @defer.inlineCallbacks
    def fill_template_args(cls, template, args=[]):
        ret = cls._template_data[template][4](args)
        if isinstance(ret, defer.Deferred):
            ret = yield ret
        defer.returnValue(ret)

    @classmethod
    def template_filename(cls, template, fname):
        return cls._template_data[template][3].format(fname=fname)

    @classmethod
    def template_list(cls):
        return [k for k, v in cls._template_data.iteritems()]
    
    @classmethod
    def template_description(cls, template):
        return cls._template_data[template][1]

    @classmethod
    def template_argstring(cls, template):
        return cls._template_data[template][2]

## Other functions

def load_macros(loc):
    """
    Loads the macros stored in the location and returns a list of Macro objects
    """
    macro_files = glob.glob(loc + "/macro_*.py")
    macro_objs = []
    for f in macro_files:
        try:
            macro_objs.append(Macro(f))
        except PappyException as e:
            print str(e)

    int_macro_files = glob.glob(loc + "/int_*.py")
    int_macro_objs = []
    for f in int_macro_files:
        try:
            int_macro_objs.append(FileInterceptMacro(f))
        except PappyException as e:
            print str(e)
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
    if 'host' in req.headers and req.host != req.headers['host']:
        params.append('host=%d'%req.host)
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

    return MacroTemplate.fill_template('macro', subs)

@defer.inlineCallbacks
def mangle_request(request, intmacros):
    """
    Mangle a request with a list of intercepting macros.
    Returns a tuple that contains the resulting request (with its unmangled
    value set if needed) and a bool that states whether the request was modified
    Returns (None, True) if the request was dropped.
    
    :rtype: (Request, Bool)
    """
    # Mangle requests with list of intercepting macros
    if not intmacros:
        defer.returnValue((request, False))

    cur_req = request.copy()
    for macro in intmacros:
        if macro.intercept_requests:
            if macro.async_req:
                cur_req = yield macro.async_mangle_request(cur_req.copy())
            else:
                cur_req = macro.mangle_request(cur_req.copy())

            if cur_req is None:
                defer.returnValue((None, True))

    mangled = False
    if not cur_req == request or \
       not cur_req.host == request.host or \
       not cur_req.port == request.port or \
       not cur_req.is_ssl == request.is_ssl:
        # copy unique data to new request and clear it off old one
        cur_req.unmangled = request
        cur_req.unmangled.is_unmangled_version = True
        if request.response:
            cur_req.response = request.response
            request.response = None
        mangled = True
    else:
        # return the original request
        cur_req = request
    defer.returnValue((cur_req, mangled))

@defer.inlineCallbacks
def mangle_response(request, intmacros):
    """
    Mangle a request's response with a list of intercepting macros.
    Returns a bool stating whether the request's response was modified.
    Unmangled values will be updated as needed.
    
    :rtype: Bool
    """
    if not intmacros:
        defer.returnValue(False)

    old_rsp = request.response
    for macro in intmacros:
        if macro.intercept_responses:
            # We copy so that changes to request.response doesn't mangle the original response
            request.response = request.response.copy()
            if macro.async_rsp:
                request.response = yield macro.async_mangle_response(request)
            else:
                request.response = macro.mangle_response(request)

            if request.response is None:
                defer.returnValue(True)

    mangled = False
    if not old_rsp == request.response:
        request.response.rspid = old_rsp
        old_rsp.rspid = None
        request.response.unmangled = old_rsp
        request.response.unmangled.is_unmangled_version = True
        mangled = True
    else:
        request.response = old_rsp
    defer.returnValue(mangled)

@defer.inlineCallbacks
def mangle_websocket_message(message, request, intmacros):
    # Mangle messages with list of intercepting macros
    if not intmacros:
        defer.returnValue((message, False))

    cur_msg = message.copy()
    for macro in intmacros:
        if macro.intercept_ws:
            if macro.async_ws:
                cur_msg = yield macro.async_mangle_ws(request, cur_msg.copy())
            else:
                cur_msg = macro.mangle_ws(request, cur_msg.copy())

            if cur_msg is None:
                defer.returnValue((None, True))

    mangled = False
    if not cur_msg == message:
        # copy unique data to new request and clear it off old one
        cur_msg.unmangled = message
        cur_msg.unmangled.is_unmangled_version = True
        mangled = True
    else:
        # return the original request
        cur_msg = message
    defer.returnValue((cur_msg, mangled))
