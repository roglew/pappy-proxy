#!/usr/bin/env python2

import cmd2
import config
import console
import comm
import context
import crochet
import http
import imp
import os
import schema.update
import proxy
import shutil
import sys
import sqlite3
from twisted.enterprise import adbapi
from twisted.internet import reactor, defer
from twisted.internet.threads import deferToThread
from twisted.internet.protocol import ServerFactory


crochet.no_setup()

def set_text_factory(conn):
    conn.text_factory = str

@defer.inlineCallbacks
def main():
    # If the data file doesn't exist, create it with restricted permissions
    if not os.path.isfile(config.DATAFILE):
        with os.fdopen(os.open(config.DATAFILE, os.O_CREAT, 0o0600), 'r') as f:
            pass

    # Set up data store
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

    d = deferToThread(console.ProxyCmd().cmdloop)
    d.addCallback(lambda ignored: reactor.stop())

    # Load the scope
    yield context.load_scope(http.dbpool)
    context.reset_to_scope()

if __name__ == '__main__':
    reactor.callWhenRunning(main)
    reactor.run()
