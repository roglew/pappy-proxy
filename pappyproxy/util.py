import re
import string
import time
import datetime

class PappyException(Exception):
    """
    The exception class for Pappy. If a plugin command raises one of these, the
    message will be printed to the console rather than displaying a traceback.
    """
    pass

def printable_data(data):
    """
    Return ``data``, but replaces unprintable characters with periods.

    :param data: The data to make printable
    :type data: String
    :rtype: String
    """
    chars = []
    for c in data:
        if c in string.printable:
            chars.append(c)
        else:
            chars.append('.')
    return ''.join(chars)

def remove_color(s):
    ansi_escape = re.compile(r'\x1b[^m]*m')
    return ansi_escape.sub('', s)

# Taken from http://stackoverflow.com/questions/4770297/python-convert-utc-datetime-string-to-local-datetime
def utc2local(utc):
    epoch = time.mktime(utc.timetuple())
    offset = datetime.datetime.fromtimestamp(epoch) - datetime.datetime.utcfromtimestamp(epoch)
    return utc + offset

# Taken from https://gist.github.com/sbz/1080258
def hexdump(src, length=16):
    FILTER = ''.join([(len(repr(chr(x))) == 3) and chr(x) or '.' for x in range(256)])
    lines = []
    for c in xrange(0, len(src), length):
        chars = src[c:c+length]
        hex = ' '.join(["%02x" % ord(x) for x in chars])
        printable = ''.join(["%s" % ((ord(x) <= 127 and FILTER[ord(x)]) or '.') for x in chars])
        lines.append("%04x  %-*s  %s\n" % (c, length*3, hex, printable))
    return ''.join(lines)
