import imp
import json
import os
import shutil

# Make sure we have a config file
if not os.path.isfile('./config.json'):
    print "Copying default config to directory"
    default_config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                       'default_user_config.json')
    shutil.copyfile(default_config_file, './config.json')

# Load local project config
with open('./config.json', 'r') as f:
    proj_config = json.load(f)

# Substitution dictionary
subs = {}
subs['PAPPYDIR'] = os.path.dirname(os.path.realpath(__file__))

# Data file settings
if 'data_file' in proj_config:
    DATAFILE = proj_config["data_file"].format(**subs)
else:
    DATAFILE = 'data.db'

# Debug settings
if 'debug_dir' in proj_config:
    DEBUG_TO_FILE = True
    DEBUG_DIR = proj_config["debug_dir"].format(**subs)
else:
    DEBUG_DIR = None
    DEBUG_TO_FILE = False
DEBUG_VERBOSITY = 0

# Cert directory settings
if 'cert_dir' in proj_config:
    CERT_DIR = proj_config["cert_dir"].format(**subs)
else:
    CERT_DIR = './certs'
SSL_PKEY_FILE = 'private.key'
SSL_CA_FILE  = 'certificate.crt'
    
# Listener settings
if "proxy_listeners" in proj_config:
    LISTENERS = []
    for l in proj_config["proxy_listeners"]:
        LISTENERS.append((l['port'], l['interface']))
else:
    LISTENERS = [(8000, '127.0.0.1')]

