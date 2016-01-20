"""
Contains helpers for interacting with the console. Includes definition for the
class that is used to run the console.
"""

import cmd2
import re
import string
import sys

from .util import PappyException
from twisted.internet import defer

###################
## Helper functions

def print_pappy_errors(func):
    def catch(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except PappyException as e:
            print str(e)
    return catch

@defer.inlineCallbacks
def load_reqlist(line, allow_special=True):
    """
    load_reqlist(line, allow_special=True)
    A helper function for parsing a list of requests that are passed as an
    argument. If ``allow_special`` is True, then it will parse IDs such as
    ``u123`` or ``s123``. Even if allow_special is false, it will still parse
    ``m##`` IDs. Will print any errors with loading any of the requests and
    will return a list of all the requests which were successfully loaded.
    Returns a deferred.

    :Returns: Twisted deferred
    """
    from .http import Request
    # Parses a comma separated list of ids and returns a list of those requests
    # prints any errors
    ids = re.split(',\s*', line)
    reqs = []
    for reqid in ids:
        try:
            req = yield Request.load_request(reqid, allow_special)
            reqs.append(req)
        except PappyException as e:
            print e
    defer.returnValue(reqs)

def print_table(coldata, rows):
    """
    Print a table.
    Coldata: List of dicts with info on how to print the columns.
    ``name`` is the heading to give column,
    ``width (optional)`` maximum width before truncating. 0 for unlimited.

    Rows: List of tuples with the data to print
    """

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

def print_requests(requests):
    """
    Takes in a list of requests and prints a table with data on each of the
    requests. It's the same table that's used by ``ls``.
    """
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
        reqlen = len(request.body)
        rsplen = 'N/A'
        mangle_str = '--'

        if request.unmangled:
            mangle_str = 'q'
            
        if request.response:
            response_code = str(request.response.response_code) + \
                ' ' + request.response.response_text
            rsplen = len(request.response.body)
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

        rows.append([rid, method, host, path, response_code,
                     reqlen, rsplen, time_str, mangle_str])
    print_table(cols, rows)
    
def confirm(message, default='n'):
    """
    A helper function to get confirmation from the user. It prints ``message``
    then asks the user to answer yes or no. Returns True if the user answers
    yes, otherwise returns False.
    """
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
        
##########
## Classes
    
class ProxyCmd(cmd2.Cmd):
    """
    An object representing the console interface. Provides methods to add
    commands and aliases to the console.
    """

    def __init__(self, *args, **kwargs):
        self.prompt = 'pappy> '
        self.debug = True

        self._cmds = {}
        self._aliases = {}
        cmd2.Cmd.__init__(self, *args, **kwargs)
    
    def __dir__(self):
        # Hack to get cmd2 to detect that we can run a command
        ret = set(dir(self.__class__))
        ret.update(self.__dict__.keys())
        ret.update(['do_'+k for k in self._cmds.keys()])
        ret.update(['help_'+k for k in self._cmds.keys()])
        ret.update(['complete_'+k for k, v in self._cmds.iteritems() if self._cmds[k][1]])
        for k, v in self._aliases.iteritems():
            ret.add('do_' + k)
            ret.add('help_' + k)
            if self._cmds[self._aliases[k]][1]:
                ret.add('complete_'+k)
        return sorted(ret)

    def __getattr__(self, attr):
        def gen_helpfunc(func):
            def f():
                if not func.__doc__:
                    to_print = 'No help exists for function'
                lines = func.__doc__.splitlines()
                if len(lines) > 0 and lines[0] == '':
                    lines = lines[1:]
                if len(lines) > 0 and lines[-1] == '':
                    lines = lines[-1:]
                to_print = '\n'.join(string.lstrip(l) for l in lines)
                print to_print
            return f

        if attr.startswith('do_'):
            command = attr[3:]
            if command in self._cmds:
                return print_pappy_errors(self._cmds[command][0])
            elif command in self._aliases:
                real_command = self._aliases[command]
                if real_command in self._cmds:
                    return print_pappy_errors(self._cmds[real_command][0])
        elif attr.startswith('help_'):
            command = attr[5:]
            if command in self._cmds:
                return gen_helpfunc(self._cmds[command][0])
            elif command in self._aliases:
                real_command = self._aliases[command]
                if real_command in self._cmds:
                    return gen_helpfunc(self._cmds[real_command][0])
        elif attr.startswith('complete_'):
            command = attr[9:]
            if command in self._cmds:
                if self._cmds[command][1]:
                    return self._cmds[command][1]
            elif command in self._aliases:
                real_command = self._aliases[command]
                if real_command in self._cmds:
                    if self._cmds[real_command][1]:
                        return self._cmds[real_command][1]
        raise AttributeError(attr)
    
    def get_names(self):
        # Hack to get cmd to recognize do_/etc functions as functions for things
        # like autocomplete
        return dir(self)

    def set_cmd(self, command, func, autocomplete_func=None):
        """
        Add a command to the console.
        """
        self._cmds[command] = (func, autocomplete_func)

    def set_cmds(self, cmd_dict):
        """
        Set multiple commands from a dictionary. Format is:
        {'command': (do_func, autocomplete_func)}
        Use autocomplete_func=None for no autocomplete function
        """
        for command, vals in cmd_dict.iteritems():
            do_func, ac_func = vals
            self.set_cmd(command, do_func, ac_func)

    def add_alias(self, command, alias):
        """
        Add an alias for a command.
        ie add_alias("foo", "f") will let you run the 'foo' command with 'f'
        """
        self._aliases[alias] = command

    def add_aliases(self, alias_list):
        """
        Pass in a list of tuples to add them all as aliases.
        ie add_aliases([('foo', 'f'), ('foo', 'fo')]) will add 'f' and 'fo' as
        aliases for 'foo'
        """
        for command, alias in alias_list:
            self.add_alias(command, alias)
    
