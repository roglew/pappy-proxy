import StringIO
import base64
import clipboard
import gzip
import shlex
import string
import urllib

from pappyproxy.util import PappyException, hexdump

def print_maybe_bin(s):
    binary = False
    for c in s:
        if c not in string.printable:
            binary = True
            break
    if binary:
        print hexdump(s)
    else:
        print s
        
def asciihex_encode_helper(s):
    return ''.join('{0:x}'.format(ord(c)) for c in s)

def asciihex_decode_helper(s):
    ret = []
    try:
        for a, b in zip(s[0::2], s[1::2]):
            c = a+b
            ret.append(chr(int(c, 16)))
        return ''.join(ret)
    except Exception as e:
        raise PappyException(e)
    
def gzip_encode_helper(s):
    out = StringIO.StringIO()
    with gzip.GzipFile(fileobj=out, mode="w") as f:
        f.write(s)
    return out.getvalue()
    
def gzip_decode_helper(s):
    dec_data = gzip.GzipFile('', 'rb', 9, StringIO.StringIO(s))
    dec_data = dec_data.read()
    return dec_data
        
def _code_helper(line, func, copy=True):
    args = shlex.split(line)
    if not args:
        s = clipboard.paste()
        s = func(s)
        if copy:
            try:
                clipboard.copy(s)
            except:
                print 'Result cannot be copied to the clipboard. Result not copied.'
        return s
    else:
        s = func(args[0].strip())
        if copy:
            try:
                clipboard.copy(s)
            except:
                print 'Result cannot be copied to the clipboard. Result not copied.'
        return s

def base64_decode(line):
    """
    Base64 decode a string.
    If no string is given, will decode the contents of the clipboard.
    Results are copied to the clipboard.
    """
    print_maybe_bin(_code_helper(line, base64.b64decode))

def base64_encode(line):
    """
    Base64 encode a string.
    If no string is given, will encode the contents of the clipboard.
    Results are copied to the clipboard.
    """
    print_maybe_bin(_code_helper(line, base64.b64encode))

def url_decode(line):
    """
    URL decode a string.
    If no string is given, will decode the contents of the clipboard.
    Results are copied to the clipboard.
    """
    print_maybe_bin(_code_helper(line, urllib.unquote))

def url_encode(line):
    """
    URL encode special characters in a string.
    If no string is given, will encode the contents of the clipboard.
    Results are copied to the clipboard.
    """
    print_maybe_bin(_code_helper(line, urllib.quote_plus))

def asciihex_decode(line):
    """
    Decode an ascii hex string.
    If no string is given, will decode the contents of the clipboard.
    Results are copied to the clipboard.
    """
    print_maybe_bin(_code_helper(line, asciihex_decode_helper))

def asciihex_encode(line):
    """
    Convert all the characters in a line to hex and combine them.
    If no string is given, will encode the contents of the clipboard.
    Results are copied to the clipboard.
    """
    print_maybe_bin(_code_helper(line, asciihex_encode_helper))
    
def gzip_decode(line):
    """
    Un-gzip a string.
    If no string is given, will decompress the contents of the clipboard.
    Results are copied to the clipboard.
    """
    print_maybe_bin(_code_helper(line, gzip_decode_helper))

def gzip_encode(line):
    """
    Gzip a string.
    If no string is given, will decompress the contents of the clipboard.
    Results are NOT copied to the clipboard.
    """
    print_maybe_bin(_code_helper(line, gzip_encode_helper, copy=False))

def base64_decode_raw(line):
    """
    Same as base64_decode but the output will never be printed as a hex dump and
    results will not be copied. It is suggested you redirect the output
    to a file.
    """
    print _code_helper(line, base64.b64decode, copy=False)

def base64_encode_raw(line):
    """
    Same as base64_encode but the output will never be printed as a hex dump and
    results will not be copied. It is suggested you redirect the output
    to a file.
    """
    print _code_helper(line, base64.b64encode, copy=False)

def url_decode_raw(line):
    """
    Same as url_decode but the output will never be printed as a hex dump and
    results will not be copied. It is suggested you redirect the output
    to a file.
    """
    print _code_helper(line, urllib.unquote, copy=False)

def url_encode_raw(line):
    """
    Same as url_encode but the output will never be printed as a hex dump and
    results will not be copied. It is suggested you redirect the output
    to a file.
    """
    print _code_helper(line, urllib.quote_plus, copy=False)

def asciihex_decode_raw(line):
    """
    Same as asciihex_decode but the output will never be printed as a hex dump and
    results will not be copied. It is suggested you redirect the output
    to a file.
    """
    print _code_helper(line, asciihex_decode_helper, copy=False)

def asciihex_encode_raw(line):
    """
    Same as asciihex_encode but the output will never be printed as a hex dump and
    results will not be copied. It is suggested you redirect the output
    to a file.
    """
    print _code_helper(line, asciihex_encode_helper, copy=False)
    
def gzip_decode_raw(line):
    """
    Same as gzip_decode but the output will never be printed as a hex dump and
    results will not be copied. It is suggested you redirect the output
    to a file.
    """
    print _code_helper(line, gzip_decode_helper, copy=False)

def gzip_encode_raw(line):
    """
    Same as gzip_encode but the output will never be printed as a hex dump and
    results will not be copied. It is suggested you redirect the output
    to a file.
    """
    print _code_helper(line, gzip_encode_helper, copy=False)
        
def load_cmds(cmd):
    cmd.set_cmds({
        'base64_decode': (base64_decode, None),
        'base64_encode': (base64_encode, None),
        'asciihex_decode': (asciihex_decode, None),
        'asciihex_encode': (asciihex_encode, None),
        'url_decode': (url_decode, None),
        'url_encode': (url_encode, None),
        'gzip_decode': (gzip_decode, None),
        'gzip_encode': (gzip_encode, None),
        'base64_decode_raw': (base64_decode_raw, None),
        'base64_encode_raw': (base64_encode_raw, None),
        'asciihex_decode_raw': (asciihex_decode_raw, None),
        'asciihex_encode_raw': (asciihex_encode_raw, None),
        'url_decode_raw': (url_decode_raw, None),
        'url_encode_raw': (url_encode_raw, None),
        'gzip_decode_raw': (gzip_decode_raw, None),
        'gzip_encode_raw': (gzip_encode_raw, None),
    })
    cmd.add_aliases([
        ('base64_decode', 'b64d'),
        ('base64_encode', 'b64e'),
        ('asciihex_decode', 'ahd'),
        ('asciihex_encode', 'ahe'),
        ('url_decode', 'urld'),
        ('url_encode', 'urle'),
        ('gzip_decode', 'gzd'),
        ('gzip_encode', 'gze'),
        ('base64_decode_raw', 'b64dr'),
        ('base64_encode_raw', 'b64er'),
        ('asciihex_decode_raw', 'ahdr'),
        ('asciihex_encode_raw', 'aher'),
        ('url_decode_raw', 'urldr'),
        ('url_encode_raw', 'urler'),
        ('gzip_decode_raw', 'gzdr'),
        ('gzip_encode_raw', 'gzer'),
    ])
