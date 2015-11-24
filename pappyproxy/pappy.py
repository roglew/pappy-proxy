#!/usr/bin/env python2

import argparse
import cmd2
import crochet
import imp
import os
import schema.update
import shutil
import sys
import sqlite3
import tempfile
from pappyproxy import console
from pappyproxy import config
from pappyproxy import comm
from pappyproxy import http
from pappyproxy import context
from pappyproxy import proxy
from twisted.enterprise import adbapi
from twisted.internet import reactor, defer
from twisted.internet.threads import deferToThread
from twisted.internet.protocol import ServerFactory


crochet.no_setup()

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
    settings = parse_args()

    if settings['lite']:
        conf_settings = config.get_default_config()
        conf_settings['debug_dir'] = None
        conf_settings['debug_to_file'] = False
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            conf_settings['data_file'] = tf.name
            print 'Temporary datafile is %s' % tf.name
        delete_data_on_quit = True
        config.load_settings(conf_settings)
    else:
        # Initialize config
        config.load_from_file('./config.json')
        delete_data_on_quit = False

    # If the data file doesn't exist, create it with restricted permissions
    if not os.path.isfile(config.DATAFILE):
        with os.fdopen(os.open(config.DATAFILE, os.O_CREAT, 0o0600), 'r') as f:
            pass
        
    dbpool = adbapi.ConnectionPool("sqlite3", config.DATAFILE,
                                   check_same_thread=False,
                                   cp_openfun=set_text_factory,
                                   cp_max=1)
    yield schema.update.update_schema(dbpool)
    http.init(dbpool)
    yield context.init()

    # Run the proxy
    if config.DEBUG_DIR and os.path.exists(config.DEBUG_DIR):
        shutil.rmtree(config.DEBUG_DIR)
        print 'Removing old debugging output'
    factory = ServerFactory()
    factory.protocol = proxy.ProxyServer
    listen_strs = []
    for listener in config.LISTENERS:
        reactor.listenTCP(listener[0], factory, interface=listener[1])
        listener_str = 'port %d' % listener[0]
        if listener[1] not in ('127.0.0.1', 'localhost'):
            listener_str += ' (bound to %s)' % listener[1]
        listen_strs.append(listener_str)
    if listen_strs:
        print 'Proxy is listening on %s' % (', '.join(listen_strs))

    com_factory = ServerFactory()
    com_factory.protocol = comm.CommServer
    # Make the port different for every instance of pappy, then pass it to
    # anything we run. Otherwise we can only have it running once on a machine
    comm_port = reactor.listenTCP(0, com_factory, interface='127.0.0.1')
    comm.set_comm_port(comm_port.getHost().port)

    sys.argv = [sys.argv[0]] # cmd2 tries to parse args
    d = deferToThread(console.ProxyCmd().cmdloop)
    d.addCallback(lambda ignored: reactor.stop())
    if delete_data_on_quit:
        d.addCallback(lambda ignored: delete_datafile())

    # Load the scope
    yield context.load_scope(http.dbpool)
    context.reset_to_scope()

def start():
    reactor.callWhenRunning(main)
    reactor.run()
    
if __name__ == '__main__':
    start()
