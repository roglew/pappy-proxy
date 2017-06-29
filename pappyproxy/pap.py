#!/usr/bin/env python3

import argparse
import sys
import time
import os

from .proxy import HTTPRequest, ProxyClient, MessageError
from .console import interface_loop
from .config import ProxyConfig
from .util import confirm

def fmt_time(t):
    timestr = strftime("%Y-%m-%d %H:%M:%S.%f", t)
    return timestr

def print_msg(msg, title):
    print("-"*10 + " " + title + " " + "-"*10)
    print(msg.full_message().decode())
    
def print_rsp(rsp):
    print_msg(rsp, "RESPONSE")
    if rsp.unmangled:
        print_msg(rsp, "UNMANGLED RESPONSE")
        
def print_ws(ws):
    print("ToServer=%s, IsBinary=%s")
    print(ws.message)

def print_req(req):
    print_msg(req, "REQUEST")
    if req.unmangled:
        print_msg(req, "UNMANGLED REQUEST")
    if req.response:
        print_rsp(req.response)
        
def generate_certificates(client, path):
    try:
        os.makedirs(path, 0o755)
    except os.error as e:
        if not os.path.isdir(path):
            raise e
    pkey_file = os.path.join(path, 'server.key')
    cert_file = os.path.join(path, 'server.pem')
    client.generate_certificates(pkey_file, cert_file)
    
def load_certificates(client, path):
    client.load_certificates(os.path.join(path, "server.pem"),
                             os.path.join(path, "server.key"))
        
def main():
    parser = argparse.ArgumentParser(description="Pappy client")
    parser.add_argument("--binary", nargs=1, help="location of the backend binary")
    parser.add_argument("--attach", nargs=1, help="attach to an already running backend")
    parser.add_argument("--dbgattach", nargs=1, help="attach to an already running backend and also perform setup")
    parser.add_argument('--debug', help='run in debug mode', action='store_true')
    parser.add_argument('--lite', help='run in lite mode', action='store_true')
    args = parser.parse_args()
    
    if args.binary is not None and args.attach is not None:
        print("Cannot provide both a binary location and an address to connect to")
        exit(1)

    data_dir = os.path.join(os.path.expanduser('~'), '.pappy')

    if args.binary is not None:
        binloc = args.binary[0]
        msg_addr = None
    elif args.attach is not None or args.dbgattach:
        binloc = None
        if args.attach is not None:
            msg_addr = args.attach[0]
        if args.dbgattach is not None:
            msg_addr = args.dbgattach[0]
    else:
        msg_addr = None
        try:
            # Try to get the binary from GOPATH
            gopath = os.environ["GOPATH"]
            binloc = os.path.join(gopath, "bin", "puppy")
        except:
            # Try to get the binary from ~/.pappy/puppy
            binloc = os.path.join(data_dir, "puppy")
            if not os.path.exists(binloc):
                print("Could not find puppy binary in GOPATH or ~/.pappy. Please ensure that it has been compiled, or pass in the binary location from the command line")
                exit(1)
    config = ProxyConfig()
    if not args.lite:
        config.load("./config.json")
    cert_dir = os.path.join(data_dir, "certs")
    
    with ProxyClient(binary=binloc, conn_addr=msg_addr, debug=args.debug) as client:
        try:
            load_certificates(client, cert_dir)
        except MessageError as e:
            print(str(e))
            if(confirm("Would you like to generate the certificates now?", "y")):
                generate_certificates(client, cert_dir)
                print("Certificates generated to {}".format(cert_dir))
                print("Be sure to add {} to your trusted CAs in your browser!".format(os.path.join(cert_dir, "server.pem")))
                load_certificates(client, cert_dir)
            else:
                print("Can not run proxy without SSL certificates")
                exit(1)
        try:
            # Only try and listen/set default storage if we're not attaching
            if args.attach is None:
                if args.lite:
                    storage = client.add_in_memory_storage("")
                else:
                    storage = client.add_sqlite_storage("./data.db", "")

                client.disk_storage = storage
                client.inmem_storage = client.add_in_memory_storage("m")
                client.set_proxy_storage(storage.storage_id)

                for iface, port, transparent in config.listeners:
                    try:
                        if transparent is not None:
                            destHost, destPort, destUseTLS = transparent
                            client.add_listener(iface, port, transparent=True,
                                    destHost=destHost, destPort=destPort, destUseTLS=destUseTLS)
                        else:
                            client.add_listener(iface, port)
                    except MessageError as e:
                        print(str(e))

                # Set upstream proxy
                if config.use_proxy:
                    client.set_proxy(config.use_proxy,
                                     config.proxy_host,
                                     config.proxy_port,
                                     config.is_socks_proxy)
            interface_loop(client)
        except MessageError as e:
            print(str(e))

if __name__ == "__main__":
    main()
    
def start():
    main()
