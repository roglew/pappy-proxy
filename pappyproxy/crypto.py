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
from cryptography.fernet import Fernet
from twisted.internet import reactor, defer

class Crypto(object):
    def __init__(self, sessconfig):
        self.config = sessconfig
        self.archive = self.config.archive 
        self.compressor = compress.Compress(sessconfig)
        self.key = None
        self.password = None
        self.salt = None

    def encrypt_project(self):
        """
        Compress and encrypt the project files, deleting clear-text files afterwards
        """

        # Get the password and salt, then derive the key
        self.crypto_ramp_up()

        # Instantiate the crypto module
        fern = Fernet(self.key)
   
        # Create project archive and crypto archive 
        self.compressor.compress_project()
        archive_file = open(self.archive, 'rb') 
        archive_crypt = open(self.config.crypt_file, 'wb')
    
        # Encrypt the archive read as a bytestring
        crypt_token = fern.encrypt(archive_file)
        archive_crypt.write(crypt_token)
    
        # Delete clear-text files
        # delete_clear_files()
        
        # Leave crypto working directory
        os.chdir('../')
    
    def decrypt_project(self):
        """
        Decrypt and decompress the project files
        """

        # Get the password and salt, then derive the key
        self.crypto_ramp_up()

        # Create crypto working directory 
        crypto_path = os.path.join(os.getcwd(), self.config.crypt_dir)
        os.mkdir(crypto_path)

        if os.path.isfile(self.config.crypt_file):
            # Derive the key
            key = self.crypto_ramp_up()
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
             
    def crypto_ramp_up(self):
        if not self.password:
            self.get_password()
        self.set_salt()
        self.derive_key()
    
    def delete_clear_files(self):
        """
        Deletes all clear-text files left in the project directory.
        """
        project_files = self.config.get_project_files()
        for pf in project_files:
    	    os.remove(pf)
    	
    def delete_crypt_files(self):
        """
        Deletes all encrypted-text files in the project directory.
        Forces generation of new salt after opening and closing the project.
        Adds security in the case of a one-time compromise of the system.
        """
        os.remove(self.config.salt_file)
        os.remove(self.config.crypt_file)
    
    def create_salt_file(self):
        salt_file = open(self.config.salt_file, 'wb')

        if not self.config.salt:
            self.set_salt()
        
        salt_file.write(self.config.salt)
        salt_file.close()
    
    def set_salt_from_file(self):
        try:
            salt_file = open(self.config.salt_file, 'rb')
            self.config.salt = salt_file.readline().strip()
        except:
            raise PappyException("Unable to read project.salt")

    def set_salt(self):
        if os.path.isfile(self.config.salt_file):
            self.set_salt_from_file()
        else:
            self.config.salt = os.urandom(16) 
    
    def get_password(self):
        """
        Retrieve password from the user. Raise an exception if the 
        password is not capable of utf-8 encoding.
        """
        encoded_passwd = ""
        try:
            passwd = raw_input("Enter a password: ")
            self.password = passwd.encode("utf-8")
        except:
            raise PappyException("Invalid password, try again")
    
    def derive_key(self):
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
    
        try:
            if not self.key:
                self.key = scrypt.hash(self.password, self.salt, bufflen=32)
        except e:
            raise PappyException("Error deriving the key: ", e)
