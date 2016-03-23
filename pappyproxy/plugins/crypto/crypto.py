#!/usr/bin/env python

import crochet
import glob
import pappyproxy

import scrypt
import twisted

from base64 import b64encode, b64decode
from cryptography import Fernet
from os import getcwd, sep, path, remove, urandom
from pappyproxy.plugins import compress
from pappyproxy.plugins.misc import CryptoCompressUtils as ccu


def encrypt_project(passwd):
    """
    Compress and encrypt the project files, deleting clear-text files afterwards
    """
    # Derive the key
    key = crypto_ramp_up(passwd)
    # Instantiate the crypto module
    fern = Fernet(key)

    compress.compress_project()
    archive = None
    if path.is_file(ZIPFILE):
        archive = open(ccu.ZIPFILE, 'rb')
    else:
        archive = open(ccu.BZ2FILE, 'rb')
    archive_crypt = open(ccu.CRYPTFILE, 'wb')

    # Encrypt the archive read as a bytestring
    crypt_token = fern.encrypt(archive)
    archive_crypt.write(crypt_token)

    # Delete clear-text files
    delete_clear_files()

def decrypt_project(passwd):
    """
    Decompress and decrypt the project files
    """
    # Derive the key
    key = crypto_ramp_up(passwd)
    fern = Fernet(key)
    archive_crypt = open(ccu.CRYPTFILE, 'rb')
    archive = fern.decrypt(archive_crypt)
    compress.decompress_project()
    delete_crypt_files()


def crypto_ramp_up(passwd):
    salt = ""
    if path.isfile(ccu.SALTFILE):
        salt = get_salt()
    else:
        salt = create_salt()
    key = derive_key(passwd, salt)
    return key

def delete_clear_files():
    """
    Deletes all clear-text files left in the project directory.
    """
    project_files = ccu.get_project_files()
    for pf in project_files:
	os.remove(pf)
	
def delete_crypt_files():
    """
    Deletes all encrypted-text files in the project directory.
    Forces generation of new salt after opening and closing the project.
    Adds security in the case of a one-time compromise of the system.
    """
    os.remove(ccu.SALTFILE)
    os.remove(ccu.CRYPTFILE)

def create_salt():
    salt = b64encode(urandom(16))
    salt_file = open(ccu.SALTFILE, 'wb')
    salt_file.write(salt)
    salt_file.close()
    return salt

def get_salt():
    try:
        salt_file = open(ccu.SALTFILE, 'rb')
        salt = b64decode(salt_file.readline())
    except:
        raise PappyException("Unable to read pappy.salt")
    return salt

def get_password():
    """
    Retrieve password from the user. Raise an exception if the 
    password is not capable of base64 encoding.
    """
    encode_passwd = ""
    try:
        passwd = raw_input("Enter a password: ")
        encode_passwd = b64encode(passwd.encode("utf-8"))
    except:
        raise PappyException("Invalid password, try again")
    return encode_passwd

def derive_key(passwd, salt):
    """
    Derive a key sufficient for use as a cryptographic key
    used to encrypt the project (currently: cryptography.Fernet).

    cryptography.Fernet utilizes AES-CBC-128, requiring a 32-byte key.
    Parameter notes from the py-scrypt source-code:
    https://bitbucket.org/mhallin/py-scrypt/

    Compute scrypt(password, salt, N, r, p, buflen).

    The parameters r, p, and buflen must satisfy r * p < 2^30 and
    buflen <= (2^32 - 1) * 32. The parameter N must be a power of 2
    greater than 1. N, r and p must all be positive.

    Notes for Python 2:
      - `password` and `salt` must be str instances
      - The result will be a str instance

    Notes for Python 3:
      - `password` and `salt` can be both str and bytes. If they are str
        instances, they wil be encoded with utf-8.
      - The result will be a bytes instance

    Exceptions raised:
      - TypeError on invalid input
      - scrypt.error if scrypt failed
    """

    derived_key = ""
    try:
        dkey = scrypt.hash(passwd, salt, bufflen=32)
    except e:
        raise PappyException("Error deriving the key: ", e)
    return derived_key
    

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def cryptocmd(line):
    """
    Encrypt/Decrypt local project directory
    Usage: pappy -e 
    Details:
        Pappy will create a compressed archive of local project files.
        
        The archive file is encrypted using the cryptography.Fernet module,
        a user-supplied password and the scrypt key-derivation function.

        cryptography.Fernet uses AES-CBC-128 with HMAC256. This is merely
        a starting point, and any help implementing a stronger crypto-system
        is very welcome. Development is geared toward using
        AES-256-GCM as the AEAD encryption mode to eliminate the need for Fernet and HMAC256.
	SCrypt will still be used as the key derivation function until a public-key encryption
	scheme is developed.
        
        See Encryption section of README.md for more information.
    """

    if isinstance(line, str):
        args = crochet.split(line)
        ## Encryption mode (Encrypt=0, Decrypt=1)
        ## Set internally depending if plugin is called during pappy startup or shutdown
        mode = args[0]

	## Request the pasword from the user
	passwd = get_passwd()

        if mode == ccu.ENCRYPT:
            encrypt_project(passwd)
        elif mode == ccu.DECRYPT:
            decrypt_project(passwd)
        else:
            raise PappyException("Incorrect crypto mode")

