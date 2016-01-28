#!/usr/bin/env python2

import argparse
import crochet
import datetime
import os
import schema.update
import shutil
import sys
import tempfile

from . import comm
from . import config
from . import context
from . import http
from . import plugin
from . import proxy
from . import requestcache
from .console import ProxyCmd
from twisted.enterprise import adbapi
from twisted.internet import reactor, defer
from twisted.internet.error import CannotListenError
from twisted.internet.protocol import ServerFactory
from twisted.internet.threads import deferToThread

crochet.no_setup()
server_factory = None
main_context = context.Context()
all_contexts = [main_context]
plugin_loader = None
cons = None

try:
    from guppy import hpy
    heapstats = hpy()
    heapstats.setref()
except ImportError:
    heapstats = None
    

def parse_args():
    # parses sys.argv and returns a settings dictionary

    parser = argparse.ArgumentParser(description='An intercepting proxy for testing web applications.')
    parser.add_argument('-l', '--lite', help='Run the proxy in "lite" mode', action='store_true')

    args = parser.parse_args(sys.argv[1:])
    settings = {}

    if args.lite:
        settings['lite'] = True
    else:
        settings['lite'] = False

    return settings

def set_text_factory(conn):
    conn.text_factory = str
    
def delete_datafile():
    print 'Deleting temporary datafile'
    os.remove(config.DATAFILE)
    
@defer.inlineCallbacks
def main():
    global server_factory
    global plugin_loader
    global cons
    settings = parse_args()

    if settings['lite']:
        conf_settings = config.get_default_config()
        conf_settings['debug_dir'] = None
        conf_settings['debug_to_file'] = False
        conf_settings['history_size'] = 0
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            conf_settings['data_file'] = tf.name
            print 'Temporary datafile is %s' % tf.name
        delete_data_on_quit = True
        config.load_settings(conf_settings)
    else:
        # Initialize config
        config.load_from_file('./config.json')
        config.global_load_from_file()
        delete_data_on_quit = False

    # If the data file doesn't exist, create it with restricted permissions
    if not os.path.isfile(config.DATAFILE):
        with os.fdopen(os.open(config.DATAFILE, os.O_CREAT, 0o0600), 'r') as f:
            pass
        
    dbpool = adbapi.ConnectionPool("sqlite3", config.DATAFILE,
                                   check_same_thread=False,
                                   cp_openfun=set_text_factory,
                                   cp_max=1)
    try:
        yield schema.update.update_schema(dbpool, config.DATAFILE)
    except Exception as e:
        print 'Error updating schema: %s' % e
        print 'Exiting...'
        reactor.stop()
    http.init(dbpool)
    yield http.Request.cache.load_ids()
    context.reset_context_caches()

    # Run the proxy
    if config.DEBUG_DIR and os.path.exists(config.DEBUG_DIR):
        shutil.rmtree(config.DEBUG_DIR)
        print 'Removing old debugging output'
    server_factory = proxy.ProxyServerFactory(save_all=True)
    listen_strs = []
    ports = []
    for listener in config.LISTENERS:
        try:
            port = reactor.listenTCP(listener[0], server_factory, interface=listener[1])
            listener_str = 'port %d' % listener[0]
            if listener[1] not in ('127.0.0.1', 'localhost'):
                listener_str += ' (bound to %s)' % listener[1]
            listen_strs.append(listener_str)
            ports.append(port)
        except CannotListenError as e:
            print repr(e)
    if listen_strs:
        print 'Proxy is listening on %s' % (', '.join(listen_strs))
    else:
        print 'No listeners opened'

    com_factory = ServerFactory()
    com_factory.protocol = comm.CommServer
    # Make the port different for every instance of pappy, then pass it to
    # anything we run. Otherwise we can only have it running once on a machine
    comm_port = reactor.listenTCP(0, com_factory, interface='127.0.0.1')
    comm.set_comm_port(comm_port.getHost().port)

    # Load the scope
    yield context.load_scope(http.dbpool)
    context.reset_to_scope(main_context)

    sys.argv = [sys.argv[0]] # cmd2 tries to parse args
    cons = ProxyCmd()
    plugin_loader = plugin.PluginLoader(cons)
    for d in config.PLUGIN_DIRS:
        if not os.path.exists(d):
            os.makedirs(d)
        plugin_loader.load_directory(d)

    @defer.inlineCallbacks
    def close_listeners(ignored):
        for port in ports:
            yield port.stopListening()

    d = deferToThread(cons.cmdloop)
    d.addCallback(close_listeners)
    d.addCallback(lambda ignored: reactor.stop())
    if delete_data_on_quit:
        d.addCallback(lambda ignored: delete_datafile())


def start():
    reactor.callWhenRunning(main)
    reactor.run()
    
if __name__ == '__main__':
    start()
