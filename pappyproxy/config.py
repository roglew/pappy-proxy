"""
The configuration settings for the proxy.

.. data:: CERT_DIR

    The location of the CA certs that Pappy will use. This can be configured in the
    ``config.json`` file for a project.
    
    :Default: ``{DATADIR}/certs``

.. data:: PAPPY_DIR

    The file where pappy's scripts are located. Don't write anything here, and you
    probably don't need to write anything here. Use DATA_DIR instead.
    
    :Default: Wherever the scripts are installed

.. data:: DATA_DIR

    The data directory. This is where files that have to be read by Pappy every time
    it's run are put. For example, plugins are stored in ``{DATADIR}/plugins`` and
    certs are by default stored in ``{DATADIR}/certs``. This defaults to ``~/.pappy``
    and isn't configurable right now.
    
    :Default: ``~/.pappy``

.. data:: DATAFILE

    The location of the CA certs that Pappy will use. This can be configured in the
    ``config.json`` file for a project.
    
    :Default: ``data.db``

.. data:: DEBUG_DIR

    The directory to write debug output to. Don't put this outside the project folder
    since it writes all the request data to this directory. You probably won't need
    to use this. Configured in the ``config.json`` file for the project.
    
    :Default: None

.. data: LISTENERS

    The list of active listeners. It is a list of tuples of the format (port, interface)
    Not modifiable after startup. Configured in the ``config.json`` file for the project.
    
    :Default: ``[(8000, '127.0.0.1')]``

.. data: PLUGIN_DIRS

    List of directories that plugins are loaded from. Not modifiable.
    
    :Default: ``['{DATA_DIR}/plugins', '{PAPPY_DIR}/plugins']``

.. data: CONFIG_DICT

    The dictionary read from config.json. When writing plugins, use this to load
    configuration options for your plugin.

.. data: GLOBAL_CONFIG_DICT

    The dictionary from ~/.pappy/global_config.json. It contains settings for
    Pappy that are specific to the current computer. Avoid putting settings here,
    especially if it involves specific projects.

"""

import json
import os
import shutil

PAPPY_DIR = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = os.path.join(os.path.expanduser('~'), '.pappy')

CERT_DIR = os.path.join(DATA_DIR, 'certs')

DATAFILE = 'data.db'

DEBUG_DIR = None
DEBUG_TO_FILE = False
DEBUG_VERBOSITY = 0

LISTENERS = [(8000, '127.0.0.1')]

SSL_CA_FILE  = 'certificate.crt'
SSL_PKEY_FILE = 'private.key'

PLUGIN_DIRS = [os.path.join(DATA_DIR, 'plugins'), os.path.join(PAPPY_DIR, 'plugins')]

CONFIG_DICT = {}
GLOBAL_CONFIG_DICT = {}

def get_default_config():
    default_config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                       'default_user_config.json')
    with open(default_config_file) as f:
        settings = json.load(f)
    return settings

def load_settings(proj_config):
    global CERT_DIR
    global DATAFILE
    global DEBUG_DIR
    global DEBUG_TO_FILE
    global DEBUG_VERBOSITY
    global LISTENERS
    global PAPPY_DIR
    global DATA_DIR
    global SSL_CA_FILE 
    global SSL_PKEY_FILE

    # Substitution dictionary
    subs = {}
    subs['PAPPYDIR'] = PAPPY_DIR
    subs['DATADIR'] = DATA_DIR

    # Data file settings
    if 'data_file' in proj_config:
        DATAFILE = proj_config["data_file"].format(**subs)

    # Debug settings
    if 'debug_dir' in proj_config:
        if proj_config['debug_dir']:
            DEBUG_TO_FILE = True
            DEBUG_DIR = proj_config["debug_dir"].format(**subs)

    # Cert directory settings
    if 'cert_dir' in proj_config:
        CERT_DIR = proj_config["cert_dir"].format(**subs)

    # Listener settings
    if "proxy_listeners" in proj_config:
        LISTENERS = []
        for l in proj_config["proxy_listeners"]:
            LISTENERS.append((l['port'], l['interface']))

def load_global_settings(global_config):
    from .http import Request
    global CACHE_SIZE

    if "cache_size" in global_config:
        CACHE_SIZE = global_config['cache_size']
    else:
        CACHE_SIZE = 2000
    Request.cache.resize(CACHE_SIZE)

def load_from_file(fname):
    global CONFIG_DICT
    # Make sure we have a config file
    if not os.path.isfile(fname):
        print "Copying default config to %s" % fname
        default_config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                        'default_user_config.json')
        shutil.copyfile(default_config_file, fname)

    # Load local project config
    with open(fname, 'r') as f:
        CONFIG_DICT = json.load(f)
    load_settings(CONFIG_DICT)

def global_load_from_file():
    global GLOBAL_CONFIG_DICT
    global DATA_DIR
    # Make sure we have a config file
    fname = os.path.join(DATA_DIR, 'global_config.json')
    if not os.path.isfile(fname):
        print "Copying default global config to %s" % fname
        default_global_config_file = os.path.join(PAPPY_DIR,
                                                  'default_global_config.json')
        shutil.copyfile(default_global_config_file, fname)

    # Load local project config
    with open(fname, 'r') as f:
        GLOBAL_CONFIG_DICT = json.load(f)
    load_global_settings(GLOBAL_CONFIG_DICT)
