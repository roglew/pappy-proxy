import copy
import json

default_config = """{
    "listeners": [
        {"iface": "127.0.0.1", "port": 8080}
    ],
    "proxy": {"use_proxy": false, "host": "", "port": 0, "is_socks": false}
}"""


class ProxyConfig:
    
    def __init__(self):
        self._listeners = [('127.0.0.1', 8080, None)]
        self._proxy = {'use_proxy': False, 'host': '', 'port': 0, 'is_socks': False}
        
    def load(self, fname):
        try:
            with open(fname, 'r') as f:
                config_info = json.loads(f.read())
        except IOError:
            config_info = json.loads(default_config)
            with open(fname, 'w') as f:
                f.write(default_config)
            
        # Listeners
        if 'listeners' in config_info:
            self._parse_listeners(config_info['listeners'])

        if 'proxy' in config_info:
            self._proxy = config_info['proxy']

    def _parse_listeners(self, listeners):
        self._listeners = []
        for info in listeners:
            if 'port' in info:
                port = info['port']
            else:
                port = 8080

            if 'interface' in info:
                iface = info['interface']
            elif 'iface' in info:
                iface = info['iface']
            else:
                iface = '127.0.0.1'

            if "transparent" in info:
                trans_info = info['transparent']
                transparent_dest = (trans_info.get('host', ""),
                                    trans_info.get('port', 0),
                                    trans_info.get('use_tls', False))
            else:
                transparent_dest = None

            self._listeners.append((iface, port, transparent_dest))
            
    @property
    def listeners(self):
        return copy.deepcopy(self._listeners)
    
    @listeners.setter
    def listeners(self, val):
        self._parse_listeners(val)
        
    @property
    def proxy(self):
        # don't use this, use the getters to get the parsed values
        return self._proxy
        
    @proxy.setter
    def proxy(self, val):
        self._proxy = val

    @property
    def use_proxy(self):
        if self._proxy is None:
            return False
        if 'use_proxy' in self._proxy:
            if self._proxy['use_proxy']:
                return True
        return False

    @property
    def proxy_host(self):
        if self._proxy is None:
            return ''
        if 'host' in self._proxy:
            return self._proxy['host']
        return ''

    @property
    def proxy_port(self):
        if self._proxy is None:
            return ''
        if 'port' in self._proxy:
            return self._proxy['port']
        return ''

    @property
    def proxy_username(self):
        if self._proxy is None:
            return ''
        if 'username' in self._proxy:
            return self._proxy['username']
        return ''

    @property
    def proxy_password(self):
        if self._proxy is None:
            return ''
        if 'password' in self._proxy:
            return self._proxy['password']
        return ''

    @property
    def use_proxy_creds(self):
        return ('username' in self._proxy or 'password' in self._proxy)

    @property
    def is_socks_proxy(self):
        if self._proxy is None:
            return False
        if 'is_socks' in self._proxy:
            if self._proxy['is_socks']:
                return True
        return False

