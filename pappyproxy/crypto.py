#!/usr/bin/env python

import crochet
import glob
import os
import pappyproxy
import scrypt
import shutil
import twisted

from . import compress
from base64 import b64encode, b64decode
from cryptography import Fernet
from twisted.internet import reactor, defer

class Crypto(object):
    def __init__(self, sessconfig):
        self.config = sessconfig
        self.archive = self.config.archive 
        self.compressor = compress.Compress(sessconfig)

    def encrypt_project(passwd):
        """
        Compress and encrypt the project files, deleting clear-text files afterwards
        """
        # Derive the key
        key = crypto_ramp_up(passwd)

        # Instantiate the crypto module
        fern = Fernet(key)
   
        # Create project archive and crypto archive 
        self.compressor.compress_project()
        archive_file = open(self.archive, 'rb') 
        archive_crypt = open(self.config.crypt_file, 'wb')
    
        # Encrypt the archive read as a bytestring
        crypt_token = fern.encrypt(archive_file)
        archive_crypt.write(crypt_token)
    
        # Delete clear-text files
        delete_clear_files()
        
        # Leave crypto working directory
        os.chdir('../')
    
    @defer.inlineCallbacks
    def decrypt_project(passwd):
        """
        Decrypt and decompress the project files
        """

        # Create crypto working directory 
        crypto_path = os.path.join(os.getcwd(), pappy_config.crypt_dir)
        os.mkdir(crypto_path)

        if os.path.isfile(self.config.crypt_file):
            # Derive the key
            key = crypto_ramp_up(passwd)
            fern = Fernet(key)

            # Decrypt the project archive
            archive_crypt = open(self.config.crypt_file, 'rb')
            archive = fern.decrypt(archive_crypt)

            shutil.move(archive, crypto_path)
            os.chdir(crypto_path)
            self.compressor.decompress_project()
        else:
            project_files = self.config.get_project_files()
            for pf in project_files:
                shutil.copy2(pf, crypto_path)
            os.chdir(crypto_path)
            
    
    def crypto_ramp_up(passwd):
        salt = ""
        if os.path.isfile(self.config.salt_file):
            salt = get_salt()
        else:
            salt = create_salt_file()
        key = derive_key(passwd, salt)
        return key
    
    def delete_clear_files():
        """
        Deletes all clear-text files left in the project directory.
        """
        project_files = self.config.get_project_files()
        for pf in project_files:
    	    os.remove(pf)
    	
    def delete_crypt_files():
        """
        Deletes all encrypted-text files in the project directory.
        Forces generation of new salt after opening and closing the project.
        Adds security in the case of a one-time compromise of the system.
        """
        os.remove(self.config.salt_file)
        os.remove(self.config.crypt_file)
    
    def create_salt_file():
        self.config.salt = urandom(16)
        salt_file = open(self.config.salt_file, 'wb')
        salt_file.write(self.config.salt)
        salt_file.close()
        return salt
    
    def get_salt():
        try:
            salt_file = open(self.config.salt_file, 'rb')
            salt = salt_file.readline()
        except:
            raise PappyException("Unable to read pappy.salt")
        return salt
    
    def get_password():
        """
        Retrieve password from the user. Raise an exception if the 
        password is not capable of utf-8 encoding.
        """
        encoded_passwd = ""
        try:
            passwd = raw_input("Enter a password: ")
            encode_passwd = passwd.encode("utf-8")
        except:
            raise PappyException("Invalid password, try again")
        return encoded_passwd
    
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
