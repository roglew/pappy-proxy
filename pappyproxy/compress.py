#!/usr/bin/env python

import crochet
import glob
import pappyproxy

import zipfile
import tarfile

try:
    import bz2
except ImportError:
    bz2 = None
    print "BZ2 not installed on your system"

from base64 import b64encode, b64decode
from os import getcwd, sep, path, urandom


class Compress(object):
    def __init__(self, sessconfig):
        self.config = sessconfig
        self.zip_archive = sessconfig.archive
        self.bz2_archive = sessconfig.archive

    def compress_project(self):
        if bz2:
            self.tar_project()
        else:
            self.zip_project()

    def decompress_project(self):
        if bz2:
            self.untar_project()
        else:
            self.unzip_project()

    def zip_project(self):
        """
        Zip project files

        Using append mode (mode='a') will create a zip archive
        if none exists in the project.
        """
        try:
            zf = zipfile.ZipFile(self.zip_archive, mode="a")
            zf.write(self.config.crypt_dir)
            zf.close()
        except zipfile.LargeZipFile as e:
            raise PappyException("Project zipfile too large. Error: ", e)

    def unzip_project(self):
        """
        Extract project files from decrypted zip archive.
        Initially checks the zip archive's magic number and
        attempts to extract pappy.json to validate integrity
        of the zipfile.
        """
        if not zipfile.is_zipfile(self.zip_archive):
            raise PappyException("Project archive corrupted.")

        zf = zipfile.ZipFile(self.zip_archive)

        try:
            zf.extract("config.json")
        except zipfile.BadZipfile as e:
            raise PappyException("Zip archive corrupted. Error: ", e)

        zf.extractall()

    def tar_project(self):
        archive = tarfile.open(self.bz2_archive, 'w:bz2')

        archive.add(self.config.crypt_dir)
        archive.close()

    def untar_project(self):
        if tarfile.is_tarfile(self.bz2_archive):
            # Raise exception if there is a failure
            try:
                with tarfile.open(self.bz2_archive, "r:bz2") as archive:
                    archive.extractall()
            except tarfile.ExtractError as e:
                raise PappyException("Tar archive corrupted. Error: ", e)
