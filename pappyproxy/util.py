import string

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
            chars += c
        else:
            chars += '.'
    return ''.join(chars)
