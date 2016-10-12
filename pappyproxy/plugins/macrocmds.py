import crochet
import pappyproxy
import shlex

from pappyproxy.plugin import active_intercepting_macros, add_intercepting_macro, remove_intercepting_macro
from pappyproxy.macros import load_macros, macro_from_requests, MacroTemplate
from pappyproxy.util import PappyException, load_reqlist, autocomplete_startswith
from twisted.internet import defer

loaded_macros = []
loaded_int_macros = []
macro_dict = {}
int_macro_dict = {}

@defer.inlineCallbacks
def gen_macro_helper(line, template=None):
    args = shlex.split(line)
    if template is None:
        fname = args[0]
        template_name = args[1]
        argstart = 2
    else:
        fname = args[0]
        template_name = template
        argstart = 1
    if template_name not in MacroTemplate.template_list():
        raise PappyException('%s is not a valid template name' % template_name)
    script_str = yield MacroTemplate.fill_template_args(template_name, args[argstart:])
    fname = MacroTemplate.template_filename(template_name, fname)
    with open(fname, 'wc') as f:
        f.write(script_str)
    print 'Wrote script to %s' % fname

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
            
def complete_run_macro(text, line, begidx, endidx):
    global macro_dict
    strs = [k for k,v in macro_dict.iteritems()]
    return autocomplete_startswith(text, strs)

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

def complete_run_int_macro(text, line, begidx, endidx):
    global int_macro_dict
    global loaded_int_macros
    running = []
    not_running = []
    for macro in loaded_int_macros:
        if macro.name in [m.name for m in active_intercepting_macros()]:
            running.append(macro)
        else:
            not_running.append(macro)
    strs = []
    for m in not_running:
        strs.append(macro.name)
        strs.append(macro.file_name)
        if macro.short_name:
            strs.append(macro.short_name)
    return autocomplete_startswith(text, strs)

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
    try:
        macro.init(args[1:])
        add_intercepting_macro(macro.name, macro)
        print '"%s" started' % macro.name
    except Exception as e:
        print 'Error initializing macro:'
        raise e

def complete_stop_int_macro(text, line, begidx, endidx):
    global int_macro_dict
    global loaded_int_macros
    running = []
    not_running = []
    for macro in loaded_int_macros:
        if macro.name in [m.name for m in active_intercepting_macros()]:
            running.append(macro)
        else:
            not_running.append(macro)
    strs = []
    for m in running:
        strs.append(macro.name)
        strs.append(macro.file_name)
        if macro.short_name:
            strs.append(macro.short_name)
    return autocomplete_startswith(text, strs)

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
        if macro.name in [m.name for m in active_intercepting_macros()]:
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
    yield gen_macro_helper(line, template='macro')

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def generate_int_macro(line):
    """
    Generate an intercepting macro script
    Usage: generate_int_macro <name>
    """
    yield gen_macro_helper(line, template='intmacro')

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def generate_template_macro(line):
    """
    Generate a macro from a built in template
    Usage: generate_template_macro <fname> <template> [args]
    """
    if line == '':
        print 'Usage: gtma <fname> <template> [args]'
        print 'Macro templates:'

        templates = MacroTemplate.template_list()
        templates.sort()
        for t in templates:
            if MacroTemplate.template_argstring(t):
                print '"%s %s" - %s' % (t, MacroTemplate.template_argstring(t), MacroTemplate.template_description(t))
            else:
                print '"%s" - %s' % (t, MacroTemplate.template_description(t))
    else:
        yield gen_macro_helper(line)

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
        'generate_template_macro': (generate_template_macro, None),
        'list_int_macros': (list_int_macros, None),
        'stop_int_macro': (stop_int_macro, complete_stop_int_macro),
        'run_int_macro': (run_int_macro, complete_run_int_macro),
        'run_macro': (run_macro, complete_run_macro),
        'load_macros': (load_macros_cmd, None),
    })
    cmd.add_aliases([
        #('rpy', ''),
        ('generate_int_macro', 'gima'),
        ('generate_macro', 'gma'),
        ('generate_template_macro', 'gtma'),
        ('list_int_macros', 'lsim'),
        ('stop_int_macro', 'sim'),
        ('run_int_macro', 'rim'),
        ('run_macro', 'rma'),
        ('load_macros', 'lma'),
    ])
