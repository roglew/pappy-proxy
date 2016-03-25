import os
import pytest
import random
import string
from pappyproxy.session import Session
from pappyproxy.crypto import Crypto
from pappyproxy.config import PappyConfig

@pytest.fixture
def conf():
    c = PappyConfig()
    return c

@pytest.fixture
def crypt():
    c = Crypto(conf())
    return c

@pytest.fixture
def tmpname():
    cns = string.ascii_lowercase + string.ascii_uppercase + string.digits
    tn = ''
    for i in xrange(8):
        tn += cns[random.randint(0,len(cns)-1)]
    return tn

tmpdir = '/tmp/test_crypto'+tmpname()
tmpfiles = ['cmdhistory', 'config.json', 'data.db']

def stub_files():
    enter_tmpdir()
    for sf in tmpfiles:
        with os.fdopen(os.open(sf, os.O_CREAT, 0o0600), 'r'):
            pass

def enter_tmpdir():
    if not os.path.isdir(tmpdir):
        os.mkdir(tmpdir)
    os.chdir(tmpdir)

def test_decrypt_tmpdir():
    enter_tmpdir()
    crypt().decrypt_project()
    assert os.path.isdir(os.path.join(os.getcwd(), '../crypt'))

def test_decrypt_copy_files():
    enter_tmpdir()
    stub_files()
    crypt().decrypt_project()
    for tf in tmpfiles:
        assert os.path.isfile(tf)
