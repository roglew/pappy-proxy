import base64
import vim
import sys
import socket
import json

class CommError(Exception):
    pass

def communicate(data):
    global PAPPY_PORT
    # Submits data to the comm port of the proxy
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', int(vim.eval('s:commport'))))
    datastr = json.dumps(data)

    # Send our data
    total_sent = 0
    while total_sent < len(data):
        sent = s.send(datastr[total_sent:])
        assert sent != 0
        total_sent += sent
    s.send('\n')

    # Get our response
    retstr = ''
    c = ''
    while c != '\n':
        retstr = retstr + c
        c = s.recv(1)
        assert c != ''
    result = json.loads(retstr)
    if not result['success']:
        vim.command('echoerr %s' % result['message'])
        raise CommError(result['message'])
    return result

def read_line(conn):
    data = ''
    c = ''
    while c != '\n':
        data = data + c
        c = conn.read(1)
    return data

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

def set_up_windows():
    reqid = vim.eval("a:2")
    comm_port = vim.eval("a:3")
    vim.command("let s:commport=%d"%int(comm_port))
    # Get the left buffer
    vim.command("new")
    vim.command("only")
    b2 = vim.current.buffer
    vim.command("let s:b2=bufnr('$')")

    # Vsplit new file
    vim.command("vnew")
    b1 = vim.current.buffer
    vim.command("let s:b1=bufnr('$')")

    # Get the request
    comm_data = {"action": "get_request", "reqid": reqid}
    try:
        reqdata = communicate(comm_data)
    except CommError:
        return

    comm_data = {"action": "get_response", "reqid": reqid}
    try:
        rspdata = communicate(comm_data)
    except CommError:
        return

    # Set up the buffers
    set_buffer_content(b1, base64.b64decode(reqdata['full_request']))
    if 'full_response' in rspdata:
        set_buffer_content(b2, base64.b64decode(rspdata['full_response']))

    # Save the port/ssl setting
    vim.command("let s:repport=%d" % int(reqdata['port']))

    if reqdata['is_ssl']:
        vim.command("let s:repisssl=1")
    else:
        vim.command("let s:repisssl=0")

def submit_current_buffer():
    curbuf = vim.current.buffer
    b2_id = vim.eval("s:b2")
    b2 = vim.buffers[int(b2_id)]
    vim.command("let s:b1=bufnr('$')")
    vim.command("only")
    vim.command("rightbelow vertical new")
    vim.command("b %s" % b2_id)
    vim.command("wincmd h")
    
    full_request = '\n'.join(curbuf)
    commdata = {'action': 'submit',
                'full_request': base64.b64encode(full_request),
                'port':int(vim.eval("s:repport"))}
    if vim.eval("s:repisssl") == '1':
        commdata["is_ssl"] = True
    else:
        commdata["is_ssl"] = False
    result = communicate(commdata)
    set_buffer_content(b2, base64.b64decode(result['response']['full_response']))
    
# (left, right) = set_up_windows()
# set_buffer_content(left, 'Hello\nWorld')
# set_buffer_content(right, 'Hello\nOther\nWorld')
#print "Arg is %s" % vim.eval("a:arg")
run_command(vim.eval("a:1"))
