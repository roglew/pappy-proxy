import glob
import imp
import os
import random
import re
import stat
from jinja2 import Environment, FileSystemLoader
from collections import namedtuple

from .proxy import InterceptMacro

class MacroException(Exception):
    pass

class FileInterceptMacro(InterceptMacro):
    """
    An intercepting macro that loads a macro from a file.
    """
    def __init__(self, client, filename=''):
        InterceptMacro.__init__(self)
        self.name = '' # name from the file
        self.file_name = filename or '' # filename we load from
        self.source = None
        self.client = client

        if self.file_name:
            self.load()

    def __repr__(self):
        s = self.name
        names = []
        names.append(self.file_name)
        s += ' (%s)' % ('/'.join(names))
        return "<InterceptingMacro %s>" % s

    def load(self):
        if self.file_name:
            match = re.findall('.*int_(.*).py$', self.file_name)
            self.name = match[0]
                
            # yes there's a race condition here, but it's better than nothing
            st = os.stat(self.file_name)
            if (st.st_mode & stat.S_IWOTH):
                raise MacroException("Refusing to load world-writable macro: %s" % self.file_name)
            module_name = os.path.basename(os.path.splitext(self.file_name)[0])
            self.source = imp.load_source('%s'%module_name, self.file_name)
        else:
            self.source = None

        # Update what we can do
        if self.source and hasattr(self.source, 'mangle_request'):
           self.intercept_requests = True
        else:
           self.intercept_requests = False

        if self.source and hasattr(self.source, 'mangle_response'):
            self.intercept_responses = True
        else:
            self.intercept_responses = False

        if self.source and hasattr(self.source, 'mangle_websocket'):
            self.intercept_ws = True
        else:
            self.intercept_ws = False

    def init(self, args):
        if hasattr(self.source, 'init'):
            self.source.init(self.client, args)

    def mangle_request(self, request):
        if hasattr(self.source, 'mangle_request'):
            return self.source.mangle_request(self.client, request)
        return request

    def mangle_response(self, request, response):
        if hasattr(self.source, 'mangle_response'):
            return self.source.mangle_response(self.client, request, response)
        return response

    def mangle_websocket(self, request, response, message):
        if hasattr(self.source, 'mangle_websocket'):
            return self.source.mangle_websocket(self.client, request, response, message)
        return message

class MacroFile:
    """
    A class representing a file that can be executed to automate actions
    """

    def __init__(self, filename=''):
        self.name = '' # name from the file
        self.file_name = filename or '' # filename we load from
        self.source = None

        if self.file_name:
            self.load()

    def load(self):
        if self.file_name:
            match = re.findall('.*macro_(.*).py$', self.file_name)
            self.name = match[0]
            st = os.stat(self.file_name)
            if (st.st_mode & stat.S_IWOTH):
                raise MacroException("Refusing to load world-writable macro: %s" % self.file_name)
            module_name = os.path.basename(os.path.splitext(self.file_name)[0])
            self.source = imp.load_source('%s'%module_name, self.file_name)
        else:
            self.source = None

    def execute(self, client, args):
        # Execute the macro
        if self.source:
            self.source.run_macro(client, args)

MacroTemplateData = namedtuple("MacroTemplateData", ["filename", "description", "argdesc", "fname_fmt"])
            
class MacroTemplate(object):
    _template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "templates")
    _template_data = {
        'macro': MacroTemplateData('macro.py.tmpl',
                                   'Generic macro template',
                                   '[reqids]',
                                   'macro_{fname}.py'),

        'intmacro': MacroTemplateData('intmacro.py.tmpl',
                                      'Generic intercepting macro template',
                                      '[reqids]',
                                      'int_{fname}.py'),
    }

    @classmethod
    def fill_template(cls, template, subs):
        loader = FileSystemLoader(cls._template_dir)
        env = Environment(loader=loader)
        template = env.get_template(cls._template_data[template].filename)
        return template.render(zip=zip, **subs)

    @classmethod
    def template_filename(cls, template, fname):
        return cls._template_data[template].fname_fmt.format(fname=fname)

    @classmethod
    def template_names(cls):
        for k, v in cls._template_data.iteritems():
            yield k
    
    @classmethod
    def template_description(cls, template):
        return cls._template_data[template].description

    @classmethod
    def template_argstring(cls, template):
        return cls._template_data[template].argdesc

## Other functions

def load_macros(loc, client):
    """
    Loads the macros stored in the location and returns a list of Macro objects
    """
    macro_files = glob.glob(loc + "/macro_*.py")
    macro_objs = []
    for f in macro_files:
        macro_objs.append(MacroFile(f))

    int_macro_files = glob.glob(loc + "/int_*.py")
    int_macro_objs = []
    for f in int_macro_files:
        int_macro_objs.append(FileInterceptMacro(client, filename=f))
    return (macro_objs, int_macro_objs)

def macro_from_requests(reqs, template='macro'):
    # Generates a macro that defines request objects for each of the requests
    # in reqs
    subs = {}

    req_lines = []
    req_params = []
    for req in reqs:
        lines = req.full_message().splitlines(True)
        #esclines = [line.encode('unicode_escape') for line in lines]
        esclines = [line for line in lines]
        req_lines.append(esclines)

        params = []
        params.append('dest_host="{}"'.format(req.dest_host))
        params.append('dest_port={}'.format(req.dest_port))
        params.append('use_tls={}'.format(req.use_tls))
        req_params.append(', '.join(params))
    subs['req_lines'] = req_lines
    subs['req_params'] = req_params

    return MacroTemplate.fill_template(template, subs)

# @defer.inlineCallbacks
# def mangle_request(request, intmacros):
#     """
#     Mangle a request with a list of intercepting macros.
#     Returns a tuple that contains the resulting request (with its unmangled
#     value set if needed) and a bool that states whether the request was modified
#     Returns (None, True) if the request was dropped.
    
#     :rtype: (Request, Bool)
#     """
#     # Mangle requests with list of intercepting macros
#     if not intmacros:
#         defer.returnValue((request, False))

#     cur_req = request.copy()
#     for macro in intmacros:
#         if macro.intercept_requests:
#             if macro.async_req:
#                 cur_req = yield macro.async_mangle_request(cur_req.copy())
#             else:
#                 cur_req = macro.mangle_request(cur_req.copy())

#             if cur_req is None:
#                 defer.returnValue((None, True))

#     mangled = False
#     if not cur_req == request or \
#        not cur_req.host == request.host or \
#        not cur_req.port == request.port or \
#        not cur_req.is_ssl == request.is_ssl:
#         # copy unique data to new request and clear it off old one
#         cur_req.unmangled = request
#         cur_req.unmangled.is_unmangled_version = True
#         if request.response:
#             cur_req.response = request.response
#             request.response = None
#         mangled = True
#     else:
#         # return the original request
#         cur_req = request
#     defer.returnValue((cur_req, mangled))

# @defer.inlineCallbacks
# def mangle_response(request, intmacros):
#     """
#     Mangle a request's response with a list of intercepting macros.
#     Returns a bool stating whether the request's response was modified.
#     Unmangled values will be updated as needed.
    
#     :rtype: Bool
#     """
#     if not intmacros:
#         defer.returnValue(False)

#     old_rsp = request.response
#     for macro in intmacros:
#         if macro.intercept_responses:
#             # We copy so that changes to request.response doesn't mangle the original response
#             request.response = request.response.copy()
#             if macro.async_rsp:
#                 request.response = yield macro.async_mangle_response(request)
#             else:
#                 request.response = macro.mangle_response(request)

#             if request.response is None:
#                 defer.returnValue(True)

#     mangled = False
#     if not old_rsp == request.response:
#         request.response.rspid = old_rsp
#         old_rsp.rspid = None
#         request.response.unmangled = old_rsp
#         request.response.unmangled.is_unmangled_version = True
#         mangled = True
#     else:
#         request.response = old_rsp
#     defer.returnValue(mangled)

# @defer.inlineCallbacks
# def mangle_websocket_message(message, request, intmacros):
#     # Mangle messages with list of intercepting macros
#     if not intmacros:
#         defer.returnValue((message, False))

#     cur_msg = message.copy()
#     for macro in intmacros:
#         if macro.intercept_ws:
#             if macro.async_ws:
#                 cur_msg = yield macro.async_mangle_ws(request, cur_msg.copy())
#             else:
#                 cur_msg = macro.mangle_ws(request, cur_msg.copy())

#             if cur_msg is None:
#                 defer.returnValue((None, True))

#     mangled = False
#     if not cur_msg == message:
#         # copy unique data to new request and clear it off old one
#         cur_msg.unmangled = message
#         cur_msg.unmangled.is_unmangled_version = True
#         mangled = True
#     else:
#         # return the original request
#         cur_msg = message
#     defer.returnValue((cur_msg, mangled))
