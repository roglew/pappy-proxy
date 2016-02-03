from pappyproxy.session import Session

MACRO_NAME = '{{macro_name}}'
SHORT_NAME = '{{short_name}}'
runargs = []

def init(args):
    global runargs
    runargs = args

def mangle_request(request):
    global runargs
    return request

def mangle_response(request):
    global runargs
    return request.response
