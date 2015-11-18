import console
import context
import proxy
import string
import subprocess
import tempfile
import http

from twisted.internet import defer

active_requests = {}

intercept_requests = False
intercept_responses = False

def set_intercept_requests(val):
    global intercept_requests
    intercept_requests = val

def set_intercept_responses(val):
    global intercept_responses
    intercept_responses = val

@defer.inlineCallbacks
def mangle_request(request, connection_id):
    # This function gets called to mangle/edit requests passed through the proxy
    global intercept_requests
    
    orig_req = http.Request(request.full_request)
    retreq = orig_req

    if context.in_scope(orig_req):
        if intercept_requests: # if we want to mangle...
            # Write original request to the temp file
            with tempfile.NamedTemporaryFile(delete=False) as tf:
                tfName = tf.name
                tf.write(orig_req.full_request)

            # Have the console edit the file
            yield console.edit_file(tfName)

            # Create new mangled request from edited file
            with open(tfName, 'r') as f:
                mangled_req = http.Request(f.read(), update_content_length=True)

            # Check if it changed
            if mangled_req.full_request != orig_req.full_request:
                # Set the object's metadata
                mangled_req.unmangled = orig_req
                retreq = mangled_req

            # Add our request to the context
        context.add_request(retreq)
    else:
        proxy.log('Out of scope! Request passed along unharmed', id=connection_id)

    active_requests[connection_id] = retreq
    retreq.submitted = True
    defer.returnValue(retreq)

@defer.inlineCallbacks
def mangle_response(response, connection_id):
    # This function gets called to mangle/edit respones passed through the proxy
    global intercept_responses
    #response = string.replace(response, 'cloud', 'butt')
    #response = string.replace(response, 'Cloud', 'Butt')

    myreq = active_requests[connection_id]

    orig_rsp = http.Response(response.full_response)
    retrsp = orig_rsp

    if context.in_scope(myreq):
        if intercept_responses: # If we want to mangle...
            # Write original request to the temp file
            with tempfile.NamedTemporaryFile(delete=False) as tf:
                tfName = tf.name
                tf.write(orig_rsp.full_response)

            # Have the console edit the file
            yield console.edit_file(tfName)
                
            # Create new mangled request from edited file
            with open(tfName, 'r') as f:
                mangled_rsp = http.Response(f.read(), update_content_length=True)

            if mangled_rsp.full_response != orig_rsp.full_response:
                mangled_rsp.unmangled = orig_rsp
                retrsp = mangled_rsp

        if not myreq.reqid:
            myreq.save()
            if myreq.unmangled:
                myreq.unmangled.save()
        myreq.response = retrsp
    else:
        proxy.log('Out of scope! Response passed along unharmed', id=connection_id)
    del active_requests[connection_id]
    myreq.response = retrsp
    context.filter_recheck()
    defer.returnValue(myreq)
    
def connection_lost(connection_id):
    del active_requests[connection_id]
