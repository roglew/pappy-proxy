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
import crochet

from twisted.internet import defer
from .colors import Colors
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
    Returns an interface to access the methods of a plugin from its
    name.  For example, to call the ``foo`` function from the ``bar``
    plugin you would call ``plugin_by_name('bar').foo()``.
    """
    import pappyproxy.pappy
    if name in pappyproxy.pappy.plugin_loader.plugins_by_name:
        return pappyproxy.pappy.plugin_loader.plugins_by_name[name].source
    else:
        raise PappyException('No plugin with name %s is loaded' % name)
    
def add_intercepting_macro(name, macro):
    """
    Adds an intercepting macro to the proxy. You can either use a
    :class:`pappyproxy.macros.FileInterceptMacro` to load an
    intercepting macro from the disk, or you can create your own using
    an :class:`pappyproxy.macros.InterceptMacro` for a base class. You
    must give a unique name that will be used in
    :func:`pappyproxy.plugin.remove_intercepting_macro` to deactivate
    it. Remember that activating an intercepting macro will disable
    request streaming and will affect performance. So please try and
    only use this if you may need to modify messages before they are
    passed along.
    """
    for factory in pappyproxy.pappy.session.server_factories:
        factory.add_intercepting_macro(macro, name=name)
    
def remove_intercepting_macro(name):
    """
    Stops an active intercepting macro. You must pass in the name that
    you used when calling
    :func:`pappyproxy.plugin.add_intercepting_macro` to identify which
    macro you would like to stop.
    """
    for factory in pappyproxy.pappy.session.server_factories:
        factory.remove_intercepting_macro(name=name)
    
def active_intercepting_macros():
    """
    Returns a dict of the active intercepting macro objects. Modifying
    this list will not affect which macros are active.
    """
    # every factory should have the same int macros so screw it we'll
    # just use the macros from the first one
    ret = []
    if len(pappyproxy.pappy.session.server_factories) > 0:
        ret = pappyproxy.pappy.session.server_factories[0].get_macro_list()
    return ret

def in_memory_reqs():
    """
    Returns a list containing the ids of the requests which exist in
    memory only (requests with an m## style id).  You can call either
    :func:`pappyproxy.http.Request.save` or
    :func:`pappyproxy.http.Request.async_deep_save` to save the
    request to the data file.
    """
    return list(pappyproxy.http.Request.cache.inmem_reqs)

def req_history(num=-1, ids=None, include_unmangled=False):
    """
    Returns an a generator that generates deferreds which resolve to
    requests in history, ignoring the current context.  If ``n`` is
    given, it will stop after ``n`` requests have been generated.  If
    ``ids`` is given, it will only include those IDs. If
    ``include_unmangled`` is True, then the iterator will include
    requests which are the unmangled version of other requests.

    An example of using the iterator to print the 10 most recent requests::

        @defer.inlineCallbacks
        def find_food():
            for req_d in req_history(10):
                req = yield req_d
                print '-'*10
                print req.full_message_pretty
    """
    return pappyproxy.Request.cache.req_it(num=num, ids=ids, include_unmangled=include_unmangled)

def async_main_context_ids(n=-1):
    """
    Returns a deferred that resolves into a list of up to ``n`` of the
    most recent requests in the main context.  You can then use
    :func:`pappyproxy.http.Request.load_request` to load the requests
    in the current context. If no value is passed for ``n``, this will
    return all of the IDs in the context.
    """
    return pappyproxy.pappy.main_context.get_reqs(n)

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def main_context_ids(*args, **kwargs):
    """
    Same as :func:`pappyproxy.plugin.async_main_context_ids` but can be called
    from macros and other non-async only functions. Cannot be called in async
    functions.
    """
    ret = yield async_main_context_ids(*args, **kwargs)
    defer.returnValue(ret)
    
def add_to_history(req):
    """
    Save a request to history without saving it to the data file. The request
    will only be saved in memory, so when the program is exited or `clrmem`
    is run, the request will be deleted.

    :param req: The request to add to history
    :type req: :class:`pappyproxy.http.Request`
    """
    pappyproxy.http.Request.cache.add(req)
    pappyproxy.context.reset_context_caches()

def get_active_filter_strings():
    """
    Returns a list of filter strings representing the currently active filters
    """
    filts = pappyproxy.pappy.main_context.active_filters
    strs = []
    for f in filts:
        strs.append(f.filter_string)
    return strs

def run_cmd(cmd):
    """
    Run a command as if you typed it into the console. Try and use
    existing APIs to do what you want before using this.
    """
    pappyproxy.pappy.cons.onecmd(cmd)

def require_modules(*largs):
    """
    A wrapper to make sure that plugin dependencies are installed. For example,
    if a command requires the ``psutil`` and ``objgraph`` package, you should
    format your command like::

        @require_modules('psutil', 'objgraph')
        def my_command(line):
            import objgraph
            import psutil
            # ... rest of command ...

    If you try to run the command without being able to import all of the required
    modules, the command will print an error and not run the command.
    """
    def wr(func):
        def wr2(*args, **kwargs):
            missing = []
            for l in largs:
                try:
                    imp.find_module(l)
                except ImportError:
                    missing.append(l)
            if missing:
                print 'Command requires %s module(s)' % (', '.join([Colors.RED+m+Colors.ENDC for m in missing]))
            else:
                return func(*args, **kwargs)
        return wr2
    return wr

def set_context_to_saved(name):
    """
    Sets the current context to the context saved under the given name.
    Raises PappyException if name does not exist
    """

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def delete_saved_context(name):
    """
    Deletes the saved context with the given name.
    Raises PappyException if name does not exist
    """
    
def save_current_context(name):
    """
    Saves the current context under the given name.
    """
    
def save_context(name, filter_strs):
    """
    Takes a list of filter strings and saves it as a context under the given name.
    
    :param name: The name to save the context under
    :type name: string
    :param filter_strs: The in-order list of filter strings of the context to save.
    :type filter_strs: List of strings
    """
