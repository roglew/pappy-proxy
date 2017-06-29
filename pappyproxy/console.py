"""
Contains helpers for interacting with the console. Includes definition for the
class that is used to run the console.
"""

import atexit
import cmd2
import os
import readline
#import string
import shlex
import sys

from .colors import Colors
from .proxy import MessageError

###################
## Helper Functions

def print_errors(func):
    def catch(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except (CommandError, MessageError) as e:
            print(str(e))
    return catch

def interface_loop(client):
    cons = Cmd(client=client)
    load_interface(cons)
    sys.argv = []
    cons.cmdloop()
    
def load_interface(cons):
    from .interface import test, view, decode, misc, context, mangle, macros, tags
    test.load_cmds(cons)
    view.load_cmds(cons)
    decode.load_cmds(cons)
    misc.load_cmds(cons)
    context.load_cmds(cons)
    mangle.load_cmds(cons)
    macros.load_cmds(cons)
    tags.load_cmds(cons)

##########
## Classes
    
class SessionEnd(Exception):
    pass

class CommandError(Exception):
    pass

class Cmd(cmd2.Cmd):
    """
    An object representing the console interface. Provides methods to add
    commands and aliases to the console. Implemented as a hack around cmd2.Cmd
    """

    def __init__(self, *args, **kwargs):
        # the \x01/\x02 are to make the prompt behave properly with the readline library
        self.prompt = 'pappy\x01' + Colors.YELLOW + '\x02> \x01' + Colors.ENDC + '\x02'
        self.debug = True
        self.histsize = 0
        if 'histsize' in kwargs:
            self.histsize = kwargs['histsize']
            del kwargs['histsize']
        if 'client' not in kwargs:
            raise Exception("client argument is required")
        self.client = kwargs['client']
        self.client.console = self
        del kwargs['client']

        self._cmds = {}
        self._aliases = {}

        atexit.register(self.save_histfile)
        readline.set_history_length(self.histsize)
        if os.path.exists('cmdhistory'):
            if self.histsize != 0:
                readline.read_history_file('cmdhistory')
            else:
                os.remove('cmdhistory')

        cmd2.Cmd.__init__(self, *args, **kwargs)

    
    def __dir__(self):
        # Hack to get cmd2 to detect that we can run a command
        ret = set(dir(self.__class__))
        ret.update(self.__dict__.keys())
        ret.update(['do_'+k for k in self._cmds.keys()])
        ret.update(['help_'+k for k in self._cmds.keys()])
        ret.update(['complete_'+k for k, v in self._cmds.items() if self._cmds[k][1]])
        for k, v in self._aliases.items():
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
                else:
                    lines = func.__doc__.splitlines()
                    if len(lines) > 0 and lines[0] == '':
                        lines = lines[1:]
                    if len(lines) > 0 and lines[-1] == '':
                        lines = lines[-1:]
                    to_print = '\n'.join(l.lstrip() for l in lines)
                    
                aliases = set()
                aliases.add(attr[5:])
                for i in range(2):
                    for k, v in self._aliases.items():
                        if k in aliases or v in aliases:
                            aliases.add(k)
                            aliases.add(v)
                to_print += '\nAliases: ' + ', '.join(aliases)
                print(to_print)
            return f
        
        def gen_dofunc(func, client):
            def f(line):
                args = shlex.split(line)
                func(client, args)
            return print_errors(f)

        if attr.startswith('do_'):
            command = attr[3:]
            if command in self._cmds:
                return gen_dofunc(self._cmds[command][0], self.client)
            elif command in self._aliases:
                real_command = self._aliases[command]
                if real_command in self._cmds:
                    return gen_dofunc(self._cmds[real_command][0], self.client)
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

    def run_args(self, args):
        command = args[0]
        if command in self._cmds:
            self._cmds[command][0](self.client, args[1:])
        elif command in self._aliases:
            real_command = self._aliases[command]
            if real_command in self._cmds:
                self._cmds[real_command][0](self.client, args[1:])

    def save_histfile(self):
        # Write the command to the history file
        if self.histsize != 0:
            readline.set_history_length(self.histsize)
            readline.write_history_file('cmdhistory')
    
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
        for command, vals in cmd_dict.items():
            do_func, ac_func = vals
            self.set_cmd(command, do_func, ac_func)

    def add_alias(self, command, alias):
        """
        Add an alias for a command.
        ie add_alias("foo", "f") will let you run the 'foo' command with 'f'
        """
        if command not in self._cmds:
            raise KeyError()
        self._aliases[alias] = command

    def add_aliases(self, alias_list):
        """
        Pass in a list of tuples to add them all as aliases.
        ie add_aliases([('foo', 'f'), ('foo', 'fo')]) will add 'f' and 'fo' as
        aliases for 'foo'
        """
        for command, alias in alias_list:
            self.add_alias(command, alias)

