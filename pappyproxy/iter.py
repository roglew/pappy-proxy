import os

from .config import PAPPY_DIR

def from_file(fname, intro=False):
    # Ignores lines until the first blank line, then returns every non-blank
    # line afterwards
    full_fname = os.path.join(PAPPY_DIR, 'lists', fname)
    with open(full_fname, 'r') as f:
        d = f.read()
    lines = d.splitlines()

    # Delete until the first blank line
    if intro:
        while lines and lines[0] != '':
            lines = lines[1:]

    # Generate non-blank lines
    for l in lines:
        if l:
            yield l
        
def fuzz_path_trav():
    """
    Fuzz common values for path traversal.
    """
    for l in from_file('path_traversal.txt', True):
        yield l

def fuzz_sqli():
    """
    Fuzz common values that could cause sql errors
    """
    for l in from_file('fuzzdb/attack/sql-injection/detect/xplatform.fuzz.txt'):
        yield l
        
def fuzz_xss():
    """
    Fuzz values for finding XSS
    """
    for l in from_file('fuzzdb/attack/xss/xss-rsnake.fuzz.txt'):
        yield l
        
def common_passwords():
    """
    List common passwords
    """
    for l in from_file('fuzzdb/wordlists-user-passwd/passwds/phpbb.txt'):
        yield l

def common_usernames():
    """
    List common usernames
    """
    for l in from_file('fuzzdb/wordlists-user-passwd/names/namelist.txt'):
        yield l
        
def fuzz_dirs():
    for l in from_file('fuzzdb/discovery/predictable-filepaths/filename-dirname-bruteforce/raft-small-directories.txt'):
        yield l
