import pytest
import mock
import pappyproxy

from pappyproxy.mangle import async_mangle_request, async_mangle_response
from pappyproxy.http import Request, Response
from testutil import no_tcp, no_database, func_deleted, mock_deferred, mock_deep_save, fake_saving

def retf(r):
    return False

@pytest.fixture
def ignore_edit(mocker):
    new_edit = mock.MagicMock()
    new_edit.return_value = mock_deferred(None)
    new_plugin = mock.MagicMock()
    new_plugin.return_value = new_edit
    mocker.patch('pappyproxy.plugin.plugin_by_name', new=new_plugin)

@pytest.fixture
def ignore_delete(mocker):
    new_os_remove = mock.MagicMock()
    mocker.patch('os.remove', new=new_os_remove)
    return new_os_remove

@pytest.fixture(autouse=True)
def no_logging(mocker):
    mocker.patch('pappyproxy.proxy.log')
        
@pytest.fixture
def req():
    r = Request()
    r.start_line = 'GET / HTTP/1.1'
    r.host = 'www.ffffff.eeeeee'
    r.body = 'AAAA'
    return r

@pytest.fixture
def req_w_rsp(req):
    r = Response()
    r.start_line = 'HTTP/1.1 200 OK'
    r.headers['Test-Header'] = 'ABC123'
    r.body = 'AAAA'
    req.response = r
    return req

@pytest.fixture
def mock_tempfile(mocker):
    new_tfile_obj = mock.MagicMock()
    tfile_instance = mock.MagicMock()
    new_tfile_obj.return_value.__enter__.return_value = tfile_instance

    tfile_instance.name = 'mockTemporaryFile'
    mocker.patch('tempfile.NamedTemporaryFile', new=new_tfile_obj)

    new_open = mock.MagicMock()
    fake_file = mock.MagicMock(spec=file)
    new_open.return_value.__enter__.return_value = fake_file
    mocker.patch('__builtin__.open', new_open)

    return (new_tfile_obj, tfile_instance, new_open, fake_file)

        
########################
## Test request mangling
    
@pytest.inlineCallbacks
def test_mangle_request_edit(req, mock_deep_save, mock_tempfile,
                             ignore_edit, ignore_delete):
    tfile_obj, tfile_instance, new_open, fake_file = mock_tempfile
    r = req
    new_contents = ('GET / HTTP/1.1\r\n'
                    'Content-Length: 4\r\n\r\n'
                    'BBBB')
    fake_file.read.return_value = new_contents
    new_req = yield async_mangle_request(r)
    assert not mock_deep_save.called
    assert tfile_obj.called
    assert tfile_instance.write.called
    assert tfile_instance.write.call_args == ((r.full_request,),)
    assert new_open.called
    assert fake_file.read.called

    assert new_req.full_request == new_contents

@pytest.inlineCallbacks
def test_mangle_request_edit_newlines(req, mock_deep_save, mock_tempfile,
                                      ignore_edit, ignore_delete):
    # Intercepting is off, request in scope
    tfile_obj, tfile_instance, new_open, fake_file = mock_tempfile
    r = req
    new_contents = ('GET / HTTP/1.1\r\n'
                    'Test-Head: FOOBIE\n'
                    'Content-Length: 4\n\r\n'
                    'BBBB')
    fake_file.read.return_value = new_contents
    new_req = yield async_mangle_request(r)

    assert new_req.full_request == ('GET / HTTP/1.1\r\n'
                                    'Test-Head: FOOBIE\r\n'
                                    'Content-Length: 4\r\n\r\n'
                                    'BBBB')
    assert new_req.headers['Test-Head'] == 'FOOBIE'

@pytest.inlineCallbacks
def test_mangle_request_drop(req, mock_deep_save, mock_tempfile,
                             ignore_edit, ignore_delete):
    # Intercepting is off, request in scope
    tfile_obj, tfile_instance, new_open, fake_file = mock_tempfile
    r = req
    new_contents = ''
    fake_file.read.return_value = new_contents
    new_req = yield async_mangle_request(r)

    assert new_req is None

@pytest.inlineCallbacks
def test_mangle_request_edit_len(req, mock_deep_save, mock_tempfile,
                                 ignore_edit, ignore_delete):
    # Intercepting is off, request in scope
    tfile_obj, tfile_instance, new_open, fake_file = mock_tempfile
    r = req
    new_contents = ('GET / HTTP/1.1\r\n'
                    'Test-Head: FOOBIE\n'
                    'Content-Length: 4\n\r\n'
                    'BBBBAAAA')
    fake_file.read.return_value = new_contents
    new_req = yield async_mangle_request(r)

    assert new_req.full_request == ('GET / HTTP/1.1\r\n'
                                    'Test-Head: FOOBIE\r\n'
                                    'Content-Length: 8\r\n\r\n'
                                    'BBBBAAAA')


#########################
## Test response mangling
    
@pytest.inlineCallbacks
def test_mangle_response_edit(req_w_rsp, mock_deep_save, mock_tempfile,
                              ignore_edit, ignore_delete):
    # Intercepting is on, edit
    tfile_obj, tfile_instance, new_open, fake_file = mock_tempfile
    r = req_w_rsp
    old_rsp = r.response.full_response
    new_contents = ('HTTP/1.1 403 NOTOKIEDOKIE\r\n'
                    'Content-Length: 4\r\n'
                    'Other-Header: foobles\r\n\r\n'
                    'BBBB')
    fake_file.read.return_value = new_contents
    mangled_rsp = yield async_mangle_response(r)
    assert not mock_deep_save.called
    assert tfile_obj.called
    assert tfile_instance.write.called
    assert tfile_instance.write.call_args == ((old_rsp,),)
    assert new_open.called
    assert fake_file.read.called

    assert mangled_rsp.full_response == new_contents

@pytest.inlineCallbacks
def test_mangle_response_newlines(req_w_rsp, mock_deep_save, mock_tempfile,
                                  ignore_edit, ignore_delete):
    # Intercepting is off, request in scope
    tfile_obj, tfile_instance, new_open, fake_file = mock_tempfile
    r = req_w_rsp
    old_rsp = r.response.full_response
    new_contents = ('HTTP/1.1 403 NOTOKIEDOKIE\n'
                    'Content-Length: 4\n'
                    'Other-Header: foobles\r\n\n'
                    'BBBB')
    fake_file.read.return_value = new_contents
    mangled_rsp = yield async_mangle_response(r)

    assert mangled_rsp.full_response == ('HTTP/1.1 403 NOTOKIEDOKIE\r\n'
                                         'Content-Length: 4\r\n'
                                         'Other-Header: foobles\r\n\r\n'
                                         'BBBB')
    assert mangled_rsp.headers['Other-Header'] == 'foobles'

@pytest.inlineCallbacks
def test_mangle_response_drop(req_w_rsp, mock_deep_save, mock_tempfile,
                              ignore_edit, ignore_delete):
    # Intercepting is off, request in scope
    tfile_obj, tfile_instance, new_open, fake_file = mock_tempfile
    r = req_w_rsp
    old_rsp = r.response.full_response
    new_contents = ''
    fake_file.read.return_value = new_contents
    mangled_rsp = yield async_mangle_response(r)

    assert mangled_rsp is None

@pytest.inlineCallbacks
def test_mangle_response_new_len(req_w_rsp, mock_deep_save, mock_tempfile,
                                 ignore_edit, ignore_delete):
    # Intercepting is off, request in scope
    tfile_obj, tfile_instance, new_open, fake_file = mock_tempfile
    r = req_w_rsp
    old_rsp = r.response.full_response
    new_contents = ('HTTP/1.1 403 NOTOKIEDOKIE\n'
                    'Content-Length: 4\n'
                    'Other-Header: foobles\r\n\n'
                    'BBBBAAAA')
    fake_file.read.return_value = new_contents
    mangled_rsp = yield async_mangle_response(r)

    assert mangled_rsp.full_response == ('HTTP/1.1 403 NOTOKIEDOKIE\r\n'
                                         'Content-Length: 8\r\n'
                                         'Other-Header: foobles\r\n\r\n'
                                         'BBBBAAAA')
