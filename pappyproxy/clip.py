"""
Copyright (c) 2014, Al Sweigart
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of the {organization} nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import contextlib
import ctypes
import os
import platform
import subprocess
import sys
import time

from ctypes import c_size_t, sizeof, c_wchar_p, get_errno, c_wchar

EXCEPT_MSG = """
    Pyperclip could not find a copy/paste mechanism for your system.
    For more information, please visit https://pyperclip.readthedocs.org """
PY2 = sys.version_info[0] == 2
text_type = unicode if PY2 else str

class PyperclipException(RuntimeError):
    pass


class PyperclipWindowsException(PyperclipException):
    def __init__(self, message):
        message += " (%s)" % ctypes.WinError()
        super(PyperclipWindowsException, self).__init__(message)

def init_osx_clipboard():
    def copy_osx(text):
        p = subprocess.Popen(['pbcopy', 'w'],
                             stdin=subprocess.PIPE, close_fds=True)
        p.communicate(input=text)

    def paste_osx():
        p = subprocess.Popen(['pbpaste', 'r'],
                             stdout=subprocess.PIPE, close_fds=True)
        stdout, stderr = p.communicate()
        return stdout.decode()

    return copy_osx, paste_osx


def init_gtk_clipboard():
    import gtk

    def copy_gtk(text):
        global cb
        cb = gtk.Clipboard()
        cb.set_text(text)
        cb.store()

    def paste_gtk():
        clipboardContents = gtk.Clipboard().wait_for_text()
        # for python 2, returns None if the clipboard is blank.
        if clipboardContents is None:
            return ''
        else:
            return clipboardContents

    return copy_gtk, paste_gtk


def init_qt_clipboard():
    # $DISPLAY should exist
    from PyQt4.QtGui import QApplication

    app = QApplication([])

    def copy_qt(text):
        cb = app.clipboard()
        cb.setText(text)

    def paste_qt():
        cb = app.clipboard()
        return text_type(cb.text())

    return copy_qt, paste_qt


def init_xclip_clipboard():
    def copy_xclip(text):
        p = subprocess.Popen(['xclip', '-selection', 'c'],
                             stdin=subprocess.PIPE, close_fds=True)
        p.communicate(input=text)

    def paste_xclip():
        p = subprocess.Popen(['xclip', '-selection', 'c', '-o'],
                             stdout=subprocess.PIPE, close_fds=True)
        stdout, stderr = p.communicate()
        return stdout.decode()

    return copy_xclip, paste_xclip


def init_xsel_clipboard():
    def copy_xsel(text):
        p = subprocess.Popen(['xsel', '-b', '-i'],
                             stdin=subprocess.PIPE, close_fds=True)
        p.communicate(input=text)

    def paste_xsel():
        p = subprocess.Popen(['xsel', '-b', '-o'],
                             stdout=subprocess.PIPE, close_fds=True)
        stdout, stderr = p.communicate()
        return stdout.decode()

    return copy_xsel, paste_xsel


def init_klipper_clipboard():
    def copy_klipper(text):
        p = subprocess.Popen(
            ['qdbus', 'org.kde.klipper', '/klipper', 'setClipboardContents',
             text],
            stdin=subprocess.PIPE, close_fds=True)
        p.communicate(input=None)

    def paste_klipper():
        p = subprocess.Popen(
            ['qdbus', 'org.kde.klipper', '/klipper', 'getClipboardContents'],
            stdout=subprocess.PIPE, close_fds=True)
        stdout, stderr = p.communicate()

        # Workaround for https://bugs.kde.org/show_bug.cgi?id=342874
        # TODO: https://github.com/asweigart/pyperclip/issues/43
        clipboardContents = stdout.decode()
        # even if blank, Klipper will append a newline at the end
        assert len(clipboardContents) > 0
        # make sure that newline is there
        assert clipboardContents.endswith('\n')
        if clipboardContents.endswith('\n'):
            clipboardContents = clipboardContents[:-1]
        return clipboardContents

    return copy_klipper, paste_klipper


def init_no_clipboard():
    class ClipboardUnavailable(object):
        def __call__(self, *args, **kwargs):
            raise PyperclipException(EXCEPT_MSG)

        if PY2:
            def __nonzero__(self):
                return False
        else:
            def __bool__(self):
                return False

    return ClipboardUnavailable(), ClipboardUnavailable()

class CheckedCall(object):
    def __init__(self, f):
        super(CheckedCall, self).__setattr__("f", f)

    def __call__(self, *args):
        ret = self.f(*args)
        if not ret and get_errno():
            raise PyperclipWindowsException("Error calling " + self.f.__name__)
        return ret

    def __setattr__(self, key, value):
        setattr(self.f, key, value)


def init_windows_clipboard():
    from ctypes.wintypes import (HGLOBAL, LPVOID, DWORD, LPCSTR, INT, HWND,
                                 HINSTANCE, HMENU, BOOL, UINT, HANDLE)

    windll = ctypes.windll

    safeCreateWindowExA = CheckedCall(windll.user32.CreateWindowExA)
    safeCreateWindowExA.argtypes = [DWORD, LPCSTR, LPCSTR, DWORD, INT, INT,
                                    INT, INT, HWND, HMENU, HINSTANCE, LPVOID]
    safeCreateWindowExA.restype = HWND

    safeDestroyWindow = CheckedCall(windll.user32.DestroyWindow)
    safeDestroyWindow.argtypes = [HWND]
    safeDestroyWindow.restype = BOOL

    OpenClipboard = windll.user32.OpenClipboard
    OpenClipboard.argtypes = [HWND]
    OpenClipboard.restype = BOOL

    safeCloseClipboard = CheckedCall(windll.user32.CloseClipboard)
    safeCloseClipboard.argtypes = []
    safeCloseClipboard.restype = BOOL

    safeEmptyClipboard = CheckedCall(windll.user32.EmptyClipboard)
    safeEmptyClipboard.argtypes = []
    safeEmptyClipboard.restype = BOOL

    safeGetClipboardData = CheckedCall(windll.user32.GetClipboardData)
    safeGetClipboardData.argtypes = [UINT]
    safeGetClipboardData.restype = HANDLE

    safeSetClipboardData = CheckedCall(windll.user32.SetClipboardData)
    safeSetClipboardData.argtypes = [UINT, HANDLE]
    safeSetClipboardData.restype = HANDLE

    safeGlobalAlloc = CheckedCall(windll.kernel32.GlobalAlloc)
    safeGlobalAlloc.argtypes = [UINT, c_size_t]
    safeGlobalAlloc.restype = HGLOBAL

    safeGlobalLock = CheckedCall(windll.kernel32.GlobalLock)
    safeGlobalLock.argtypes = [HGLOBAL]
    safeGlobalLock.restype = LPVOID

    safeGlobalUnlock = CheckedCall(windll.kernel32.GlobalUnlock)
    safeGlobalUnlock.argtypes = [HGLOBAL]
    safeGlobalUnlock.restype = BOOL

    GMEM_MOVEABLE = 0x0002
    CF_UNICODETEXT = 13

    @contextlib.contextmanager
    def window():
        """
        Context that provides a valid Windows hwnd.
        """
        # we really just need the hwnd, so setting "STATIC"
        # as predefined lpClass is just fine.
        hwnd = safeCreateWindowExA(0, b"STATIC", None, 0, 0, 0, 0, 0,
                                   None, None, None, None)
        try:
            yield hwnd
        finally:
            safeDestroyWindow(hwnd)

    @contextlib.contextmanager
    def clipboard(hwnd):
        """
        Context manager that opens the clipboard and prevents
        other applications from modifying the clipboard content.
        """
        # We may not get the clipboard handle immediately because
        # some other application is accessing it (?)
        # We try for at least 500ms to get the clipboard.
        t = time.time() + 0.5
        success = False
        while time.time() < t:
            success = OpenClipboard(hwnd)
            if success:
                break
            time.sleep(0.01)
        if not success:
            raise PyperclipWindowsException("Error calling OpenClipboard")

        try:
            yield
        finally:
            safeCloseClipboard()

    def copy_windows(text):
        # This function is heavily based on
        # http://msdn.com/ms649016#_win32_Copying_Information_to_the_Clipboard
        with window() as hwnd:
            # http://msdn.com/ms649048
            # If an application calls OpenClipboard with hwnd set to NULL,
            # EmptyClipboard sets the clipboard owner to NULL;
            # this causes SetClipboardData to fail.
            # => We need a valid hwnd to copy something.
            with clipboard(hwnd):
                safeEmptyClipboard()

                if text:
                    # http://msdn.com/ms649051
                    # If the hMem parameter identifies a memory object,
                    # the object must have been allocated using the
                    # function with the GMEM_MOVEABLE flag.
                    count = len(text) + 1
                    handle = safeGlobalAlloc(GMEM_MOVEABLE,
                                             count * sizeof(c_wchar))
                    locked_handle = safeGlobalLock(handle)

                    ctypes.memmove(c_wchar_p(locked_handle), c_wchar_p(text), count * sizeof(c_wchar))

                    safeGlobalUnlock(handle)
                    safeSetClipboardData(CF_UNICODETEXT, handle)

    def paste_windows():
        with clipboard(None):
            handle = safeGetClipboardData(CF_UNICODETEXT)
            if not handle:
                # GetClipboardData may return NULL with errno == NO_ERROR
                # if the clipboard is empty.
                # (Also, it may return a handle to an empty buffer,
                # but technically that's not empty)
                return ""
            return c_wchar_p(handle).value

    return copy_windows, paste_windows

# `import PyQt4` sys.exit()s if DISPLAY is not in the environment.
# Thus, we need to detect the presence of $DISPLAY manually
# and not load PyQt4 if it is absent.
HAS_DISPLAY = os.getenv("DISPLAY", False)
CHECK_CMD = "where" if platform.system() == "Windows" else "which"


def _executable_exists(name):
    return subprocess.call([CHECK_CMD, name],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0


def determine_clipboard():
    # Determine the OS/platform and set
    # the copy() and paste() functions accordingly.
    if 'cygwin' in platform.system().lower():
        # FIXME: pyperclip currently does not support Cygwin,
        # see https://github.com/asweigart/pyperclip/issues/55
        pass
    elif os.name == 'nt' or platform.system() == 'Windows':
        return init_windows_clipboard()
    if os.name == 'mac' or platform.system() == 'Darwin':
        return init_osx_clipboard()
    if HAS_DISPLAY:
        # Determine which command/module is installed, if any.
        try:
            import gtk  # check if gtk is installed
        except ImportError:
            pass
        else:
            return init_gtk_clipboard()

        try:
            import PyQt4  # check if PyQt4 is installed
        except ImportError:
            pass
        else:
            return init_qt_clipboard()

        if _executable_exists("xclip"):
            return init_xclip_clipboard()
        if _executable_exists("xsel"):
            return init_xsel_clipboard()
        if _executable_exists("klipper") and _executable_exists("qdbus"):
            return init_klipper_clipboard()

    return init_no_clipboard()


def set_clipboard(clipboard):
    global copy, paste

    clipboard_types = {'osx': init_osx_clipboard,
                       'gtk': init_gtk_clipboard,
                       'qt': init_qt_clipboard,
                       'xclip': init_xclip_clipboard,
                       'xsel': init_xsel_clipboard,
                       'klipper': init_klipper_clipboard,
                       'windows': init_windows_clipboard,
                       'no': init_no_clipboard}

    copy, paste = clipboard_types[clipboard]()


copy, paste = determine_clipboard()
