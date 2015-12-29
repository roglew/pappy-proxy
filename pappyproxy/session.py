from .http import ResponseCookie

class Session(object):

    def __init__(self, cookie_names=None, header_names=None,
                 cookie_vals=None, header_vals=None):
        self.cookies = cookie_names or []
        self.headers = header_names or []
        self.cookie_vals = cookie_vals or {}
        self.header_vals = header_vals or {}

        if cookie_vals:
            for k, v in cookie_vals.iteritems():
                if k not in self.cookies:
                    self.cookies.append(k)

        if header_vals:
            for k, v in header_vals.iteritems():
                if k not in self.headers:
                    self.headers.append(k)

    def apply_req(self, req):
        for k, v in self.cookie_vals.iteritems():
            if isinstance(v, ResponseCookie):
                req.cookies[v.key] = v.val
            else:
                req.cookies[k] = v
        for k, v in self.header_vals.iteritems():
            req.headers[k] = v

    def apply_rsp(self, rsp):
        for k, v in self.cookie_vals.iteritems():
            if isinstance(v, ResponseCookie):
                rsp.set_cookie(v)
            else:
                cookie_str = '%s=%s' % (k, v)
                rsp.set_cookie(ResponseCookie(cookie_str))
        # Don't apply headers to responses

    def get_req(self, req, cookies=None, headers=None):
        if cookies:
            for c in cookies:
                if c not in self.cookies:
                    self.cookies.append(c)
        if headers:
            for h in headers:
                if h not in self.headers:
                    self.headers.append(h)

        if cookies:
            for cookie in cookies:
                if cookie in req.cookies:
                    if cookie not in self.cookies:
                        self.cookies.append(cookie)
                    cookie_str = '%s=%s' % (cookie, req.cookies[cookie])
                    self.cookie_vals[cookie] = ResponseCookie(cookie_str)
        else:
            for k, v in req.cookies.all_pairs():
                if k in self.cookies:
                    cookie_str = '%s=%s' % (k, v)
                    self.cookie_vals[cookie] = ResponseCookie(cookie_str)
        if headers:
            for header in headers:
                if header in self.headers:
                    self.header_vals[header] = req.headers[header]

    def get_rsp(self, rsp, cookies=None):
        if cookies:
            for c in cookies:
                if c not in self.cookies:
                    self.cookies.append(c)

        if cookies:
            for cookie in cookies:
                if cookie in rsp.cookies:
                    if cookie not in self.cookies:
                        self.cookies.append(cookie)
                    self.cookie_vals[cookie] = rsp.cookies[cookie]
        else:
            for k, v in rsp.cookies.all_pairs():
                if v.key in self.cookies:
                    self.cookie_vals[v.key] = v
