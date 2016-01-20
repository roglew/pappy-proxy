import crochet
import pappyproxy
import shlex

from pappyproxy.plugin import active_intercepting_macros, add_intercepting_macro, remove_intercepting_macro
from pappyproxy.console import load_reqlist
from pappyproxy.macros import load_macros, macro_from_requests, gen_imacro
from pappyproxy.util import PappyException
from twisted.internet import defer

loaded_macros = []
loaded_int_macros = []
macro_dict = {}
int_macro_dict = {}

def load_macros_cmd(line):
    """
    Load macros from a directory. By default loads macros in the current directory.
    Usage: load_macros [dir]
    """
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

def run_macro(line):
    """
    Run a macro
    Usage: run_macro <macro name or macro short name>
    """
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

def run_int_macro(line):
    """
    Activate an intercepting macro
    Usage: run_int_macro <macro name or macro short name>
    Macro can be stopped with stop_int_macro
    """
    global int_macro_dict
    global loaded_int_macros
    args = shlex.split(line)
    if len(args) == 0:
        raise PappyException('You must give an intercepting macro to run. You can give its short name, or the name in the filename.')
    if args[0] not in int_macro_dict:
        raise PappyException('%s not a loaded intercepting macro' % line)
    macro = int_macro_dict[args[0]]
    macro.init(args[1:])
    add_intercepting_macro(macro.name, macro)
    print '"%s" started' % macro.name

def stop_int_macro(line):
    """
    Stop a running intercepting macro
    Usage: stop_int_macro <macro name or macro short name>
    """
    global int_macro_dict
    global loaded_int_macros
    if not line:
        raise PappyException('You must give an intercepting macro to run. You can give its short name, or the name in the filename.')
    if line not in int_macro_dict:
        raise PappyException('%s not a loaded intercepting macro' % line)
    macro = int_macro_dict[line]
    remove_intercepting_macro(macro.name)
    print '"%s" stopped' % macro.name
    
def list_int_macros(line):
    """
    List all active/inactive intercepting macros
    """
    global int_macro_dict
    global loaded_int_macros
    running = []
    not_running = []
    for macro in loaded_int_macros:
        if macro.name in active_intercepting_macros():
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
    
@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def generate_macro(line):
    """
    Generate a macro script with request objects
    Usage: generate_macro <name> [reqs]
    """
    if line == '':
        raise PappyException('Macro name is required')
    args = shlex.split(line)
    name = args[0]
    if len(args) > 1:
        reqs = yield load_reqlist(args[1])
    else:
        reqs = []
    script_str = macro_from_requests(reqs)
    fname = 'macro_%s.py' % name
    with open(fname, 'wc') as f:
        f.write(script_str)
    print 'Wrote script to %s' % fname

def generate_int_macro(line):
    """
    Generate an intercepting macro script
    Usage: generate_int_macro <name>
    """
    if line == '':
        raise PappyException('Macro name is required')
    args = shlex.split(line)
    name = args[0]
    script_str = gen_imacro()
    fname = 'int_%s.py' % name
    with open(fname, 'wc') as f:
        f.write(script_str)
    print 'Wrote script to %s' % fname

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def rpy(line):
    """
    Copy python object definitions of requests.
    Usage: rpy <reqs>
    """
    reqs = yield load_reqlist(line)
    for req in reqs:
        print pappyproxy.macros.req_obj_def(req)

###############
## Plugin hooks

def load_cmds(cmd):
    cmd.set_cmds({
        'rpy': (rpy, None),
        'generate_int_macro': (generate_int_macro, None),
        'generate_macro': (generate_macro, None),
        'list_int_macros': (list_int_macros, None),
        'stop_int_macro': (stop_int_macro, None),
        'run_int_macro': (run_int_macro, None),
        'run_macro': (run_macro, None),
        'load_macros': (load_macros_cmd, None),
    })
    cmd.add_aliases([
        #('rpy', ''),
        ('generate_int_macro', 'gima'),
        ('generate_macro', 'gma'),
        ('list_int_macros', 'lsim'),
        ('stop_int_macro', 'sim'),
        ('run_int_macro', 'rim'),
        ('run_macro', 'rma'),
        ('load_macros', 'lma'),
    ])
