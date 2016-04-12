from .http import ResponseCookie

class Session(object):
    """
    A class used to maintain a session over multiple requests. Can remember cookies
    and apply a specific header to requests. It is also possible to give the session
    a list of cookie names and it will only save those cookies.
    """

    def __init__(self, cookie_names=None, header_names=None,
                 cookie_vals=None, header_vals=None):
        """
        Session(self, cookie_names=None, header_names=None, cookie_vals=None, header_vals=None)
        Constructor

        :param cookie_names: A whitelist for cookies that should be saved from :func:`~pappyproxy.session.Session.save_req` and :func:`~pappyproxy.session.Session.save_rsp` in the session. If no values are given, all cookies will be saved.
        :param header_names: A whitelist for headers that should be saved from :func:`~pappyproxy.session.Session.save_req` in the session. If no values are given, no headers will be saved.
        :param cookie_vals: A dictionary of cookies to populate the session session with. The key should be the cookie name, and the value can be either a string or a :class:`~pappyproxy.http.ResponseCookie`. If a :class:`~pappyproxy.http.ResponseCookie` is given, its flags will be used in :func:`~pappyproxy.session.Session.apply_rsp`.
        :param header_vals: A dictionary of header values to populate the session with. The key should be the header name and the value should be a string which should be the header value.
        """

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

    def _cookie_obj(k, v):
        """
        Returns the value as a cookie object regardless of if the cookie is a string or a ResponseCookie.
        """
        if isinstance(v, ResponseCookie):
            return v
        else:
            cookie_str = '%s=%s' % (k, v)
            return ResponseCookie(cookie_str)

    def _cookie_val(v):
        """
        Returns the value of the cookie regardless of if the value is a string or a ResponseCookie
        """
        if isinstance(v, ResponseCookie):
            return v.val
        else:
            return v

    def apply_req(self, req):
        """
        apply_req(request)
        
        Apply saved headers and cookies to the request
        """

        for k, v in self.cookie_vals.iteritems():
            req.cookies[k] = self._cookie_val(v)
        for k, v in self.header_vals.iteritems():
            req.headers[k] = v

    def apply_rsp(self, rsp):
        """
        apply_rsp(response)
        
        Will add a Set-Cookie header for each saved cookie. Will not
        apply any saved headers. If the cookie was added from a call to
        :func:`~pappyproxy.session.Session.save_rsp`, the Set-Cookie flags
        will be the same as the original response.
        """

        for k, v in self.cookie_vals.iteritems():
            val = self._cookie_obj(v)
            rsp.set_cookie(val)
        # Don't apply headers to responses

    def save_req(self, req, cookies=None, headers=None):
        """
        save_req(req, cookies=None, headers=None)

        Updates the state of the session from the given request.
        Cookie and headers can be added to their whitelists by passing in a list
        for either ``cookies`` or ``headers``.
        """

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

    def save_rsp(self, rsp, cookies=None):
        """
        save_rsp(rsp, cookies=None)

        Update the state of the session from the response. Only cookies can be
        updated from a response. Additional values can be added to the whitelist
        by passing in a list of values for the ``cookies`` parameter.
        """
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

    def set_cookie(key, val):
        """
        set_cookie(key, val)
        
        Set a cookie in the session. ``val`` can be either a string or a :class:`~pappyproxy.http.ResponseCookie`.
        If a :class:`~pappyproxy.http.ResponseCookie` is used, make sure its ``key`` value is the same as
        the key passed in to the function.
        """
        self.cookie_vals[key] = val

    def get_cookie(key):
        """
        get_cookie(key)

        Returns a string with the value of the cookie with the given string, even if the value is a :class:`~pappyproxy.http.ResponseCookie`.
        If you want to get a :class:`~pappyproxy.http.ResponseCookie`, use :func:`~pappyproxy.session.Session.get_rsp_cookie`.
        """
        if not key in self.cookie_vals:
            raise KeyError('Cookie is not stored in session.')
        v = self.cookie_vals[key]
        return self._cookie_val(v)

    def get_rsp_cookie(key):
        """
        get_rsp_cookie(key)

        Returns the :class:`~pappyproxy.http.ResponseCookie` associated with the key
        regardless of if the value is stored as a string or a :class:`~pappyproxy.http.ResponseCookie`.
        """
        if not key in self.cookie_vals:
            raise KeyError('Cookie is not stored in session.')
        v = self.cookie_vals[key]
        return self._cookie_obj(v)

