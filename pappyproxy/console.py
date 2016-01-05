import cmd2
import crochet
import curses
import datetime
import os
import pappyproxy
import pygments
import re
import shlex
import string
import subprocess
import sys
import termios
import time
import urllib

from twisted.internet import defer, reactor
from pappyproxy.util import PappyException
from pappyproxy.macros import load_macros, macro_from_requests, gen_imacro
from pappyproxy.repeater import start_editor
from pygments.lexers import get_lexer_for_mimetype
from pygments.lexers import HttpLexer
from pygments.formatters import TerminalFormatter

"""
console.py

Functions and classes involved with interacting with console input and output
"""

# http://www.termsys.demon.co.uk/vtansi.htm#cursor
SAVE_CURSOR = '\x1b[7'
UNSAVE_CURSOR = '\x1b[8'
LINE_UP = '\x1b[1A'
LINE_ERASE = '\x1b[2K'
PRINT_LINE = '\x1b[1i'

edit_queue = []
loaded_macros = []
loaded_int_macros = []
macro_dict = {}
int_macro_dict = {}
proxy_server_factory = None

def print_pappy_errors(func):
    def catch(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except PappyException as e:
            print str(e)
    return catch

def set_proxy_server_factory(factory):
    global proxy_server_factory
    proxy_server_factory = factory

class ProxyCmd(cmd2.Cmd):

    def __init__(self, *args, **kwargs):
        self.alerts = []
        self.prompt = 'itsPappyTime> '
        self.debug = True
        cmd2.Cmd.__init__(self, *args, **kwargs)
        
    def add_alert(self, alert):
        self.alerts.append(alert)

    def postcmd(self, stop, line):
        for l in self.alerts:
            print '[!] ', l
        self.alerts = []
        return stop

    def help_view_request_headers(self):
        print ("View information about request\n"
               "Usage: view_request_info <reqid> [u]"
               "If 'u' is given as an additional argument, the unmangled version "
               "of the request will be displayed.")

    @print_pappy_errors
    @crochet.wait_for(timeout=None)
    @defer.inlineCallbacks
    def do_view_request_info(self, line):
        args = shlex.split(line)
        reqids = args[0]

        reqs = yield load_reqlist(reqids)

        for req in reqs:
            print ''
            print_request_extended(req)
        print ''

    def help_view_request_headers(self):
        print ("View the headers of the request\n"
               "Usage: view_request_headers <reqid> [u]"
               "If 'u' is given as an additional argument, the unmangled version "
               "of the request will be displayed.")

    @print_pappy_errors
    @crochet.wait_for(timeout=None)
    @defer.inlineCallbacks
    def do_view_request_headers(self, line):
        args = shlex.split(line)
        reqid = args[0]
        showid = reqid

        reqs = yield load_reqlist(reqid)
        for req in reqs:
            if len(reqs) > 1:
                print 'Request %s:' % req.reqid
            print ''
            view_full_request(req, True)
            if len(reqs) > 1:
                print '-'*30

    def help_view_full_request(self):
        print ("View the full data of the request\n"
               "Usage: view_full_request <reqid> [u]\n"
               "If 'u' is given as an additional argument, the unmangled version "
               "of the request will be displayed.")

    @print_pappy_errors
    @crochet.wait_for(timeout=None)
    @defer.inlineCallbacks
    def do_view_full_request(self, line):
        args = shlex.split(line)
        reqid = args[0]
        showid = reqid

        reqs = yield load_reqlist(reqid)
        for req in reqs:
            if len(reqs) > 1:
                print 'Request %s:' % req.reqid
            print ''
            view_full_request(req)
            if len(reqs) > 1:
                print '-'*30

    def help_view_response_headers(self):
        print ("View the headers of the response\n"
               "Usage: view_response_headers <reqid>")

    @print_pappy_errors
    @crochet.wait_for(timeout=None)
    @defer.inlineCallbacks
    def do_view_response_headers(self, line):
        reqs = yield load_reqlist(line)
        for req in reqs:
            if req.response:
                if len(reqs) > 1:
                    print '-'*15 + (' %s ' % req.reqid)  + '-'*15
                view_full_response(req.response, True)
            else:
                print "Request %s does not have a response" % req.reqid

    def help_view_full_response(self):
        print ("View the full data of the response associated with a request\n"
               "Usage: view_full_response <reqid>")

    @print_pappy_errors
    @crochet.wait_for(timeout=None)
    @defer.inlineCallbacks
    def do_view_full_response(self, line):
        reqs = yield load_reqlist(line)
        for req in reqs:
            if req.response:
                if len(reqs) > 1:
                    print '-'*15 + (' %s ' % req.reqid)  + '-'*15
                view_full_response(req.response)
            else:
                print "Request %s does not have a response" % req.reqid

    def help_dump_response(self):
        print ('Dump the data of the response to a file.\n'
               'Usage: dump_response <id> <filename>')
        
    @print_pappy_errors
    @crochet.wait_for(timeout=None)
    @defer.inlineCallbacks
    def do_dump_response(self, line):
        # dump the data of a response
        args = shlex.split(line)
        reqid = args[0]
        showid = reqid
        req = yield pappyproxy.http.Request.load_request(reqid)
        rsp = req.response
        if len(args) >= 2:
            fname = args[1]
        else:
            fname = req.path.split('/')[-1]

        with open(fname, 'w') as f:
            f.write(rsp.raw_data)
        print 'Response data written to %s' % fname

    def help_list(self):
        print ("List request/response pairs in the current context\n"
               "Usage: list")

    @print_pappy_errors
    def do_list(self, line):
        args = shlex.split(line)
        if len(args) > 0:
            if args[0][0].lower() == 'a':
                print_count = -1
            else:
                try:
                    print_count = int(args[0])
                except:
                    print "Please enter a valid argument for list"
                    return
        else:
            print_count = 25
        
        def key_reqtime(req):
            if req.time_start is None:
                return -1
            else:
                return (req.time_start-datetime.datetime(1970,1,1)).total_seconds()

        to_print = list(pappyproxy.context.active_requests)
        to_print = sorted(to_print, key=key_reqtime, reverse=True)
        if print_count > 0:
            to_print = to_print[:print_count]
        print_requests(to_print)

    def help_site_map(self):
        print ('Print the site map. Only includes requests in the current context.\n'
               'Usage: site_map')
        
    @print_pappy_errors
    def do_site_map(self, line):
        to_print = [r for r in pappyproxy.context.active_requests if not r.response or r.response.response_code != 404]
        tree = get_site_map(to_print)
        print_tree(tree)

    def help_filter(self):
        print ("Apply a filter to the current context\n"
               "Usage: filter <filter string>\n"
               "See README.md for information on filter strings")

    @print_pappy_errors
    def do_filter(self, line):
        if not line:
            raise PappyException("Filter string required")
        
        filter_to_add = pappyproxy.context.Filter(line)
        pappyproxy.context.add_filter(filter_to_add)

    def complete_builtin_filter(self, text, line, begidx, endidx):
        all_names = pappyproxy.context.BuiltinFilters.list()
        if not text:
            ret = all_names[:]
        else:
            ret = [n for n in all_names if n.startswith(text)]
        return ret
        
    @print_pappy_errors
    def do_builtin_filter(self, line):
        if not line:
            raise PappyException("Filter name required")
        
        filters_to_add = pappyproxy.context.BuiltinFilters.get(line)
        for f in filters_to_add:
            print f.filter_string
            pappyproxy.context.add_filter(f)

    def help_filter_up(self):
        print ("Remove the last applied filter\n"
               "Usage: filter_up")

    @print_pappy_errors
    def do_filter_up(self, line):
        pappyproxy.context.filter_up()

    def help_filter_clear(self):
        print ("Reset the context so that it contains no filters (ignores scope)\n"
               "Usage: filter_clear")

    @print_pappy_errors
    @crochet.wait_for(timeout=None)
    @defer.inlineCallbacks
    def do_filter_clear(self, line):
        pappyproxy.context.active_filters = []
        yield pappyproxy.context.reload_from_storage()

    def help_filter_list(self):
        print ("Print the filters that make up the current context\n"
               "Usage: filter_list")

    @print_pappy_errors
    def do_filter_list(self, line):
        for f in pappyproxy.context.active_filters:
            print f.filter_string


    def help_scope_save(self):
        print ("Set the scope to be the current context. Saved between launches\n"
               "Usage: scope_save")

    @print_pappy_errors
    @crochet.wait_for(timeout=None)
    @defer.inlineCallbacks
    def do_scope_save(self, line):
        pappyproxy.context.save_scope()
        yield pappyproxy.context.store_scope(pappyproxy.http.dbpool)

    def help_scope_reset(self):
        print ("Set the context to be the scope (view in-scope items)\n"
               "Usage: scope_reset")

    @print_pappy_errors
    def do_scope_reset(self, line):
        pappyproxy.context.reset_to_scope()

    def help_scope_delete(self):
        print ("Delete the scope so that it contains all request/response pairs\n"
               "Usage: scope_delete")        

    @print_pappy_errors
    @crochet.wait_for(timeout=None)
    @defer.inlineCallbacks
    def do_scope_delete(self, line):
        pappyproxy.context.set_scope([])
        yield pappyproxy.context.store_scope(pappyproxy.http.dbpool)

    def help_scope_list(self):
        print ("Print the filters that make up the scope\n"
               "Usage: scope_list")

    @print_pappy_errors
    def do_scope_list(self, line):
        pappyproxy.context.print_scope()

    def help_filter_prune(self):
        print ('Delete all out of context requests from the data file. '
               'CANNOT BE UNDONE!! Be careful!\n'
               'Usage: filter_prune')

    @print_pappy_errors
    @crochet.wait_for(timeout=None)
    @defer.inlineCallbacks
    def do_filter_prune(self, line):
        # Delete filtered items from datafile
        print ''
        print 'Currently active filters:'
        for f in pappyproxy.context.active_filters:
            print '> %s' % f.filter_string

        # We copy so that we're not removing items from a set we're iterating over
        reqs = list(pappyproxy.context.inactive_requests)
        act_reqs = list(pappyproxy.context.active_requests)
        message = 'This will delete %d/%d requests. You can NOT undo this!! Continue?' % (len(reqs), (len(reqs) + len(act_reqs)))
        if not confirm(message, 'n'):
            defer.returnValue(None)
        
        for r in reqs:
            yield r.deep_delete()
            pappyproxy.context.remove_request(r)
        print 'Deleted %d requests' % len(reqs)
        defer.returnValue(None)
        
    def help_clrmem(self):
        print ('Delete all in-memory only requests'
               'Usage: clrmem')
        
    def do_clrmem(self, line):
        to_delete = list(pappyproxy.context.in_memory_requests)
        for r in to_delete:
            pappyproxy.context.remove_request(r)

    def help_repeater(self):
        print ("Open a request in the repeater\n"
               "Usage: repeater <reqid>")

    @print_pappy_errors
    def do_repeater(self, line):
        # This is not async on purpose. start_editor acts up if this is called
        # with inline callbacks. As a result, check_reqid and get_unmangled
        # cannot be async
        args = shlex.split(line)
        reqid = args[0]

        check_reqid(reqid)
        start_editor(reqid)

    def help_intercept(self):
        print ("Intercept requests and/or responses and edit them with before passing them along\n"
               "Usage: intercept <reqid>")

    @print_pappy_errors
    def do_intercept(self, line):
        global edit_queue
        global proxy_server_factory
        args = shlex.split(line)
        intercept_requests = False
        intercept_responses = False

        req_names = ('req', 'request', 'requests')
        rsp_names = ('rsp', 'response', 'responses')

        if any(a in req_names for a in args):
            intercept_requests = True
        if any(a in rsp_names for a in args):
            intercept_responses = True

        if intercept_requests and intercept_responses:
            intercept_str = 'Requests and responses'
        elif intercept_requests:
            intercept_str = 'Requests'
        elif intercept_responses:
            intercept_str = 'Responses'
        else:
            intercept_str = 'NOTHING'

        macro_file = os.path.join(pappyproxy.config.PAPPY_DIR, 'mangle.py')
        mangle_macro = pappyproxy.macros.InterceptMacro(macro_file)
        mangle_macro.intercept_requests = intercept_requests
        mangle_macro.intercept_responses = intercept_responses

        pappyproxy.proxy.add_intercepting_macro('pappy_intercept', mangle_macro,
                                                proxy_server_factory.intercepting_macros)

        ## Interceptor loop
        stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()

        try:
            editnext = False
            stdscr.nodelay(True)
            while True:
                stdscr.addstr(0, 0, "Currently intercepting: %s" % intercept_str)
                stdscr.clrtoeol()
                stdscr.addstr(1, 0, "%d item(s) in queue." % len(edit_queue))
                stdscr.clrtoeol()
                if editnext:
                    stdscr.addstr(2, 0, "Waiting for next item... Press 'q' to quit or 'b' to quit waiting")
                else:
                    stdscr.addstr(2, 0, "Press 'n' to edit the next item or 'q' to quit interceptor.")
                stdscr.clrtoeol()

                c = stdscr.getch()
                if c == ord('q'):
                    break
                elif c == ord('n'):
                    editnext = True
                elif c == ord('b'):
                    editnext = False

                if editnext and edit_queue:
                    editnext = False
                    (to_edit, deferred) = edit_queue.pop(0)
                    editor = 'vi'
                    if 'EDITOR' in os.environ:
                        editor = os.environ['EDITOR']
                    subprocess.call([editor, to_edit])
                    stdscr.clear()
                    deferred.callback(None)
        finally:
            curses.nocbreak()
            stdscr.keypad(0)
            curses.echo()
            curses.endwin()
            try:
                pappyproxy.proxy.remove_intercepting_macro('pappy_intercept',
                                                           proxy_server_factory.intercepting_macros)
            except PappyException:
                pass
            # Send remaining requests along
            while len(edit_queue) > 0:
                (fname, deferred) = edit_queue.pop(0)
                deferred.callback(None)
                
    def help_load_macros(self, line):
        print ('Load macros from a directory. By default loads macros in the current directory.\n'
               'Usage: load_macros [dir]')
                
    @print_pappy_errors
    def do_load_macros(self, line):
        global macro_dict
        global int_macro_dict
        global loaded_macros
        global loaded_int_macros

        if line:
            load_dir = line
        else:
            load_dir = '.'
        (to_load, int_to_load) = load_macros(load_dir)
        if not to_load and not int_to_load:
            raise PappyException('No macros to load.')

        macro_dict = {}
        loaded_macros = []
        int_macro_dict = {}
        loaded_int_macros = []

        for macro in to_load:
            if macro.name in macro_dict:
                print 'Name conflict in %s! "%s" already in use, not loading.' % (macro.filename, macro.name)
            elif macro.short_name and macro.short_name in macro_dict:
                print 'Name conflict in %s! "%s" already in use, not loading.' % (macro.filename, macro.short_name)
            elif macro.file_name in macro_dict:
                print 'Name conflict in %s! "%s" already in use, not loading.' % (macro.filename, macro.file_name)
            else:
                macro_dict[macro.name] = macro
                macro_dict[macro.file_name] = macro
                if macro.short_name:
                    macro_dict[macro.short_name] = macro
                loaded_macros.append(macro)
                print 'Loaded "%s"' % macro

        for macro in int_to_load:
            if macro.name in int_macro_dict:
                print 'Name conflict in %s! "%s" already in use, not loading.' % (macro.filename, macro.name)
            elif macro.short_name and macro.short_name in int_macro_dict:
                print 'Name conflict in %s! "%s" already in use, not loading.' % (macro.filename, macro.short_name)
            elif macro.file_name in int_macro_dict:
                print 'Name conflict in %s! "%s" already in use, not loading.' % (macro.filename, macro.file_name)
            else:
                int_macro_dict[macro.name] = macro
                int_macro_dict[macro.file_name] = macro
                if macro.short_name:
                    int_macro_dict[macro.short_name] = macro
                loaded_int_macros.append(macro)
                print 'Loaded "%s"' % macro

    def help_run_macro(self):
        print ('Run a macro\n'
               'Usage: run_macro <macro name or macro short name>')
                
    @print_pappy_errors
    def do_run_macro(self, line):
        global macro_dict
        global loaded_macros
        args = shlex.split(line)
        if not args:
            raise PappyException('You must give a macro to run. You can give its short name, or the name in the filename.')
        mname = args[0]
        if mname not in macro_dict:
            raise PappyException('%s not a loaded macro' % mname)
        macro = macro_dict[mname]
        macro.execute(args[1:])

    def help_run_int_macro(self):
        print ('Activate an intercepting macro\n'
               'Usage: run_int_macro <macro name or macro short name>\n'
               'Macro can be stopped with stop_int_macro')
        
    @print_pappy_errors
    def do_run_int_macro(self, line):
        global int_macro_dict
        global loaded_int_macros
        if not line:
            raise PappyException('You must give an intercepting macro to run. You can give its short name, or the name in the filename.')
        if line not in int_macro_dict:
            raise PappyException('%s not a loaded intercepting macro' % line)
        macro = int_macro_dict[line]
        pappyproxy.proxy.add_intercepting_macro(macro.name, macro)
        print '"%s" started' % macro.name

    def help_stop_int_macro(self):
        print ('Stop a running intercepting macro\n'
               'Usage: stop_int_macro <macro name or macro short name>')
        
    @print_pappy_errors
    def do_stop_int_macro(self, line):
        global int_macro_dict
        global loaded_int_macros
        if not line:
            raise PappyException('You must give an intercepting macro to run. You can give its short name, or the name in the filename.')
        if line not in int_macro_dict:
            raise PappyException('%s not a loaded intercepting macro' % line)
        macro = int_macro_dict[line]
        pappyproxy.proxy.remove_intercepting_macro(macro.name)
        print '"%s" stopped' % macro.name

    def help_list_int_macros(self):
        print ('List all active/inactive intercepting macros')
        
    def do_list_int_macros(self, line):
        global int_macro_dict
        global loaded_int_macros
        running = []
        not_running = []
        for macro in loaded_int_macros:
            if macro.name in pappyproxy.proxy.intercepting_macros:
                running.append(macro)
            else:
                not_running.append(macro)

        if not running and not not_running:
            print 'No loaded intercepting macros'
                
        if running:
            print 'Active intercepting macros:'
            for m in running:
                print '  %s' % m

        if not_running:
            print 'Inactive intercepting macros:'
            for m in not_running:
                print '  %s' % m
        
    def do_help_generate_macro(self):
        print ('Generate a macro script with request objects'
               'Usage: generate_macro <name> <req0>, <req1>, ... <reqn>')
        
    @print_pappy_errors
    @crochet.wait_for(timeout=None)
    @defer.inlineCallbacks
    def do_generate_macro(self, line):
        if line == '':
            raise PappyException('Macro name is required')
        args = shlex.split(line)
        name = args[0]
        reqs = yield load_reqlist(args[1])
        script_str = macro_from_requests(reqs)
        fname = 'macro_%s.py' % name
        with open(fname, 'wc') as f:
            f.write(script_str)
        print 'Wrote script to %s' % fname

    def do_help_generate_macro(self):
        print ('Generate a macro script with request objects\n'
               'Usage: generate_macro <name> <req0>, <req1>, ... <reqn>')
        
    def help_generate_int_macro(self):
        print ('Generate an intercepting macro script\n'
               'Usage: generate_int_macro <name>')
        
    @print_pappy_errors
    def do_generate_int_macro(self, line):
        if line == '':
            raise PappyException('Macro name is required')
        args = shlex.split(line)
        name = args[0]
        script_str = gen_imacro()
        fname = 'int_%s.py' % name
        with open(fname, 'wc') as f:
            f.write(script_str)
        print 'Wrote script to %s' % fname

    def help_gencerts(self):
        print ("Generate CA cert and private CA file\n"
               "Usage: gencerts [/path/to/put/certs/in]")

    def help_rpy(self):
        print ('Copy python object definitions of requests.\n'
               'Usage: rpy <list of reqids>')
        
    @print_pappy_errors
    @crochet.wait_for(timeout=None)
    @defer.inlineCallbacks
    def do_rpy(self, line):
        reqs = yield load_reqlist(line)
        for req in reqs:
            print pappyproxy.macros.req_obj_def(req)

    @print_pappy_errors
    def do_inmem(self, line):
        r = pappyproxy.http.Request()
        r.status_line = 'GET /%s HTTP/1.1' % line
        r.reqid = pappyproxy.context.get_memid()
        pappyproxy.context.add_request(r)

    def help_tag(self):
        print ('Add a tag to requests.\n'
               'Usage: tag <tag> <request ids>\n'
               'You can tag as many requests as you want at the same time. If no'
               ' ids are given, the tag will be applied to all in-context requests.')
        
    @print_pappy_errors
    @crochet.wait_for(timeout=None)
    @defer.inlineCallbacks
    def do_tag(self, line):
        args = shlex.split(line)
        if len(args) == 0:
            self.help_tag()
            defer.returnValue(None)
        tag = args[0]

        if len(args) > 1:
            reqs = yield load_reqlist(args[1], False)
            ids = [r.reqid for r in reqs]
            print 'Tagging %s with %s' % (', '.join(ids), tag)
        else:
            print "Tagging all in-context requests with %s" % tag
            reqs = list(pappyproxy.context.active_requests)

        for req in reqs:
            if tag not in req.tags:
                req.tags.append(tag)
                if req.saved:
                    yield req.async_save()
                pappyproxy.context.add_request(req)
            else:
                print 'Request %s already has tag %s' % (req.reqid, tag)

    def help_untag(self):
        print ('Remove a tag from requests\n'
               'Usage: untag <tag> <request ids>\n'
               'You can provide as many request ids as you want and the tag will'
               ' be removed from all of them. If no ids are given, the tag will '
               'be removed from all in-context requests.')
                
    @print_pappy_errors
    @crochet.wait_for(timeout=None)
    @defer.inlineCallbacks
    def do_untag(self, line):
        args = shlex.split(line)
        if len(args) == 0:
            self.help_untag()
            defer.returnValue(None)
        tag = args[0]

        ids = []
        if len(args) > 1:
            reqs = yield load_reqlist(args[1], False)
            ids = [r.reqid for r in reqs]
        else:
            print "Untagging all in-context requests with tag %s" % tag
            reqs = list(pappyproxy.context.active_requests)

        for req in reqs:
            if tag in req.tags:
                req.tags.remove(tag)
                if req.saved:
                    yield req.async_save()
        if ids:
            print 'Tag %s removed from %s' % (tag, ', '.join(ids))
        pappyproxy.context.filter_recheck()
        
    def help_clrtag(self):
        print ('Clear all the tags from requests\n'
               'Usage: clrtag <request ids>')
        
    @print_pappy_errors
    @crochet.wait_for(timeout=None)
    @defer.inlineCallbacks
    def do_clrtag(self, line):
        args = shlex.split(line)
        if len(args) == 0:
            self.help_clrtag()
            defer.returnValue(None)
        reqs = yield load_reqlist(args[1], False)

        for req in reqs:
            if req.tags:
                req.tags = []
                print 'Tags cleared from request %s' % (req.reqid)
                if req.saved:
                    yield req.async_save()
        pappyproxy.context.filter_recheck()

    @print_pappy_errors
    @crochet.wait_for(timeout=None)
    @defer.inlineCallbacks
    def do_save(self, line):
        args = shlex.split(line)
        if len(args) == 0:
            self.help_save()
            defer.returnValue(None)
        reqs = yield load_reqlist(args)
        for req in reqs:
            if req.reqid[0] != 'm':
                print '%s is already saved' % req.reqid
            else:
                oldid = req.reqid
                try:
                    yield req.async_deep_save()
                    print '%s saved with id %s' % (oldid, req.reqid)
                except PappyException as e:
                    print 'Unable to save %s: %s' % (oldid, e)
        defer.returnValue(None)

    @print_pappy_errors
    @crochet.wait_for(timeout=None)
    @defer.inlineCallbacks
    def do_export(self, line):
        args = shlex.split(line)
        if len(args) < 2:
            self.help_export()
            defer.returnValue(None)

        if args[0] not in ('req', 'rsp'):
            raise PappyException('Request or response not specified')

        reqs = yield load_reqlist(args[1])
        for req in reqs:
            try:
                if args[0] == 'req':
                    fname = 'req_%s.txt'%req.reqid
                    with open(fname, 'w') as f:
                        f.write(req.full_request)
                    print 'Full request written to %s' % fname
                elif args[0] == 'rsp':
                    fname = 'rsp_%s.txt'%req.reqid
                    with open(fname, 'w') as f:
                        f.write(req.full_response)
                    print 'Full response written to %s' % fname
            except PappyException as e:
                print 'Unable to export %s: %s' % (req.reqid, e)

    @print_pappy_errors
    def do_gencerts(self, line):
        dest_dir = line or pappyproxy.config.CERT_DIR
        message = "This will overwrite any existing certs in %s. Are you sure?" % dest_dir
        if not confirm(message, 'n'):
            return False
        print "Generating certs to %s" % dest_dir
        pappyproxy.proxy.generate_ca_certs(dest_dir)

    def help_log(self):
        print ("View the log\n"
               "Usage: log [verbosity (default is 1)]\n"
               "verbosity=1: Show connections as they're made/lost, some additional info\n"
               "verbosity=3: Show full requests/responses as they are processed by the proxy")

    @print_pappy_errors
    def do_log(self, line):
        try:
            verbosity = int(line.strip())
        except:
            verbosity = 1
        pappyproxy.config.DEBUG_VERBOSITY = verbosity
        raw_input()
        pappyproxy.config.DEBUG_VERBOSITY = 0

    ## Shortcut funcs

    def help_urld(self):
        print "Url decode a string\nUsage: urld <string>"
    
    @print_pappy_errors
    def do_urld(self, line):
        print urllib.unquote(line)
        
    def help_urle(self):
        print "Url encode a string\nUsage: urle <string>"

    @print_pappy_errors
    def do_urle(self, line):
        print urllib.quote_plus(line)

    @print_pappy_errors
    def do_testerror(self, line):
        raise PappyException("Test error")

    @print_pappy_errors
    def do_EOF(self):
        print "EOF"
        return True

    ### ABBREVIATIONS
    def help_ls(self):
        self.help_list()

    @print_pappy_errors
    def do_ls(self, line):
        self.onecmd('list %s' % line)

    def help_sm(self):
        self.help_list()

    @print_pappy_errors
    def do_sm(self, line):
        self.onecmd('site_map %s' % line)

    def help_sr(self):
        self.help_scope_reset()

    @print_pappy_errors
    def do_sr(self, line):
        self.onecmd('scope_reset %s' % line)

    def help_sls(self):
        self.help_scope_list()

    @print_pappy_errors
    def do_sls(self, line):
        self.onecmd('scope_list %s' % line)

    def help_viq(self):
        self.help_view_request_info()

    @print_pappy_errors
    def do_viq(self, line):
        self.onecmd('view_request_info %s' % line)

    def help_vhq(self):
        self.help_view_request_headers()

    @print_pappy_errors
    def do_vhq(self, line):
        self.onecmd('view_request_headers %s' % line)

    def help_vfq(self):
        self.help_view_full_request()

    @print_pappy_errors
    def do_vfq(self, line):
        self.onecmd('view_full_request %s' % line)

    def help_vhs(self):
        self.help_view_response_headers()

    @print_pappy_errors
    def do_vhs(self, line):
        self.onecmd('view_response_headers %s' % line)

    def help_vfs(self):
        self.help_view_full_response()

    @print_pappy_errors
    def do_vfs(self, line):
        self.onecmd('view_full_response %s' % line)

    def help_fl(self):
        self.help_filter()

    @print_pappy_errors
    def do_fl(self, line):
        self.onecmd('filter %s' % line)

    def help_f(self):
        self.help_filter()

    @print_pappy_errors
    def do_f(self, line):
        self.onecmd('filter %s' % line)

    def help_fls(self):
        self.help_filter_list()

    @print_pappy_errors
    def do_fls(self, line):
        self.onecmd('filter_list %s' % line)

    def help_fc(self):
        self.help_filter_clear()

    @print_pappy_errors
    def do_fc(self, line):
        self.onecmd('filter_clear %s' % line)

    def help_fbi(self):
        self.help_filter()

    def help_fu(self):
        self.help_filter_up()

    @print_pappy_errors
    def do_fu(self, line):
        self.onecmd('filter_up %s' % line)

    def complete_fbi(self, *args, **kwargs):
        return self.complete_builtin_filter(*args, **kwargs)
        
    @print_pappy_errors
    def do_fbi(self, line):
        self.onecmd('builtin_filter %s' % line)

    def help_rp(self):
        self.help_repeater()

    @print_pappy_errors
    def do_rp(self, line):
        self.onecmd('repeater %s' % line)

    def help_ic(self):
        self.help_intercept()

    @print_pappy_errors
    def do_ic(self, line):
        self.onecmd('intercept %s' % line)

    def help_rma(self):
        self.help_run_macro()

    @print_pappy_errors
    def do_rma(self, line):
        self.onecmd('run_macro %s' % line)

    def help_rim(self):
        self.help_run_int_macro()

    @print_pappy_errors
    def do_rim(self, line):
        self.onecmd('run_int_macro %s' % line)

    def help_sim(self):
        self.help_stop_int_macro()

    @print_pappy_errors
    def do_sim(self, line):
        self.onecmd('stop_int_macro %s' % line)

    def help_lim(self):
        self.help_list_int_macros()

    @print_pappy_errors
    def do_lim(self, line):
        self.onecmd('list_int_macros %s' % line)

    def help_lma(self):
        self.help_load_macros()

    @print_pappy_errors
    def do_lma(self, line):
        self.onecmd('load_macros %s' % line)

    def help_gma(self, line):
        self.help_generate_macro()

    @print_pappy_errors
    def do_gma(self, line):
        self.onecmd('generate_macro %s' % line)

    def help_gima(self, line):
        self.help_generate_int_macro()

    @print_pappy_errors
    def do_gima(self, line):
        self.onecmd('generate_int_macro %s' % line)

    
def cmd_failure(cmd):
    print "FAILURE"

def edit_file(fname, front=False):
    global edit_queue
    # Adds the filename to the edit queue. Returns a deferred that is fired once
    # the file is edited and the editor is closed
    d = defer.Deferred()
    if front:
        edit_queue = [(fname, d)] + edit_queue
    else:
        edit_queue.append((fname, d))
    return d
    
def print_table(coldata, rows):
    # Coldata: List of dicts with info on how to print the columns.
    #  name: heading to give column
    #  width: (optional) maximum width before truncating. 0 for unlimited
    # Rows: List of tuples with the data to print

    # Get the width of each column
    widths = []
    headers = []
    for data in coldata:
        if 'name' in data:
            headers.append(data['name'])
        else:
            headers.append('')
    empty_headers = True
    for h in headers:
        if h != '':
            empty_headers = False
    if not empty_headers:
        rows = [headers] + rows

    for i in range(len(coldata)):
        col = coldata[i]
        if 'width' in col and col['width'] > 0:
            maxwidth = col['width']
        else:
            maxwidth = 0
        colwidth = 0
        for row in rows:
            printstr = str(row[i])
            if len(printstr) > colwidth:
                colwidth = len(printstr)
        if maxwidth > 0 and colwidth > maxwidth:
            widths.append(maxwidth)
        else:
            widths.append(colwidth)

    # Print rows
    padding = 2
    for row in rows:
        for (col, width) in zip(row, widths):
            printstr = str(col)
            if len(printstr) > width:
                for i in range(len(printstr)-4, len(printstr)-1):
                    printstr=printstr[:width]
                    printstr=printstr[:-3]+'...'
            sys.stdout.write(printstr)
            sys.stdout.write(' '*(width-len(printstr)))
            sys.stdout.write(' '*padding)
        sys.stdout.write('\n')
        sys.stdout.flush()


def printable_data(data):
    chars = []
    for c in data:
        if c in string.printable:
            chars += c
        else:
            chars += '.'
    return ''.join(chars)

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def get_unmangled(reqid):
    # Used for the repeater command. Must not be async
    req = yield pappyproxy.http.Request.load_request(reqid)
    if req.unmangled:
        defer.returnValue(req.unmangled.reqid)
    else:
        defer.returnValue(None)

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def check_reqid(reqid):
    # Used for the repeater command. Must not be async
    try:
        yield pappyproxy.http.Request.load_request(reqid)
    except:
        raise PappyException('"%s" is not a valid request id' % reqid)
    defer.returnValue(None)
    
def view_full_request(request, headers_only=False):
    if headers_only:
        to_print = printable_data(request.raw_headers)
    else:
        to_print = printable_data(request.full_request)
    to_print = pygments.highlight(to_print, HttpLexer(), TerminalFormatter())

    print to_print

def view_full_response(response, headers_only=False):
    def check_type(response, against):
        if 'Content-Type' in response.headers and against in response.headers['Content-Type']:
            return True
        return False

    if headers_only:
        to_print = printable_data(response.raw_headers)
        to_print = pygments.highlight(to_print, HttpLexer(), TerminalFormatter())
        print to_print
    else:
        headers = printable_data(response.raw_headers)
        headers = pygments.highlight(headers, HttpLexer(), TerminalFormatter())
        print headers
        to_print = printable_data(response.raw_data)
        if 'Content-Type' in response.headers:
            try:
                lexer = get_lexer_for_mimetype(response.headers['Content-Type'].split(';')[0])
                to_print = pygments.highlight(to_print, lexer, TerminalFormatter())
            except ClassNotFound:
                pass

        print to_print

def print_requests(requests):
    # Print a table with info on all the requests in the list
    cols = [
        {'name':'ID'},
        {'name':'Verb'},
        {'name': 'Host'},
        {'name':'Path', 'width':40},
        {'name':'S-Code'},
        {'name':'Req Len'},
        {'name':'Rsp Len'},
        {'name':'Time'},
        {'name':'Mngl'},
    ]
    rows = []
    for request in requests:
        rid = request.reqid
        method = request.verb
        if 'host' in request.headers:
            host = request.headers['host']
        else:
            host = '??'
        path = request.full_path
        reqlen = len(request.raw_data)
        rsplen = 'N/A'
        mangle_str = '--'

        if request.unmangled:
            mangle_str = 'q'
            
        if request.response:
            response_code = str(request.response.response_code) + \
                ' ' + request.response.response_text
            rsplen = len(request.response.raw_data)
            if request.response.unmangled:
                if mangle_str == '--':
                    mangle_str = 's'
                else:
                    mangle_str += '/s'
        else:
            response_code = ''

        time_str = '--'
        if request.time_start and request.time_end:
            time_delt = request.time_end - request.time_start
            time_str = "%.2f" % time_delt.total_seconds()

        port = request.port
        if request.is_ssl:
            is_ssl = 'YES'
        else:
            is_ssl = 'NO'
            
        rows.append([rid, method, host, path, response_code,
                     reqlen, rsplen, time_str, mangle_str])
    print_table(cols, rows)
    
def print_request_extended(request):
    # Prints extended info for the request
    title = "Request Info (reqid=%s)" % request.reqid
    print title
    print '-'*len(title)
    reqlen = len(request.raw_data)
    reqlen = '%d bytes' % reqlen
    rsplen = 'No response'

    mangle_str = 'Nothing mangled'
    if request.unmangled:
        mangle_str = 'Request'

    if request.response:
        response_code = str(request.response.response_code) + \
            ' ' + request.response.response_text
        rsplen = len(request.response.raw_data)
        rsplen = '%d bytes' % rsplen

        if request.response.unmangled:
            if mangle_str == 'Nothing mangled':
                mangle_str = 'Response'
            else:
                mangle_str += ' and Response'
    else:
        response_code = ''

    time_str = '--'
    if request.time_start and request.time_end:
        time_delt = request.time_end - request.time_start
        time_str = "%.2f sec" % time_delt.total_seconds()

    port = request.port
    if request.is_ssl:
        is_ssl = 'YES'
    else:
        is_ssl = 'NO'

    if request.time_start:
        time_made_str = request.time_start.strftime('%a, %b %d, %Y, %I:%M:%S %p')
    else:
        time_made_str = '--'
    
    print 'Made on %s' % time_made_str
    print 'ID: %s' % request.reqid
    print 'Verb: %s' % request.verb
    print 'Host: %s' % request.host
    print 'Path: %s' % request.full_path
    print 'Status Code: %s' % response_code
    print 'Request Length: %s' % reqlen
    print 'Response Length: %s' % rsplen
    if request.response and request.response.unmangled:
        print 'Unmangled Response Length: %s bytes' % len(request.response.unmangled.full_response)
    print 'Time: %s' % time_str
    print 'Port: %s' % request.port
    print 'SSL: %s' % is_ssl
    print 'Mangled: %s' % mangle_str
    print 'Tags: %s' % (', '.join(request.tags))

@defer.inlineCallbacks
def load_reqlist(line, allow_special=True):
    # Parses a comma separated list of ids and returns a list of those requests
    # prints any errors
    ids = re.split(',\s*', line)
    reqs = []
    for reqid in ids:
        try:
            req = yield pappyproxy.http.Request.load_request(reqid, allow_special)
            reqs.append(req)
        except PappyException as e:
            print e
    defer.returnValue(reqs)

def get_site_map(reqs):
    # Takes in a list of requests and returns a tree representing the site map
    paths_set = set()
    for req in reqs:
        paths_set.add(req.path_tuple)
    paths = sorted(list(paths_set))
    return paths

def print_tree(tree):
    # Prints a tree. Takes in a sorted list of path tuples
    _print_tree_helper(tree, 0, [])
    
def _get_tree_prefix(depth, print_bars, last):
    if depth == 0:
        return u''
    else:
        ret = u''
        pb = print_bars + [True]
        for i in range(depth):
            if pb[i]:
                ret += u'\u2502   '
            else:
                ret += u'    '
        if last:
            ret += u'\u2514\u2500\u2500 '
        else:
            ret += u'\u251c\u2500\u2500 '
        return ret
    
def _print_tree_helper(tree, depth, print_bars):
    # Takes in a tree and prints it at the given depth
    if tree == [] or tree == [()]:
        return
    while tree[0] == ():
        tree = tree[1:]
        if tree == [] or tree == [()]:
            return
    if len(tree) == 1 and len(tree[0]) == 1:
        print _get_tree_prefix(depth, print_bars + [False], True) + tree[0][0]
        return

    curkey = tree[0][0]
    subtree = []
    for row in tree:
        if row[0] != curkey:
            if curkey == '':
                curkey = '/'
            print _get_tree_prefix(depth, print_bars, False) + curkey
            if depth == 0:
                _print_tree_helper(subtree, depth+1, print_bars + [False])
            else:
                _print_tree_helper(subtree, depth+1, print_bars + [True])
            curkey = row[0]
            subtree = []
        subtree.append(row[1:])
    if curkey == '':
        curkey = '/'
    print _get_tree_prefix(depth, print_bars, True) + curkey
    _print_tree_helper(subtree, depth+1, print_bars + [False])
            
def confirm(message, default='n'):
    if 'n' in default.lower():
        default = False
    else:
        default = True

    print message
    if default:
        answer = raw_input('(Y/n) ')
    else:
        answer = raw_input('(y/N) ')


    if not answer:
        return default

    if answer[0].lower() == 'y':
        return True
    else:
        return False
        
