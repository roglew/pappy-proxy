"""
This module contains all the api calls written for use in plugins. If you want
to do anything that is't allowed through these function calls or through the
functions provided for macros, contact me and I'll see what I can do to add some
more functionality into the next version.
"""

import glob
import imp
import os
import pappyproxy
import stat

from .proxy import add_intercepting_macro as proxy_add_intercepting_macro
from .proxy import remove_intercepting_macro as proxy_remove_intercepting_macro
from .util import PappyException

class Plugin(object):

    def __init__(self, cmd, fname=None):
        self.cmd = cmd
        self.filename = ''
        self.source = None
        self.module_name = ''

        if fname:
            self.filename = fname
            self.load_file(fname)

    def load_file(self, fname):
        module_name = os.path.basename(os.path.splitext(fname)[0])
        if os.path.basename(fname) == '__init__.py':
            return
        st = os.stat(fname)
        if (st.st_mode & stat.S_IWOTH):
            raise PappyException("Refusing to load world-writable plugin: %s" % fname)
        self.source = imp.load_source('%s'%module_name, fname)
        if hasattr(self.source, 'load_cmds'):
            self.source.load_cmds(self.cmd)
        else:
            print ('WARNING: %s does not define load_cmds. It will not be '
                   'possible to interact with the plugin through the console.' % fname)
        self.module_name = module_name
            

class PluginLoader(object):

    def __init__(self, cmd):
        self.cmd = cmd
        self.loaded_plugins = []
        self.plugins_by_name = {}

    def load_plugin(self, fname):
        p = Plugin(self.cmd, fname)
        self.loaded_plugins.append(p)
        self.plugins_by_name[p.module_name] = p

    def load_directory(self, directory):
        fnames = glob.glob(os.path.join(directory, '*.py'))
        for fname in fnames:
            try:
                self.load_plugin(fname)
            except PappyException as e:
                print str(e)
                           
##########################
## Plugin helper functions

def plugin_by_name(name):
    """
    Returns an interface to access the methods of a plugin from its name.
    For example, to call the ``foo`` function from the ``bar`` plugin
    you would call ``plugin_by_name('bar').foo()``.
    """
    import pappyproxy.pappy
    if name in pappyproxy.pappy.plugin_loader.plugins_by_name:
        return pappyproxy.pappy.plugin_loader.plugins_by_name[name].source
    else:
        raise PappyException('No plugin with name %s is loaded' % name)
    
def add_intercepting_macro(name, macro):
    """
    Adds an intercepting macro to the proxy. You can either use a
    :class:`pappyproxy.macros.FileInterceptMacro` to load an intercepting macro
    from the disk, or you can create your own using an :class:`pappyproxy.macros.InterceptMacro`
    for a base class. You must give a unique name that will be used in
    :func:`pappyproxy.plugin.remove_intercepting_macro` to deactivate it. Remember
    that activating an intercepting macro will disable request streaming and will
    affect performance. So please try and only use this if you may need to modify
    messages before they are passed along.
    """
    proxy_add_intercepting_macro(name, macro, pappyproxy.pappy.server_factory.intercepting_macros)
    
def remove_intercepting_macro(name):
    """
    Stops an active intercepting macro. You must pass in the name that you used
    when calling :func:`pappyproxy.plugin.add_intercepting_macro` to identify
    which macro you would like to stop.
    """
    proxy_remove_intercepting_macro(name, pappyproxy.pappy.server_factory.intercepting_macros)
    
def active_intercepting_macros():
    """
    Returns a list of the active intercepting macro objects. Modifying this list
    will not affect which macros are active.
    """
    return pappyproxy.pappy.server_factory.intercepting_macros[:]

def in_memory_reqs():
    """
    Returns a list containing all out of the requests which exist in memory only
    (requests with an m## style id).
    You can call either :func:`pappyproxy.http.Request.save` or 
    :func:`pappyproxy.http.Request.async_save` to save the request to the data file.
    """
    return list(pappyproxy.context.Context.in_memory_requests)

def all_reqs():
    """
    Returns a list containing all the requests in history (including requests
    that only exist in memory). Modifying this list will not modify requests
    included in the history. However, you can edit the requests
    in this list then call either :func:`pappyproxy.http.Request.save` or 
    :func:`pappyproxy.http.Request.async_save` to modify the actual request.
    """
    return list(pappyproxy.context.Context.all_reqs)

def main_context():
    """
    Returns the context object representing the main context. Use this to interact
    with the context. The returned object can be modified
    at will. Avoid modifying any class values (ie all_reqs, in_memory_requests)
    and use the class methods to add/remove requests. See the documentation on
    :class:`pappyproxy.context.Context` for more information.
    """
    return pappyproxy.pappy.main_context

def add_req(req):
    """
    Adds a request to the history. Will not do anything to requests which are
    already in history. If the request is not saved, it will be given an m## id.
    """
    pappyproxy.pappy.main_context.add_request(req)

def run_cmd(cmd):
    """
    Run a command as if you typed it into the console. Try and use existing APIs
    to do what you want before using this.
    """
    pappyproxy.pappy.cons.onecmd(cmd)
