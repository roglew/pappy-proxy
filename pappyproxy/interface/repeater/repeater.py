import base64
import copy
import datetime
import json
import math
import re
import shlex
import socket
import sys
import vim
import threading

from collections import namedtuple
from urlparse import urlparse, ParseResult, parse_qs
from urllib import urlencode
import Cookie as hcookies

## STRIPPED DOWN COPY OF HTTP OBJECTS / COMMS

class MessageError(Exception):
    pass


class ProxyException(Exception):
    pass


class InvalidQuery(Exception):
    pass

class SocketClosed(Exception):
    pass

class SockBuffer:
    # I can't believe I have to implement this

    def __init__(self, sock):
        self.buf = [] # a list of chunks of strings
        self.s = sock
        self.closed = False
        
    def close(self):
        self.s.shutdown(socket.SHUT_RDWR)
        self.s.close()
        self.closed = True
        
    def _check_newline(self):
        for chunk in self.buf:
            if '\n' in chunk:
                return True
        return False
            
    def readline(self):
        # Receive until we get a newline, raise SocketClosed if socket is closed
        while True:
            try:
                data = self.s.recv(8192)
            except OSError:
                raise SocketClosed()
            if not data:
                raise SocketClosed()
            self.buf.append(data)
            if b'\n' in data:
                break

        # Combine chunks
        retbytes = bytes()
        n = 0
        for chunk in self.buf:
            n += 1
            if b'\n' in chunk:
                head, tail = chunk.split(b'\n', 1)
                retbytes += head
                self.buf = self.buf[n:]
                self.buf = [tail] + self.buf
                break
            else:
                retbytes += chunk
        return retbytes.decode()
    
    def send(self, data):
        try:
            self.s.send(data)
        except OSError:
            raise SocketClosed()

class Headers:
    def __init__(self, headers=None):
        if headers is None:
            self.headers = {}
        else:
            self.headers = headers
        
    def __contains__(self, hd):
        for k, _ in self.headers.items():
            if k.lower() == hd.lower():
                return True
        return False
        
    def add(self, k, v):
        try:
            l = self.headers[k.lower()]
            l.append((k,v))
        except KeyError:
            self.headers[k.lower()] = [(k,v)]
            
    def set(self, k, v):
        self.headers[k.lower()] = [(k,v)]
        
    def get(self, k):
        return self.headers[k.lower()][0][1]
    
    def delete(self, k):
        del self.headers[k.lower()]
    
    def pairs(self, key=None):
        for _, kvs in self.headers.items():
            for k, v in kvs:
                if key is None or k.lower() == key.lower():
                    yield (k, v)
    
    def dict(self):
        retdict = {}
        for _, kvs in self.headers.items():
            for k, v in kvs:
                if k in retdict:
                    retdict[k].append(v)
                else:
                    retdict[k] = [v]
        return retdict
    
class RequestContext:
    def __init__(self, client, query=None):
        self._current_query = []
        self.client = client
        if query is not None:
            self._current_query = query
        
    def _validate(self, query):
        self.client.validate_query(query)
    
    def set_query(self, query):
        self._validate(query)
        self._current_query = query

    def apply_phrase(self, phrase):
        self._validate([phrase])
        self._current_query.append(phrase)

    def pop_phrase(self):
        if len(self._current_query) > 0:
            self._current_query.pop()

    def apply_filter(self, filt):
        self._validate([[filt]])
        self._current_query.append([filt])
        
    @property
    def query(self):
        return copy.deepcopy(self._current_query)


class URL:
    def __init__(self, url):
        parsed = urlparse(url)
        if url is not None:
            parsed = urlparse(url)
            self.scheme = parsed.scheme
            self.netloc = parsed.netloc
            self.path = parsed.path
            self.params = parsed.params
            self.query = parsed.query
            self.fragment = parsed.fragment
        else:
            self.scheme = ""
            self.netloc = ""
            self.path = "/"
            self.params = ""
            self.query = ""
            self.fragment = ""
            
    def geturl(self, include_params=True):
        params = self.params
        query = self.query
        fragment = self.fragment

        if not include_params:
            params = ""
            query = ""
            fragment = ""

        r = ParseResult(scheme=self.scheme,
                        netloc=self.netloc,
                        path=self.path,
                        params=params,
                        query=query,
                        fragment=fragment)
        return r.geturl()
    
    def parameters(self):
        try:
            return parse_qs(self.query, keep_blank_values=True)
        except Exception:
            return []
    
    def param_iter(self):
        for k, vs in self.parameters().items():
            for v in vs:
                yield k, v
        
    def set_param(self, key, val):
        params = self.parameters()
        params[key] = [val]
        self.query = urlencode(params)
        
    def add_param(self, key, val):
        params = self.parameters()
        if key in params:
            params[key].append(val)
        else:
            params[key] = [val]
        self.query = urlencode(params)
        
    def del_param(self, key):
        params = self.parameters()
        del params[key]
        self.query = urlencode(params)
        
    def set_params(self, params):
        self.query = urlencode(params)
                

class InterceptMacro:
    """
    A class representing a macro that modifies requests as they pass through the
    proxy
    """

    def __init__(self):
        self.name = ''
        self.intercept_requests = False
        self.intercept_responses = False
        self.intercept_ws = False

    def __repr__(self):
        return "<InterceptingMacro (%s)>" % self.name

    def mangle_request(self, request):
        return request

    def mangle_response(self, request, response):
        return response

    def mangle_websocket(self, request, response, message):
        return message


class HTTPRequest:
    def __init__(self, method="GET", path="/", proto_major=1, proto_minor=1,
                 headers=None, body=bytes(), dest_host="", dest_port=80,
                 use_tls=False, time_start=None, time_end=None, db_id="",
                 tags=None, headers_only=False, storage_id=0):
        # http info
        self.method = method
        self.url = URL(path)
        self.proto_major = proto_major
        self.proto_minor = proto_minor

        self.headers = Headers()
        if headers is not None:
            for k, vs in headers.items():
                for v in vs:
                    self.headers.add(k, v)
        
        self.headers_only = headers_only
        self._body = bytes()
        if not headers_only:
            self.body = body
        
        # metadata
        self.dest_host = dest_host
        self.dest_port = dest_port
        self.use_tls = use_tls
        self.time_start = time_start or datetime.datetime(1970, 1, 1)
        self.time_end = time_end or datetime.datetime(1970, 1, 1)
        
        self.response = None
        self.unmangled = None
        self.ws_messages = []
        
        self.db_id = db_id
        self.storage_id = storage_id
        if tags is not None:
            self.tags = set(tags)
        else:
            self.tags = set()
        
    @property
    def body(self):
        return self._body
            
    @body.setter
    def body(self, bs):
        self.headers_only = False
        if type(bs) is str:
            self._body = bs.encode()
        elif type(bs) is bytes:
            self._body = bs
        else:
            raise Exception("invalid body type: {}".format(type(bs)))
        self.headers.set("Content-Length", str(len(self._body)))
        
    @property
    def content_length(self):
        if 'content-length' in self.headers:
            return int(self.headers.get('content-length'))
        return len(self.body)
        
    def status_line(self):
        sline = "{method} {path} HTTP/{proto_major}.{proto_minor}".format(
            method=self.method, path=self.url.geturl(), proto_major=self.proto_major,
            proto_minor=self.proto_minor).encode()
        return sline
    
    def headers_section(self):
        message = self.status_line() + b"\r\n"
        for k, v in self.headers.pairs():
            message += "{}: {}\r\n".format(k, v).encode()
        return message
        
    def full_message(self):
        message = self.headers_section()
        message += b"\r\n"
        message += self.body
        return message
    
    def parameters(self):
        try:
            return parse_qs(self.body.decode(), keep_blank_values=True)
        except Exception:
            return []
    
    def param_iter(self, ignore_content_type=False):
        if not ignore_content_type:
            if "content-type" not in self.headers:
                return
            if "www-form-urlencoded" not in self.headers.get("content-type").lower():
                return
        for k, vs in self.parameters().items():
            for v in vs:
                yield k, v
                
    def set_param(self, key, val):
        params = self.parameters()
        params[key] = [val]
        self.body = urlencode(params)
        
    def add_param(self, key, val):
        params = self.parameters()
        if key in params:
            params[key].append(val)
        else:
            params[key] = [val]
        self.body = urlencode(params)
        
    def del_param(self, key):
        params = self.parameters()
        del params[key]
        self.body = urlencode(params)
        
    def set_params(self, params):
        self.body = urlencode(params)

    def cookies(self):
        try:
            cookie = hcookies.BaseCookie()
            cookie.load(self.headers.get("cookie"))
            return cookie
        except Exception as e:
            return hcookies.BaseCookie()
    
    def cookie_iter(self):
        c = self.cookies()
        for k in c:
            yield k, c[k].value
                
    def set_cookie(self, key, val):
        c = self.cookies()
        c[key] = val
        self.set_cookies(c)
        
    def del_cookie(self, key):
        c = self.cookies()
        del c[key]
        self.set_cookies(c)
        
    def set_cookies(self, c):
        cookie_pairs = []
        if isinstance(c, hcookies.BaseCookie()):
            # it's a basecookie
            for k in c:
                cookie_pairs.append('{}={}'.format(k, c[k].value))
        else:
            # it's a dictionary
            for k, v in c.items():
                cookie_pairs.append('{}={}'.format(k, v))
        header_str = '; '.join(cookie_pairs)
        self.headers.set("Cookie", header_str)
        
    def copy(self):
        return HTTPRequest(
            method=self.method,
            path=self.url.geturl(),
            proto_major=self.proto_major,
            proto_minor=self.proto_minor,
            headers=self.headers.headers,
            body=self.body,
            dest_host=self.dest_host,
            dest_port=self.dest_port,
            use_tls=self.use_tls,
            tags=copy.deepcopy(self.tags),
            headers_only=self.headers_only,
        )
    

class HTTPResponse:
    def __init__(self, status_code=200, reason="OK", proto_major=1, proto_minor=1,
                 headers=None, body=bytes(), db_id="", headers_only=False):
        self.status_code = status_code
        self.reason = reason
        self.proto_major = proto_major
        self.proto_minor = proto_minor

        self.headers = Headers()
        if headers is not None:
            for k, vs in headers.items():
                for v in vs:
                    self.headers.add(k, v)
        
        self.headers_only = headers_only
        self._body = bytes()
        if not headers_only:
            self.body = body
        
        self.unmangled = None
        self.db_id = db_id

    @property
    def body(self):
        return self._body

    @body.setter
    def body(self, bs):
        self.headers_only = False
        if type(bs) is str:
            self._body = bs.encode()
        elif type(bs) is bytes:
            self._body = bs
        else:
            raise Exception("invalid body type: {}".format(type(bs)))
        self.headers.set("Content-Length", str(len(self._body)))
        
    @property
    def content_length(self):
        if 'content-length' in self.headers:
            return int(self.headers.get('content-length'))
        return len(self.body)

    def status_line(self):
        sline = "HTTP/{proto_major}.{proto_minor} {status_code} {reason}".format(
            proto_major=self.proto_major, proto_minor=self.proto_minor,
            status_code=self.status_code, reason=self.reason).encode()
        return sline

    def headers_section(self):
        message = self.status_line() + b"\r\n"
        for k, v in self.headers.pairs():
            message += "{}: {}\r\n".format(k, v).encode()
        return message

    def full_message(self):
        message = self.headers_section()
        message += b"\r\n"
        message += self.body
        return message
    
    def cookies(self):
        try:
            cookie = hcookies.BaseCookie()
            for _, v in self.headers.pairs('set-cookie'):
                cookie.load(v)
            return cookie
        except Exception as e:
            return hcookies.BaseCookie()

    def cookie_iter(self):
        c = self.cookies()
        for k in c:
            yield k, c[k].value
                
    def set_cookie(self, key, val):
        c = self.cookies()
        c[key] = val
        self.set_cookies(c)
        
    def del_cookie(self, key):
        c = self.cookies()
        del c[key]
        self.set_cookies(c)
        
    def set_cookies(self, c):
        self.headers.delete("set-cookie")
        if isinstance(c, hcookies.BaseCookie):
            cookies = c
        else:
            cookies = hcookies.BaseCookie()
            for k, v in c.items():
                cookies[k] = v
        for _, m in c.items():
            self.headers.add("Set-Cookie", m.OutputString())

    def copy(self):
        return HTTPResponse(
            status_code=self.status_code,
            reason=self.reason,
            proto_major=self.proto_major,
            proto_minor=self.proto_minor,
            headers=self.headers.headers,
            body=self.body,
            headers_only=self.headers_only,
        )

class WSMessage:
    def __init__(self, is_binary=True, message=bytes(), to_server=True,
                 timestamp=None, db_id=""):
        self.is_binary = is_binary
        self.message = message
        self.to_server = to_server
        self.timestamp = timestamp or datetime.datetime(1970, 1, 1)
        
        self.unmangled = None
        self.db_id = db_id
        
    def copy(self):
        return WSMessage(
            is_binary=self.is_binary,
            message=self.message,
            to_server=self.to_server,
        )

ScopeResult = namedtuple("ScopeResult", ["is_custom", "filter"])
ListenerResult = namedtuple("ListenerResult", ["lid", "addr"])
GenPemCertsResult = namedtuple("GenPemCertsResult", ["key_pem", "cert_pem"])
SavedQuery = namedtuple("SavedQuery", ["name", "query"])
SavedStorage = namedtuple("SavedStorage", ["storage_id", "description"])

def messagingFunction(func):
    def f(self, *args, **kwargs):
        if self.is_interactive:
            raise MessageError("cannot be called while other message is interactive")
        if self.closed:
            raise MessageError("connection is closed")
        return func(self, *args, **kwargs)
    return f
        
class ProxyConnection:
    next_id = 1
    def __init__(self, kind="", addr=""):
        self.connid = ProxyConnection.next_id
        ProxyConnection.next_id += 1
        self.sbuf = None
        self.buf = bytes()
        self.parent_client = None
        self.debug = False
        self.is_interactive = False
        self.closed = True
        self.sock_lock_read = threading.Lock()
        self.sock_lock_write = threading.Lock()
        self.kind = None
        self.addr = None
        
        if kind.lower() == "tcp":
            tcpaddr, port = addr.rsplit(":", 1)
            self.connect_tcp(tcpaddr, int(port))
        elif kind.lower() == "unix":
            self.connect_unix(addr)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def connect_tcp(self, addr, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((addr, port))
        self.sbuf = SockBuffer(s)
        self.closed = False
        self.kind = "tcp"
        self.addr = "{}:{}".format(addr, port)

    def connect_unix(self, addr):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(addr)
        self.sbuf = SockBuffer(s)
        self.closed = False
        self.kind = "unix"
        self.addr = addr
        
    @property
    def maddr(self):
        if self.kind is not None:
            return "{}:{}".format(self.kind, self.addr)
        else:
            return None
        
    def close(self):
        self.sbuf.close()
        if self.parent_client is not None:
            self.parent_client.conns.remove(self)
        self.closed = True
    
    def read_message(self):
        with self.sock_lock_read:
            l = self.sbuf.readline()
            if self.debug:
                print("<({}) {}".format(self.connid, l))
            j = json.loads(l)
            if "Success" in j and j["Success"] == False:
                if "Reason" in j:
                    raise MessageError(j["Reason"])
                raise MessageError("unknown error")
            return j
    
    def submit_command(self, cmd):
        with self.sock_lock_write:
            ln = json.dumps(cmd).encode()+b"\n"
            if self.debug:
                print(">({}) {} ".format(self.connid, ln.decode()))
            self.sbuf.send(ln)
        
    def reqrsp_cmd(self, cmd):
        self.submit_command(cmd)
        ret = self.read_message()
        if ret is None:
            raise Exception()
        return ret
    
    ###########
    ## Commands
    
    @messagingFunction
    def ping(self):
        cmd = {"Command": "Ping"}
        result = self.reqrsp_cmd(cmd)
        return result["Ping"]
    
    @messagingFunction
    def submit(self, req, storage=None):
        cmd = {
            "Command": "Submit",
            "Request": encode_req(req),
            "Storage": 0,
        }
        if storage is not None:
            cmd["Storage"] = storage
        result = self.reqrsp_cmd(cmd)
        if "SubmittedRequest" not in result:
            raise MessageError("no request returned")
        req = decode_req(result["SubmittedRequest"])
        req.storage_id = storage
        return req
    
    @messagingFunction
    def save_new(self, req, storage):
        reqd = encode_req(req)
        cmd = {
            "Command": "SaveNew",
            "Request": encode_req(req),
            "Storage": storage,
        }
        result = self.reqrsp_cmd(cmd)
        req.db_id = result["DbId"]
        req.storage_id = storage
        return result["DbId"]
    
    def _query_storage(self, q, storage, headers_only=False, max_results=0):
        cmd = {
            "Command": "StorageQuery",
            "Query": q,
            "HeadersOnly": headers_only,
            "MaxResults": max_results,
            "Storage": storage,
        }
        result = self.reqrsp_cmd(cmd)
        reqs = []
        for reqd in result["Results"]:
            req = decode_req(reqd, headers_only=headers_only)
            req.storage_id = storage
            reqs.append(req)
        return reqs
        
    @messagingFunction
    def query_storage(self, q, storage, max_results=0, headers_only=False):
        return self._query_storage(q, storage, headers_only=headers_only, max_results=max_results)
        
    @messagingFunction
    def req_by_id(self, reqid, storage, headers_only=False):
        results = self._query_storage([[["dbid", "is", reqid]]], storage,
                                      headers_only=headers_only, max_results=1)
        if len(results) == 0:
            raise MessageError("request with id {} does not exist".format(reqid))
        return results[0]
    
    @messagingFunction
    def set_scope(self, filt):
        cmd = {
            "Command": "SetScope",
            "Query": filt,
        }
        self.reqrsp_cmd(cmd)
        
    @messagingFunction
    def get_scope(self):
        cmd = {
            "Command": "ViewScope",
        }
        result = self.reqrsp_cmd(cmd)
        ret = ScopeResult(result["IsCustom"], result["Query"])
        return ret
    
    @messagingFunction
    def add_tag(self, reqid, tag, storage):
        cmd = {
            "Command": "AddTag",
            "ReqId": reqid,
            "Tag": tag,
            "Storage": storage,
        }
        self.reqrsp_cmd(cmd)

    @messagingFunction
    def remove_tag(self, reqid, tag, storage):
        cmd = {
            "Command": "RemoveTag",
            "ReqId": reqid,
            "Tag": tag,
            "Storage": storage,
        }
        self.reqrsp_cmd(cmd)

    @messagingFunction
    def clear_tag(self, reqid, storage):
        cmd = {
            "Command": "ClearTag",
            "ReqId": reqid,
            "Storage": storage,
        }
        self.reqrsp_cmd(cmd)
        
    @messagingFunction
    def all_saved_queries(self, storage):
        cmd = {
            "Command": "AllSavedQueries",
            "Storage": storage,
        }
        results = self.reqrsp_cmd(cmd)
        queries = []
        for result in results["Queries"]:
            queries.append(SavedQuery(name=result["Name"], query=result["Query"]))
        return queries

    @messagingFunction
    def save_query(self, name, filt, storage):
        cmd = {
            "Command": "SaveQuery",
            "Name": name,
            "Query": filt,
            "Storage": storage,
        }
        self.reqrsp_cmd(cmd)

    @messagingFunction
    def load_query(self, name, storage):
        cmd = {
            "Command": "LoadQuery",
            "Name": name,
            "Storage": storage,
        }
        result = self.reqrsp_cmd(cmd)
        return result["Query"]

    @messagingFunction
    def delete_query(self, name, storage):
        cmd = {
            "Command": "DeleteQuery",
            "Name": name,
            "Storage": storage,
        }
        self.reqrsp_cmd(cmd)
        
    @messagingFunction
    def add_listener(self, addr, port):
        laddr = "{}:{}".format(addr, port)
        cmd = {
            "Command": "AddListener",
            "Type": "tcp",
            "Addr": laddr,
        }
        result = self.reqrsp_cmd(cmd)
        lid = result["Id"]
        return lid
    
    @messagingFunction
    def remove_listener(self, lid):
        cmd = {
            "Command": "RemoveListener",
            "Id": lid,
        }
        self.reqrsp_cmd(cmd)
        
    @messagingFunction
    def get_listeners(self):
        cmd = {
            "Command": "GetListeners",
        }
        result = self.reqrsp_cmd(cmd)
        results = []
        for r in result["Results"]:
            results.append(r["Id"], r["Addr"])
        return results
    
    @messagingFunction
    def load_certificates(self, pkey_file, cert_file):
        cmd = {
            "Command": "LoadCerts",
            "KeyFile": pkey_file,
            "CertificateFile": cert_file,
        }
        self.reqrsp_cmd(cmd)
        
    @messagingFunction
    def set_certificates(self, pkey_pem, cert_pem):
        cmd = {
            "Command": "SetCerts",
            "KeyPEMData": pkey_pem,
            "CertificatePEMData": cert_pem,
        }
        self.reqrsp_cmd(cmd)
        
    @messagingFunction
    def clear_certificates(self):
        cmd = {
            "Command": "ClearCerts",
        }
        self.reqrsp_cmd(cmd)

    @messagingFunction
    def generate_certificates(self, pkey_file, cert_file):
        cmd = {
            "Command": "GenCerts",
            "KeyFile": pkey_file,
            "CertFile": cert_file,
        }
        self.reqrsp_cmd(cmd)

    @messagingFunction
    def generate_pem_certificates(self):
        cmd = {
            "Command": "GenPEMCerts",
        }
        result = self.reqrsp_cmd(cmd)
        ret = GenPemCertsResult(result["KeyPEMData"], result["CertificatePEMData"])
        return ret
    
    @messagingFunction
    def validate_query(self, query):
        cmd = {
            "Command": "ValidateQuery",
            "Query": query,
        }
        try:
            result = self.reqrsp_cmd(cmd)
        except MessageError as e:
            raise InvalidQuery(str(e))
        
    @messagingFunction
    def add_sqlite_storage(self, path, desc):
        cmd = {
            "Command": "AddSQLiteStorage",
            "Path": path,
            "Description": desc
        }
        result = self.reqrsp_cmd(cmd)
        return result["StorageId"]

    @messagingFunction
    def add_in_memory_storage(self, desc):
        cmd = {
            "Command": "AddInMemoryStorage",
            "Description": desc
        }
        result = self.reqrsp_cmd(cmd)
        return result["StorageId"]

    @messagingFunction
    def close_storage(self, strage_id):
        cmd = {
            "Command": "CloseStorage",
            "StorageId": storage_id,
        }
        result = self.reqrsp_cmd(cmd)

    @messagingFunction
    def set_proxy_storage(self, storage_id):
        cmd = {
            "Command": "SetProxyStorage",
            "StorageId": storage_id,
        }
        result = self.reqrsp_cmd(cmd)

    @messagingFunction
    def list_storage(self):
        cmd = {
            "Command": "ListStorage",
        }
        result = self.reqrsp_cmd(cmd)
        ret = []
        for ss in result["Storages"]:
            ret.append(SavedStorage(ss["Id"], ss["Description"]))
        return ret
        
    @messagingFunction
    def intercept(self, macro):
        # Run an intercepting macro until closed

        from .util import log_error
        # Start intercepting
        self.is_interactive = True
        cmd = {
            "Command": "Intercept",
            "InterceptRequests": macro.intercept_requests,
            "InterceptResponses": macro.intercept_responses,
            "InterceptWS": macro.intercept_ws,
        }
        try:
            self.reqrsp_cmd(cmd)
        except Exception as e:
            self.is_interactive = False
            raise e
        
        def run_macro():
            while True:
                try:
                    msg = self.read_message()
                except MessageError as e:
                    log_error(str(e))
                    return
                except SocketClosed:
                    return

                def mangle_and_respond(msg):
                    retCmd = None
                    if msg["Type"] == "httprequest":
                        req = decode_req(msg["Request"])
                        newReq = macro.mangle_request(req)

                        if newReq is None:
                            retCmd = {
                                "Id": msg["Id"],
                                "Dropped": True,
                            }
                        else:
                            newReq.unmangled = None
                            newReq.response = None
                            newReq.ws_messages = []

                            retCmd = {
                                "Id": msg["Id"],
                                "Dropped": False,
                                "Request": encode_req(newReq),
                            }
                    elif msg["Type"] == "httpresponse":
                        req = decode_req(msg["Request"])
                        rsp = decode_rsp(msg["Response"])
                        newRsp = macro.mangle_response(req, rsp)

                        if newRsp is None:
                            retCmd = {
                                "Id": msg["Id"],
                                "Dropped": True,
                            }
                        else:
                            newRsp.unmangled = None

                            retCmd = {
                                "Id": msg["Id"],
                                "Dropped": False,
                                "Response": encode_rsp(newRsp),
                            }
                    elif msg["Type"] == "wstoserver" or msg["Type"] == "wstoclient":
                        req = decode_req(msg["Request"])
                        rsp = decode_rsp(msg["Response"])
                        wsm = decode_ws(msg["WSMessage"])
                        newWsm = macro.mangle_websocket(req, rsp, wsm)

                        if newWsm is None:
                            retCmd = {
                                "Id": msg["Id"],
                                "Dropped": True,
                            }
                        else:
                            newWsm.unmangled = None

                            retCmd = {
                                "Id": msg["Id"],
                                "Dropped": False,
                                "WSMessage": encode_ws(newWsm),
                            }
                    else:
                        raise Exception("Unknown message type: " + msg["Type"])
                    if retCmd is not None:
                        try:
                            self.submit_command(retCmd)
                        except SocketClosed:
                            return

                mangle_thread = threading.Thread(target=mangle_and_respond,
                                                 args=(msg,))
                mangle_thread.start()
        
        self.int_thread = threading.Thread(target=run_macro)
        self.int_thread.start()
    

ActiveStorage = namedtuple("ActiveStorage", ["type", "storage_id", "prefix"])

def _serialize_storage(stype, prefix):
    return "{}|{}".format(stype, prefix)
        
class ProxyClient:
    def __init__(self, binary=None, debug=False, conn_addr=None):
        self.binloc = binary
        self.proxy_proc = None
        self.ltype = None
        self.laddr = None
        self.debug = debug
        self.conn_addr = conn_addr
        
        self.conns = set()
        self.msg_conn = None # conn for single req/rsp messages
        
        self.context = RequestContext(self)
        
        self.storage_by_id = {}
        self.storage_by_prefix = {}
        self.proxy_storage = None
        
        self.reqrsp_methods = {
            "submit_command",
            #"reqrsp_cmd",
            "ping",
            #"submit",
            #"save_new",
            #"query_storage",
            #"req_by_id",
            "set_scope",
            "get_scope",
            # "add_tag",
            # "remove_tag",
            # "clear_tag",
            "all_saved_queries",
            "save_query",
            "load_query",
            "delete_query",
            "add_listener",
            "remove_listener",
            "get_listeners",
            "load_certificates",
            "set_certificates",
            "clear_certificates",
            "generate_certificates",
            "generate_pem_certificates",
            "validate_query",
            "list_storage",
            # "add_sqlite_storage",
            # "add_in_memory_storage",
            # "close_storage",
            # "set_proxy_storage",
        }
        
    def __enter__(self):
        if self.conn_addr is not None:
            self.msg_connect(self.conn_addr)
        else:
            self.execute_binary(binary=self.binloc, debug=self.debug)
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        
    def __getattr__(self, name):
        if name in self.reqrsp_methods:
            return getattr(self.msg_conn, name)
        raise NotImplementedError(name)

    @property
    def maddr(self):
        if self.ltype is not None:
            return "{}:{}".format(self.ltype, self.laddr)
        else:
            return None
        
    def execute_binary(self, binary=None, debug=False, listen_addr=None):
        self.binloc = binary
        args = [self.binloc]
        if listen_addr is not None:
            args += ["--msglisten", listen_addr]
        else:
            args += ["--msgauto"]

        if debug:
            args += ["--dbg"]
        self.proxy_proc = Popen(args, stdout=PIPE, stderr=PIPE)

        # Wait for it to start and make connection
        listenstr = self.proxy_proc.stdout.readline().rstrip()
        self.msg_connect(listenstr.decode())
        
    def msg_connect(self, addr):
        self.ltype, self.laddr = addr.split(":", 1)
        self.msg_conn = self.new_conn()
        self._get_storage()
        
    def close(self):
        conns = list(self.conns)
        for conn in conns:
            conn.close()
        if self.proxy_proc is not None:
            self.proxy_proc.terminate()

    def new_conn(self):
        conn = ProxyConnection(kind=self.ltype, addr=self.laddr)
        conn.parent_client = self
        conn.debug = self.debug
        self.conns.add(conn)
        return conn
    
    # functions involving storage
    
    def _add_storage(self, storage, prefix):
        self.storage_by_prefix[prefix] = storage
        self.storage_by_id[storage.storage_id] = storage
        
    def _clear_storage(self):
        self.storage_by_prefix = {}
        self.storage_by_id = {}

    def _get_storage(self):
        self._clear_storage()
        storages = self.list_storage()
        for s in storages:
            stype, prefix = s.description.split("|")
            storage = ActiveStorage(stype, s.storage_id, prefix)
            self._add_storage(storage, prefix)
        
    def parse_reqid(self, reqid):
        if reqid[0].isalpha():
            prefix = reqid[0]
            realid = reqid[1:]
        else:
            prefix = ""
            realid = reqid
        storage = self.storage_by_prefix[prefix]
        return storage, realid
        
    def storage_iter(self):
        for _, s in self.storage_by_id.items():
            yield s
            
    def _stg_or_def(self, storage):
        if storage is None:
            return self.proxy_storage
        return storage
    
    def in_context_requests(self, headers_only=False, max_results=0):
        results = self.query_storage(self.context.query,
                                     headers_only=headers_only,
                                     max_results=max_results)
        ret = results
        if max_results > 0 and len(results) > max_results:
            ret = results[:max_results]
        return ret
    
    def prefixed_reqid(self, req):
        prefix = ""
        if req.storage_id in self.storage_by_id:
            s = self.storage_by_id[req.storage_id]
            prefix = s.prefix
        return "{}{}".format(prefix, req.db_id)
    
    # functions that don't just pass through to underlying conn
    
    def add_sqlite_storage(self, path, prefix):
        desc = _serialize_storage("sqlite", prefix)
        sid = self.msg_conn.add_sqlite_storage(path, desc)
        s = ActiveStorage(type="sqlite", storage_id=sid, prefix=prefix)
        self._add_storage(s, prefix)
        return s

    def add_in_memory_storage(self, prefix):
        desc = _serialize_storage("inmem", prefix)
        sid = self.msg_conn.add_in_memory_storage(desc)
        s = ActiveStorage(type="inmem", storage_id=sid, prefix=prefix)
        self._add_storage(s, prefix)
        return s
    
    def close_storage(self, storage_id):
        s = self.storage_by_id[storage_id]
        self.msg_conn.close_storage(s.storage_id)
        del self.storage_by_id[s.storage_id]
        del self.storage_by_prefix[s.storage_prefix]
        
    def set_proxy_storage(self, storage_id):
        s = self.storage_by_id[storage_id]
        self.msg_conn.set_proxy_storage(s.storage_id)
        self.proxy_storage = storage_id
        
    def save_new(self, req, storage=None):
        self.msg_conn.save_new(req, storage=self._stg_or_def(storage))
        
    def submit(self, req, storage=None):
        self.msg_conn.submit(req, storage=self._stg_or_def(storage))

    def query_storage(self, q, max_results=0, headers_only=False, storage=None):
        results = []
        if storage is None:
            for s in self.storage_iter():
                results += self.msg_conn.query_storage(q, max_results=max_results,
                                                       headers_only=headers_only,
                                                       storage=s.storage_id)
        else:
            results += self.msg_conn.query_storage(q, max_results=max_results,
                                                   headers_only=headers_only,
                                                   storage=storage)
        results.sort(key=lambda req: req.time_start)
        results = [r for r in reversed(results)]
        return results
            
    def req_by_id(self, reqid, headers_only=False):
        storage, rid = self.parse_reqid(reqid)
        return self.msg_conn.req_by_id(rid, headers_only=headers_only,
                                       storage=storage.storage_id)

    # for these and submit, might need storage stored on the request itself
    def add_tag(self, reqid, tag, storage=None):
        self.msg_conn.add_tag(reqid, tag, storage=self._stg_or_def(storage))

    def remove_tag(self, reqid, tag, storage=None):
        self.msg_conn.remove_tag(reqid, tag, storage=self._stg_or_def(storage))

    def clear_tag(self, reqid, storage=None):
        self.msg_conn.clear_tag(reqid, storage=self._stg_or_def(storage))

    def all_saved_queries(self, storage=None):
        self.msg_conn.all_saved_queries(storage=None)

    def save_query(self, name, filt, storage=None):
        self.msg_conn.save_query(name, filt, storage=self._stg_or_def(storage))

    def load_query(self, name, storage=None):
        self.msg_conn.load_query(name, storage=self._stg_or_def(storage))

    def delete_query(self, name, storage=None):
        self.msg_conn.delete_query(name, storage=self._stg_or_def(storage))


def decode_req(result, headers_only=False):
    if "StartTime" in result:
        time_start = time_from_nsecs(result["StartTime"])
    else:
        time_start = None

    if "EndTime" in result:
        time_end = time_from_nsecs(result["EndTime"])
    else:
        time_end = None
        
    if "DbId" in result:
        db_id = result["DbId"]
    else:
        db_id = ""

    if "Tags" in result:
        tags = result["Tags"]
    else:
        tags = ""

    ret = HTTPRequest(
        method=result["Method"],
        path=result["Path"],
        proto_major=result["ProtoMajor"],
        proto_minor=result["ProtoMinor"],
        headers=copy.deepcopy(result["Headers"]),
        body=base64.b64decode(result["Body"]),
        dest_host=result["DestHost"],
        dest_port=result["DestPort"],
        use_tls=result["UseTLS"],
        time_start=time_start,
        time_end=time_end,
        tags=tags,
        headers_only=headers_only,
        db_id=db_id,
        )
    
    if "Unmangled" in result:
        ret.unmangled = decode_req(result["Unmangled"], headers_only=headers_only)
    if "Response" in result:
        ret.response = decode_rsp(result["Response"], headers_only=headers_only)
    if "WSMessages" in result:
        for wsm in result["WSMessages"]:
            ret.ws_messages.append(decode_ws(wsm))
    return ret

def decode_rsp(result, headers_only=False):
    ret = HTTPResponse(
        status_code=result["StatusCode"],
        reason=result["Reason"],
        proto_major=result["ProtoMajor"],
        proto_minor=result["ProtoMinor"],
        headers=copy.deepcopy(result["Headers"]),
        body=base64.b64decode(result["Body"]),
        headers_only=headers_only,
    )
    
    if "Unmangled" in result:
        ret.unmangled = decode_rsp(result["Unmangled"], headers_only=headers_only)
    return ret

def decode_ws(result):
    timestamp = None
    db_id = ""

    if "Timestamp" in result:
        timestamp = time_from_nsecs(result["Timestamp"])
    if "DbId" in result:
        db_id = result["DbId"]

    ret = WSMessage(
        is_binary=result["IsBinary"],
        message=base64.b64decode(result["Message"]),
        to_server=result["ToServer"],
        timestamp=timestamp,
        db_id=db_id,
    )
    
    if "Unmangled" in result:
        ret.unmangled = decode_ws(result["Unmangled"])

    return ret

def encode_req(req, int_rsp=False):
    msg = {
	"DestHost": req.dest_host,
	"DestPort": req.dest_port,
	"UseTLS": req.use_tls,
	"Method": req.method,
	"Path": req.url.geturl(),
	"ProtoMajor": req.proto_major,
	"ProtoMinor": req.proto_major,
	"Headers": req.headers.dict(),
	"Body": base64.b64encode(copy.copy(req.body)).decode(),
    }
    
    if not int_rsp:
        msg["StartTime"] = time_to_nsecs(req.time_start)
        msg["EndTime"] = time_to_nsecs(req.time_end)
        if req.unmangled is not None:
            msg["Unmangled"] = encode_req(req.unmangled)
        if req.response is not None:
            msg["Response"] = encode_rsp(req.response)
            msg["WSMessages"] = []
        for wsm in req.ws_messages:
            msg["WSMessages"].append(encode_ws(wsm))
    return msg
            
def encode_rsp(rsp, int_rsp=False):
    msg = {
	"ProtoMajor": rsp.proto_major,
	"ProtoMinor": rsp.proto_minor,
	"StatusCode": rsp.status_code,
	"Reason": rsp.reason,
	"Headers": rsp.headers.dict(),
	"Body": base64.b64encode(copy.copy(rsp.body)).decode(),
    }
    
    if not int_rsp:
        if rsp.unmangled is not None:
            msg["Unmangled"] = encode_rsp(rsp.unmangled)
    return msg

def encode_ws(ws, int_rsp=False):
    msg = {
	"Message": base64.b64encode(ws.message).decode(),
	"IsBinary": ws.is_binary,
	"toServer": ws.to_server,
    }
    if not int_rsp:
        if ws.unmangled is not None:
            msg["Unmangled"] = encode_ws(ws.unmangled)
        msg["Timestamp"] = time_to_nsecs(ws.timestamp)
        msg["DbId"] = ws.db_id
    return msg

def time_from_nsecs(nsecs):
    secs = nsecs/1000000000
    t = datetime.datetime.utcfromtimestamp(secs)
    return t

def time_to_nsecs(t):
    if t is None:
        return None
    secs = (t-datetime.datetime(1970,1,1)).total_seconds()
    return int(math.floor(secs * 1000000000))

RequestStatusLine = namedtuple("RequestStatusLine", ["method", "path", "proto_major", "proto_minor"])
ResponseStatusLine = namedtuple("ResponseStatusLine", ["proto_major", "proto_minor", "status_code", "reason"])

def parse_req_sline(sline):
    if len(sline.split(b' ')) == 3:
        verb, path, version = sline.split(b' ')
    elif len(parts) == 2:
        verb, version = parts.split(b' ')
        path = b''
    else:
        raise ParseError("malformed statusline")
    raw_version = version[5:] # strip HTTP/
    pmajor, pminor = raw_version.split(b'.', 1)
    return RequestStatusLine(verb.decode(), path.decode(), int(pmajor), int(pminor))

def parse_rsp_sline(sline):
    if len(sline.split(b' ')) > 2:
        version, status_code, reason = sline.split(b' ', 2)
    else:
        version, status_code = sline.split(b' ', 1)
        reason = ''
    raw_version = version[5:] # strip HTTP/
    pmajor, pminor = raw_version.split(b'.', 1)
    return ResponseStatusLine(int(pmajor), int(pminor), int(status_code), reason.decode())

def _parse_message(bs, sline_parser):
    header_env, body = re.split(b"\r?\n\r?\n", bs, 1)
    status_line, header_bytes = re.split(b"\r?\n", header_env, 1)
    h = Headers()
    for l in re.split(b"\r?\n", header_bytes):
        k, v = l.split(b": ", 1)
        if k.lower != 'content-length':
            h.add(k.decode(), v.decode())
    h.add("Content-Length", str(len(body)))
    return (sline_parser(status_line), h, body)
        
def parse_request(bs, dest_host='', dest_port=80, use_tls=False):
    req_sline, headers, body = _parse_message(bs, parse_req_sline)
    req = HTTPRequest(
        method=req_sline.method,
        path=req_sline.path,
        proto_major=req_sline.proto_major,
        proto_minor=req_sline.proto_minor,
        headers=headers.dict(),
        body=body,
        dest_host=dest_host,
        dest_port=dest_port,
        use_tls=use_tls,
        )
    return req

def parse_response(bs):
    rsp_sline, headers, body = _parse_message(bs, parse_rsp_sline)
    rsp = HTTPResponse(
        status_code=rsp_sline.status_code,
        reason=rsp_sline.reason,
        proto_major=rsp_sline.proto_major,
        proto_minor=rsp_sline.proto_minor,
        headers=headers.dict(),
        body=body,
        )
    return rsp

## ACTUAL PLUGIN DATA ##                

def escape(s):
    return s.replace("'", "''")

def run_command(command):
    funcs = {
        "setup": set_up_windows,
        "submit": submit_current_buffer,
    }
    if command in funcs:
        funcs[command]()

def set_buffer_content(buf, text):
    buf[:] = None
    first = True
    for l in text.split('\n'):
        if first:
            buf[0] = l
            first = False
        else:
            buf.append(l)
            
def update_buffers(req):
    b1_id = int(vim.eval("s:b1"))
    b1 = vim.buffers[b1_id]

    b2_id = int(vim.eval("s:b2"))
    b2 = vim.buffers[b2_id]

    # Set up the buffers
    set_buffer_content(b1, req.full_message())

    if req.response is not None:
        set_buffer_content(b2, req.response.full_message())

    # Save the port, ssl, host setting
    vim.command("let s:dest_port=%d" % req.dest_port)
    vim.command("let s:dest_host='%s'" % escape(req.dest_host))

    if req.use_tls:
        vim.command("let s:use_tls=1")
    else:
        vim.command("let s:use_tls=0")
        
def set_conn(conn_type, conn_addr):
    conn_type = vim.command("let s:conn_type='%s'" % escape(conn_type))
    conn_addr = vim.command("let s:conn_addr='%s'" % escape(conn_addr))

def get_conn_addr():
    conn_type = vim.eval("s:conn_type")
    conn_addr = vim.eval("s:conn_addr")
    return (conn_type, conn_addr)

def set_up_windows():
    reqid = vim.eval("a:2")
    storage_id = vim.eval("a:3")
    msg_addr = vim.eval("a:4")

    vim.command("let s:storage_id=%d" % int(storage_id))
    
    # Get the left buffer
    vim.command("new")
    vim.command("only")
    b2 = vim.current.buffer
    vim.command("let s:b2=bufnr('$')")

    # Vsplit new file
    vim.command("vnew")
    b1 = vim.current.buffer
    vim.command("let s:b1=bufnr('$')")

    print msg_addr
    comm_type, comm_addr = msg_addr.split(":", 1)
    set_conn(comm_type, comm_addr)
    with ProxyConnection(kind=comm_type, addr=comm_addr) as conn:
        # Get the request
        req = conn.req_by_id(reqid, int(storage_id))
        update_buffers(req)
        
def dest_loc():
    dest_host = vim.eval("s:dest_host")
    dest_port = int(vim.eval("s:dest_port"))
    tls_num = vim.eval("s:use_tls")
    storage_id = int(vim.eval("s:storage_id"))
    if tls_num == "1":
        use_tls = True
    else:
        use_tls = False
    return (dest_host, dest_port, use_tls, storage_id)

def submit_current_buffer():
    curbuf = vim.current.buffer
    b2_id = int(vim.eval("s:b2"))
    b2 = vim.buffers[b2_id]
    vim.command("let s:b1=bufnr('$')")
    vim.command("only")
    vim.command("rightbelow vertical new")
    vim.command("b %d" % b2_id)
    vim.command("wincmd h")
    full_request = '\n'.join(curbuf)

    req = parse_request(full_request)
    dest_host, dest_port, use_tls, storage_id = dest_loc()
    req.dest_host = dest_host
    req.dest_port = dest_port
    req.use_tls = use_tls

    comm_type, comm_addr = get_conn_addr()
    with ProxyConnection(kind=comm_type, addr=comm_addr) as conn:
        new_req = conn.submit(req, storage=storage_id)
        conn.add_tag(new_req.db_id, "repeater", storage_id)
        update_buffers(new_req)
    
# (left, right) = set_up_windows()
# set_buffer_content(left, 'Hello\nWorld')
# set_buffer_content(right, 'Hello\nOther\nWorld')
#print "Arg is %s" % vim.eval("a:arg")
run_command(vim.eval("a:1"))
