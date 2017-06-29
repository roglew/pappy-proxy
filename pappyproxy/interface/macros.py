from ..util import load_reqlist
from ..macros import macro_from_requests, MacroTemplate, load_macros
from ..colors import Colors

macro_dict = {}
int_macro_dict = {}
int_conns = {}

def generate_macro(client, args):
    if len(args) == 0:
        print("usage: gma [name] [reqids]")
        return
    macro_name = args[0]

    reqs = [r for r in load_reqlist(client, ','.join(args[1:]))]
    script_string = macro_from_requests(reqs)
    fname = MacroTemplate.template_filename('macro', macro_name)
    with open(fname, 'w') as f:
        f.write(script_string)
    print("Macro written to {}".format(fname))

def generate_int_macro(client, args):
    if len(args) == 0:
        print("usage: gima [name] [reqids]")
        return
    macro_name = args[0]

    reqs = [r for r in load_reqlist(client, ','.join(args[1:]))]

    script_string = macro_from_requests(reqs, template='intmacro')
    fname = MacroTemplate.template_filename('intmacro', macro_name)
    with open(fname, 'w') as f:
        f.write(script_string)
    print("Macro written to {}".format(fname))
    
def load_macros_cmd(client, args):
    global macro_dict

    load_dir = '.'
    if len(args) > 0:
        load_dir = args[0]

    _stop_all_int_macros()

    loaded_macros, loaded_int_macros = load_macros(load_dir, client)
    for macro in loaded_macros:
        macro_dict[macro.name] = macro
        print("Loaded {} ({})".format(macro.name, macro.file_name))
    for macro in loaded_int_macros:
        int_macro_dict[macro.name] = macro
        print("Loaded {} ({})".format(macro.name, macro.file_name))

def complete_run_macro(text, line, begidx, endidx):
    from ..util import autocomplete_starts_with

    global macro_dict
    strs = macro_dict.keys()
    return autocomplete_startswith(text, strs)
        
def run_macro(client, args):
    global macro_dict
    if len(args) == 0:
        print("usage: rma [macro name]")
        return
    macro = macro_dict[args[0]]
    macro.execute(client, args[1:])

def complete_run_int_macro(text, line, begidx, endidx):
    from ..util import autocomplete_starts_with

    global int_macro_dict
    strs = int_macro_dict.keys()
    return autocomplete_startswith(text, strs)

def run_int_macro(client, args):
    global int_macro_dict
    global int_conns
    if len(args) == 0:
        print("usage: rim [macro name]")
        return
    if args[0] in int_conns:
        print("%s is already running!" % args[0])
        return
    macro = int_macro_dict[args[0]]
    macro.init(args[1:])
    conn = client.new_conn()
    int_conns[args[0]] = conn
    conn.intercept(macro)
    print("Started %s" % args[0])

def complete_stop_int_macro(text, line, begidx, endidx):
    from ..util import autocomplete_starts_with

    global int_conns
    strs = int_conns.keys()
    return autocomplete_startswith(text, strs)

def stop_int_macro(client, args):
    global int_conns
    if len(args) > 0:
        conn = int_conns[args[0]]
        conn.close()
        del int_conns[args[0]]
        print("Stopped %s" % args[0])
    else:
        _stop_all_int_macros()

def _stop_all_int_macros():
    global int_conns
    for k, conn in int_conns.items():
        conn.close()
        del int_conns[k]
        print("Stopped %s" % k)

def list_macros(client, args):
    global macro_dict
    global int_macro_dict
    global int_conns
    if len(macro_dict) > 0:
        print('Loaded Macros:')
    for k, m in macro_dict.items():
        print('  '+k)

    if len(int_macro_dict) > 0:
        print('Loaded Intercepting Macros:')
        for k, m in int_macro_dict.items():
            pstr = '  '+k
            if k in int_conns:
                pstr += ' (' + Colors.GREEN + 'RUNNING' + Colors.ENDC + ')'
            print(pstr)

def load_cmds(cmd):
    cmd.set_cmds({
        'generate_macro': (generate_macro, None),
        'generate_int_macro': (generate_int_macro, None),
        'load_macros': (load_macros_cmd, None),
        'run_macro': (run_macro, complete_run_macro),
        'run_int_macro': (run_int_macro, complete_run_int_macro),
        'stop_int_macro': (stop_int_macro, complete_stop_int_macro),
        'list_macros': (list_macros, None),
    })
    cmd.add_aliases([
        ('generate_macro', 'gma'),
        ('generate_int_macro', 'gima'),
        ('load_macros', 'lma'),
        ('run_macro', 'rma'),
        ('run_int_macro', 'rim'),
        ('stop_int_macro', 'sim'),
        ('list_macros', 'lsma'),
    ])
