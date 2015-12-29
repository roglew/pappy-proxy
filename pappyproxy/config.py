import imp
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
    #subs['PAPPYDIR'] = PAPPY_DIR
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


def load_from_file(fname):
    # Make sure we have a config file
    if not os.path.isfile(fname):
        print "Copying default config to %s" % fname
        default_config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                        'default_user_config.json')
        shutil.copyfile(default_config_file, fname)

    # Load local project config
    with open(fname, 'r') as f:
        proj_config = json.load(f)
    load_settings(proj_config)
