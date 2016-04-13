"""
Contains helpers for interacting with the console. Includes definition for the
class that is used to run the console.
"""

import atexit
import cmd2
import os
import readline
import string

from .util import PappyException
from .colors import Colors

###################
## Helper functions

def print_pappy_errors(func):
    def catch(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except PappyException as e:
            print str(e)
    return catch

##########
## Classes
    
class ProxyCmd(cmd2.Cmd):
    """
    An object representing the console interface. Provides methods to add
    commands and aliases to the console.
    """

    def __init__(self, *args, **kwargs):
        # the \x01/\x02 are to make the prompt behave properly with the readline library
        self.prompt = 'pappy\x01' + Colors.YELLOW + '\x02> \x01' + Colors.ENDC + '\x02'
        self.debug = True
        self.session = kwargs['session']
        del kwargs['session']

        self._cmds = {}
        self._aliases = {}

        # Only read and save history when not in crypto mode
        if not self.session.config.crypt_session:
            atexit.register(self.save_histfile)
            readline.set_history_length(self.session.config.histsize)
            if os.path.exists('cmdhistory'):
                if self.session.config.histsize != 0:
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

    def save_histfile(self):
        # Only write to file if not in crypto mode
        if not self.session.config.crypt_session:
            # Write the command to the history file
            if self.session.config.histsize != 0:
                readline.set_history_length(self.session.config.histsize)
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

