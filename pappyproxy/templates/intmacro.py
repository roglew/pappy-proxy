from pappyproxy.session import Session

MACRO_NAME = '{{macro_name}}'
SHORT_NAME = '{{short_name}}'

def mangle_request(request):
    return request

def mangle_response(request):
    return request.response
