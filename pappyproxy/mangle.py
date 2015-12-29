import copy
import os
import string
import subprocess
import tempfile
import pappyproxy

from pappyproxy import http
from twisted.internet import defer

MACRO_NAME = 'Pappy Text Editor Interceptor'

@defer.inlineCallbacks
def async_mangle_request(request):
    # This function gets called to mangle/edit requests passed through the proxy
    
    retreq = request
    # Write original request to the temp file
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tfName = tf.name
        tf.write(request.full_request)

    # Have the console edit the file
    yield pappyproxy.console.edit_file(tfName)

    # Create new mangled request from edited file
    with open(tfName, 'r') as f:
        text = f.read()

    os.remove(tfName)

    # Check if dropped
    if text == '':
        pappyproxy.proxy.log('Request dropped!')
        defer.returnValue(None)

    mangled_req = http.Request(text, update_content_length=True)
    mangled_req.port = request.port
    mangled_req.is_ssl = request.is_ssl

    # Check if it changed
    if mangled_req.full_request != request.full_request:
        retreq = mangled_req

    defer.returnValue(retreq)

@defer.inlineCallbacks
def async_mangle_response(request):
    # This function gets called to mangle/edit respones passed through the proxy

    retrsp = request.response
    # Write original response to the temp file
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tfName = tf.name
        tf.write(request.response.full_response)

    # Have the console edit the file
    yield pappyproxy.console.edit_file(tfName, front=True)

    # Create new mangled response from edited file
    with open(tfName, 'r') as f:
        text = f.read()

    os.remove(tfName)

    # Check if dropped
    if text == '':
        pappyproxy.proxy.log('Response dropped!')
        defer.returnValue(None)

    mangled_rsp = http.Response(text, update_content_length=True)

    if mangled_rsp.full_response != request.response.full_response:
        mangled_rsp.unmangled = request.response
        retrsp = mangled_rsp

    defer.returnValue(retrsp)
    
