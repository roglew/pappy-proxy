#!/usr/bin/env python

import crochet
import glob
import os
import pappyproxy
import scrypt
import shutil
import twisted

from . import compress
from .util import PappyException
from base64 import b64encode, b64decode
from cryptography.fernet import Fernet, InvalidToken
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
        
        # Leave the crypto working directory
        os.chdir('../')

        # Get the password and salt, then derive the key
        self.crypto_ramp_up()
        
        self.compressor.compress_project()
         
        # Create project and crypto archive 
        archive_file = open(self.archive, 'rb') 
        archive_crypt = open(self.config.crypt_file, 'wb')
    
        # Encrypt the archive read as a bytestring
        fern = Fernet(self.key)
        crypt_token = fern.encrypt(archive_file.read())
        archive_crypt.write(crypt_token)

        # Store the salt for the next decryption
        self.create_salt_file()

        archive_file.close()
        archive_crypt.close()
    
        # Delete clear-text files
        self.delete_clear_files()
        
    
    def decrypt_project(self):
        """
        Decrypt and decompress the project files
        """

        # If project hasn't been encrypted before, setup crypt working directory
        crypt_fp = os.path.join(os.getcwd(), self.config.crypt_file)
        if not os.path.isfile(crypt_fp):
            os.mkdir(self.config.crypt_dir)

            project_files = self.config.get_project_files()
            for pf in project_files:
                shutil.copy2(pf, self.config.crypt_dir)
            os.chdir(self.config.crypt_dir)
        
        # Otherwise, decrypt and decompress the project 
        else: 
            self.crypto_ramp_up()
            fern = Fernet(self.key)

            # Decrypt the project archive
            archive_crypt = open(self.config.crypt_file, 'rb').read()
            archive_file = open(self.config.archive, 'wb')
            try:
                archive = fern.decrypt(archive_crypt)
            except InvalidToken:
                raise PappyException("Problem decrypting the file, restart pappy to try again")
            
            archive_file.write(archive)
            archive_file.close()

            self.compressor.decompress_project()

            # Force generation of new salt and crypt archive
            self.delete_crypt_files()
            
            os.chdir(self.config.crypt_dir)
             
    def crypto_ramp_up(self):
        if not self.password:
            self.get_password()
        self.set_salt()
        self.derive_key()
    
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
    
    def set_salt(self):
        if os.path.isfile(self.config.salt_file):
            self.set_salt_from_file()
        else:
            self.salt = os.urandom(16) 
    
    def set_salt_from_file(self):
        try:
            salt_file = open(self.config.salt_file, 'rb')
            self.salt = salt_file.readline().strip()
        except:
            raise PappyException("Unable to read project.salt")
    
    def create_salt_file(self):
        salt_file = open(self.config.salt_file, 'wb')

        salt_file.write(self.salt)
        salt_file.close()
    
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
                self.key = b64encode(scrypt.hash(self.password, self.salt, buflen=32))
        except TypeError, e:
            raise PappyException("Scrypt failed with type error: ", e)
        except scrypt.error, e:
            raise PappyException("Scrypt failed with internal error: ", e)
    
    def delete_clear_files(self):
        """
        Deletes all clear-text files left in the project directory.
        """
        shutil.rmtree(self.config.crypt_dir)
        os.remove(self.config.archive)
    	
    def delete_crypt_files(self):
        """
        Deletes all encrypted-text files in the project directory.
        Forces generation of new salt after opening and closing the project.
        Adds security in the case of a one-time compromise of the system.
        """
        #os.remove(self.config.salt_file)
        os.remove(self.config.crypt_file)
