The Pappy Proxy
===============

Introduction
------------

The Pappy (**P**\ roxy **A**\ ttack **P**\ roxy **P**\ rox\ **Y**) Proxy
is an intercepting proxy for performing web application security
testing. Its features are often similar, or straight up rippoffs from
`Burp Suite <https://portswigger.net/burp/>`__. However, Burp Suite is
neither open source nor a command line tool, thus making a proxy like
Pappy inevitable. The project is still in its early stages, so there are
bugs and only the bare minimum features, but it should be able to do
some cool stuff soon (I'm already using it for realtm work).

Contributing
------------

**I am taking any and all feature requests.** If you've used Burp and
had any inconvenience with it, tell me about it and I'll do everything
in my power to make sure Pappy doesn't have those issues. Or even
better, if you want Burp to do something that it doesn't already, let me
know so that I can [STRIKEOUT:use it to stomp them into the dust]
improve my project.

If you're brave and want to try and contribute code, please let me know.
Right now the codebase is a giant clusterfun which I have refactored a
few times already, but I would be more than happy to find a stable part
of the codebase that you can contribute to.

How to Use It
=============

Installation
------------

Pappy supports OS X and Linux (sorry Windows). Installation requires
``pip`` or some other command that can handle a ``setup.py`` with
requirements. Once the requirements are installed, you can check that it
installed correctly by running ``pappy -l`` to start the proxy.

::

    $ git clone https://github.com/roglew/pappy-proxy.git
    $ cd pappy-proxy
    $ pip install .

Quickstart
----------

Pappy projects take up an entire directory. While a full directory may
seem like a dumb idea compared to storing everything in a zip file,
future releases will do fun stuff like generate attack scripts or other
files that need to be used by other programs on a regular basis. To
start a project, do something like:

::

    $ mkdir test_project
    $ cd test_project 
    $ pappy
    Copying default config to directory
    Proxy is listening on port 8000
    itsPappyTime> exit
    $ ls
    data.db            project_config.json  project_config.pyc
    $ 

And that's it! The proxy will by default be running on port 8000 and
bound to localhost (to keep the hackers out). You can modify the
port/interface in ``config.json``. You can list all your intercepted
requests with ``ls``, view a full request with ``vfq <reqid>`` or view a
full response with ``vfs <reqid>``. No you can't delete them yet. I'm
working on it.

Lite Mode
---------

If you don't want to dirty up a directory, you can run Pappy in "lite"
mode. Pappy will use the default configuration settings and will create
a temporary datafile in ``/tmp`` to use. When you quit, the file will be
deleted. If you want to run Pappy in line mode, run Pappy with either
``-l`` or ``--lite``.

Example:

::

    $ pappy -l
    Temporary datafile is /tmp/tmpw4mGv2
    Proxy is listening on port 8000
    itsPappyTime> quit
    Deleting temporary datafile
    $ 

Adding The CA Cert to Your Browser
----------------------------------

In order for Pappy to view data sent using HTTPS, you need to add a
generated CA cert (``certificate.crt``) to your browser. Certificates
are generated using the ``gencerts`` command and are by default stored
in the same directory as ``pappy.py``. This allows Pappy to act as a CA
and MITM HTTPS connections. I believe that Firefox and Chrome ignore
keychain/system certs, so you will have to install the CA cert to the
browsers instead of (or in addition to) adding the cert to your
keychain.

Firefox
~~~~~~~

You can add the CA cert to Firefox by going to
``Preferences -> Advanced -> View Certificates -> Authorities -> Import``
and selecting the ``certificate.crt`` file in the ``certs`` directory.

Chrome
~~~~~~

You can add the CA cert to Chrome by going to
``Settings -> Show advanced settings -> HTTPS/SSL -> Manage Certificates -> Authorities -> Import``
and selecting the ``certificate.crt`` file in the ``certs`` directory.

Safari
~~~~~~

For Safari (on macs, obviously), you need to add the CA cert to your
system keychain. You can do this by double clicking on the CA cert and
following the prompts.

Internet Explorer
~~~~~~~~~~~~~~~~~

I didn't search too hard for instructions on this (since Pappy doesn't
support windows) and I don't own a Windows machine to try this, so if
you have trouble, I'm not the one to ask. According to Google you can
double-click the cert to install it to the system, or you can do
``Tools -> Content -> Certificates -> Trusted Root Certificates -> Import``.

Configuration
-------------

Configuration for each project is done in the ``config.json`` file. The
file is a JSON-formatted dictionary that contains settings for the
proxy. The following fields can be used to configure the proxy:

+----------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Key                        | Value                                                                                                                                                                                                                                                                                                                                                                                 |
+============================+=======================================================================================================================================================================================================================================================================================================================================================================================+
| ``data_file``              | The file where requests and images will be stored                                                                                                                                                                                                                                                                                                                                     |
+----------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| ``debug_dir`` (optional)   | Where connection debug info should be stored. If not present, debug info is not saved to a file.                                                                                                                                                                                                                                                                                      |
+----------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| ``cert_dir``               | Where the CA cert and the private key for the CA cert are stored                                                                                                                                                                                                                                                                                                                      |
+----------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| ``proxy_listeners``        | A list of dicts which describe which ports the proxy will listen on. Each item is a dict with "port" and "interface" values which determine which port and interface to listen on. For example, if port=8000 and the interface is 127.0.0.1, the proxy will only accept connections from localhost on port 8000. To accept connections from anywhere, set the interface to 0.0.0.0.   |
+----------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

The following tokens will also be replaced with values:

+------------------+------------------------------------------------+
| Token            | Replaced with                                  |
+==================+================================================+
| ``{PAPPYDIR}``   | The directory where Pappy's files are stored   |
+------------------+------------------------------------------------+

Generating Pappy's CA Cert
--------------------------

In order to intercept and modify requests to sites that use HTTPS, you
have to generate and install CA certs to your browser. You can do this
by running the ``gencerts`` command in Pappy. By default, certs are
stored in the same directory as Pappy's script files. However, you can
change where Pappy will look for the private key file in the config
file. In addition, you can give the ``gencerts`` command an argument to
have it put the generated certs in a different directory.

+----------------------------------------+----------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Command                                | Description                                                                                                                                                    |
+========================================+================================================================================================================================================================+
| ``gencerts [/path/to/put/certs/in]``   | Generate a CA cert that can be added to your browser to let Pappy decrypt HTTPS traffic. Also generates the private key for that cert in the same directory.   |
+----------------------------------------+----------------------------------------------------------------------------------------------------------------------------------------------------------------+

Browsing Recorded Requests/Responses
------------------------------------

The following commands can be used to view requests and responses

+--------------------+--------------------------------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Command            | Aliases                        | Description                                                                                                                                                                                                                                                                                                                                                                                                                        |
+====================+================================+====================================================================================================================================================================================================================================================================================================================================================================================================================================+
| ``ls [a|<num>``]   | list, ls                       | List requests that are in the current context (see Context section). Has information like the host, target path, and status code. With no arguments, it will print the 25 most recent requests in the current context. If you pass 'a' or 'all' as an argument, it will print all the requests in the current context. If you pass a number "n" as an argument, it will print the n most recent requests in the current context.   |
+--------------------+--------------------------------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| ``viq <id> [u]``   | view\_request\_info, viq       | View additional information about a request. Includes the target port, if SSL was used, and other information. If 'u' is given as an additional argument, it will print information on the unmangled version of the request.                                                                                                                                                                                                       |
+--------------------+--------------------------------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| ``vfq <id> [u]``   | view\_full\_request, vfq       | [V]iew [F]ull Re[Q]uest, prints the full request including headers and data. If 'u' is given as an additional argument, it will print the unmangled version of the request.                                                                                                                                                                                                                                                        |
+--------------------+--------------------------------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| ``vhq <id> [u]``   | view\_request\_headers, vhq    | [V]iew [H]eaders of a Re[Q]uest. Prints just the headers of a request. If 'u' is given as an additional argument, it will print the unmangled version of the request.                                                                                                                                                                                                                                                              |
+--------------------+--------------------------------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| ``vfs <id> [u]``   | view\_full\_response, vfs      | [V]iew [F]ull Re[S]ponse, prints the full response associated with a request including headers and data. If 'u' is given as an additional argument, it will print the unmangled version of the response.                                                                                                                                                                                                                           |
+--------------------+--------------------------------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| ``vhs <id> [u]``   | view\_response\_headers, vhs   | [V]iew [H]eaders of a Re[S]ponse. Prints just the headers of a response associated with a request. If 'u' is given as an additional argument, it will print the unmangled version of the response.                                                                                                                                                                                                                                 |
+--------------------+--------------------------------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

The table shown will have the following columns:

+-----------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Label     | Description                                                                                                                                                                                                            |
+===========+========================================================================================================================================================================================================================+
| ID        | The request ID of that request. Used to identify the request for other commands.                                                                                                                                       |
+-----------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Method    | The method(/http verb) for the request                                                                                                                                                                                 |
+-----------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Host      | The host that the request was sent to                                                                                                                                                                                  |
+-----------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Path      | The path of the request                                                                                                                                                                                                |
+-----------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| S-Code    | The status code of the response                                                                                                                                                                                        |
+-----------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Req Len   | The length of the data submitted                                                                                                                                                                                       |
+-----------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Rsp Len   | The length of the data returned in the response                                                                                                                                                                        |
+-----------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Time      | The time in seconds it took to complete the request                                                                                                                                                                    |
+-----------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Mngl      | If the request or response were mangled with the interceptor. If the request was mangled, the column will show 'q'. If the response was mangled, the column will show 's'. If both were mangled, it will show 'q/s'.   |
+-----------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

Context
-------

The context is a set of filters that define which requests are
considered "active". Only requests in the current context are displayed
with ``ls``, and eventually contexts will be how Pappy will manage
requests for group operations. By default, the context includes every
single request that passes through the proxy. You can limit down the
current context by applying filters. Filters apply rules such as "the
response code must equal 500" or "the host must contain google.com".
Once you apply one or more filters, only requests/responses which pass
every active filter will be a part of the current context.

+-------------------------+---------------------+------------------------------------------------------------------------------------------------------------------------------------------------+
| Command                 | Aliases             | Description                                                                                                                                    |
+=========================+=====================+================================================================================================================================================+
| ``f <filter string>``   | filter, fl, f       | Add a filter that limits which requests are included in the current context. See the Filter String section for how to create a filter string   |
+-------------------------+---------------------+------------------------------------------------------------------------------------------------------------------------------------------------+
| ``fc``                  | filter\_clear, fc   | Clears the filters and resets the context to contain all requests and responses. Ignores scope                                                 |
+-------------------------+---------------------+------------------------------------------------------------------------------------------------------------------------------------------------+
| ``fls``                 | filter\_list, fls   | Print the filters that make up the current context                                                                                             |
+-------------------------+---------------------+------------------------------------------------------------------------------------------------------------------------------------------------+

Filter Strings
--------------

Filter strings define a condition that a request/response pair must pass
to be part of a context. Most filter strings have the following format:

::

    <field> <comparer> <value>

Where ``<field>`` is some part of the request/response, ``<comparer>``
is some comparison to ``<value>``. Also **if you prefix a comparer with
'n' it turns it into a negation.** For example, if you wanted a filter
that only matches requests to target.org, you could use the following
filter string:

::

    host is target.org

    field = "host"
    comparer = "is"
    value = "target.org"

For fields that are a list of key/value pairs (headers, get params, post
params, and cookies) you can use the following format:

::

    <field> <comparer1> <value1>[ <comparer2> <value2>]

This is a little more complicated. If you don't give comparer2/value2,
the filter will pass any pair where the key or the value matches
comparer1 and value1. If you do give comparer2/value2, the key must
match comparer1/value1 and the value must match comparer2/value2 For
example:

::

    Filter A:
        cookie contains Session

    Filter B:
        cookie contains Session contains 456

    Filter C:
        cookie ncontains Ultra

    Cookie: SuperSession=abc123
    Matches A and C but not B

    Cookie: UltraSession=abc123456
    Matches both A and B but not C

List of fields
~~~~~~~~~~~~~~

+--------------+--------------------------------+----------------------------------------------------------------------------------+-------------+
| Field Name   | Aliases                        | Description                                                                      | Format      |
+==============+================================+==================================================================================+=============+
| all          | all                            | The entire request represented as one string                                     | String      |
+--------------+--------------------------------+----------------------------------------------------------------------------------+-------------+
| host         | host, domain, hs, dm           | The target host (ie www.target.com)                                              | String      |
+--------------+--------------------------------+----------------------------------------------------------------------------------+-------------+
| path         | path, pt                       | The path of the url (ie /path/to/secrets.php)                                    | String      |
+--------------+--------------------------------+----------------------------------------------------------------------------------+-------------+
| body         | body, data, bd, dt             | The body (data section) of either the request or the response                    | String      |
+--------------+--------------------------------+----------------------------------------------------------------------------------+-------------+
| verb         | verb, vb                       | The HTTP verb of the request (ie GET, POST)                                      | String      |
+--------------+--------------------------------+----------------------------------------------------------------------------------+-------------+
| param        | param, pm                      | Either the get or post parameters                                                | Key/Value   |
+--------------+--------------------------------+----------------------------------------------------------------------------------+-------------+
| header       | header, hd                     | An HTTP header (ie User-Agent, Basic-Authorization) in the request or response   | Key/Value   |
+--------------+--------------------------------+----------------------------------------------------------------------------------+-------------+
| rawheaders   | rawheaders, rh                 | The entire header section (as one string) of either the head or the response     | String      |
+--------------+--------------------------------+----------------------------------------------------------------------------------+-------------+
| sentcookie   | sentcookie, sck                | A cookie sent in a request                                                       | Key/Value   |
+--------------+--------------------------------+----------------------------------------------------------------------------------+-------------+
| setcookie    | setcookie, stck                | A cookie set by a response                                                       | Key/Value   |
+--------------+--------------------------------+----------------------------------------------------------------------------------+-------------+
| statuscode   | statuscode, sc, responsecode   | The response code of the response                                                | Numeric     |
+--------------+--------------------------------+----------------------------------------------------------------------------------+-------------+

List of comparers
~~~~~~~~~~~~~~~~~

+--------------+------------------+-----------------------------------------------------------------+
| Field Name   | Aliases          | Description                                                     |
+==============+==================+=================================================================+
| is           | is               | Exact string match                                              |
+--------------+------------------+-----------------------------------------------------------------+
| contains     | contains, ct     | A contain B is true if B is a substring of A                    |
+--------------+------------------+-----------------------------------------------------------------+
| containsr    | containsr, ctr   | A containr B is true if A matches regexp B (NOT IMPLEMENTED)    |
+--------------+------------------+-----------------------------------------------------------------+
| exists       | exists, ex       | A exists B if A is not an empty string (likely buggy)           |
+--------------+------------------+-----------------------------------------------------------------+
| Leq          | Leq              | A Leq B if A's length equals B (B must be a number)             |
+--------------+------------------+-----------------------------------------------------------------+
| Lgt          | Lgt              | A Lgt B if A's length is greater than B (B must be a number )   |
+--------------+------------------+-----------------------------------------------------------------+
| Llt          | Llt              | A Llt B if A's length is less than B (B must be a number)       |
+--------------+------------------+-----------------------------------------------------------------+
| eq           | eq               | A eq B if A = B (A and B must be a number)                      |
+--------------+------------------+-----------------------------------------------------------------+
| gt           | gt               | A gt B if A > B (A and B must be a number)                      |
+--------------+------------------+-----------------------------------------------------------------+
| lt           | lt               | A lt B if A < B (A and B must be a number)                      |
+--------------+------------------+-----------------------------------------------------------------+

Scope
-----

Scope is a set of rules to define whether Pappy should mess with a
request. You define the scope by setting the context to what you want
the scope to be and running ``scope_save``. The scope is saved in
data.db and is automatically restored when using the same project
directory.

Any requests which don't match all the filters in the scope will be
passed straight to the browser and will not be caught by the interceptor
or recorded in the database. This is useful to make sure you don't
accidentally do something like log in to your email through the proxy
and have your plaintext username/password stored and accidentally shown
to your coworkers.

+--------------------+--------------------+------------------------------------------------------+
| Command            | Aliases            | Description                                          |
+====================+====================+======================================================+
| ``scope_save``     | scope\_save        | Set the current context to be the scope              |
+--------------------+--------------------+------------------------------------------------------+
| ``sr``             | scope\_reset, sr   | Set the current context to the scope                 |
+--------------------+--------------------+------------------------------------------------------+
| ``scope_delete``   | scope\_delete      | Clear the scope (everything's in scope!)             |
+--------------------+--------------------+------------------------------------------------------+
| ``scope_list``     | scope\_list, sls   | List all the filters that are applied to the scope   |
+--------------------+--------------------+------------------------------------------------------+

Interceptor
-----------

This feature is like Burp's proxy with "Intercept Mode" turned on,
except it's not turned on unless you explicitly turn it on. When the
proxy gets a request while in intercept mode, it lets you edit it before
it forwards it to the server. In addition, it can stop responses from
the server and let you edit them before they get forwarded to the
browser. When you run the command, you can pass ``request`` and/or
``response`` as arguments to say whether you would like to intercept
requests and/or responses. Only in-scope requests/responses will be
intercepted (see Scope section).

The interceptor will use your EDITOR variable to decide which editor to
edit the request/response with. If no editor variable is set, it will
default to ``vi``.

To forward a request, edit it, save the file, then quit.

+---------------------------------------------------------+-----------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Command                                                 | Aliases         | Description                                                                                                                                                                                                     |
+=========================================================+=================+=================================================================================================================================================================================================================+
| ``ic <requests,responses,request,response,req,rsp>+``   | intercept, ic   | Begins interception mode. Press enter to leave interception mode and return to the command prompt. Pass in ``request`` to intercept requests, ``response`` to intercept responses, or both to intercept both.   |
+---------------------------------------------------------+-----------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

::

    Intercept both requests and responses:
    > ic requests responses
    > ic req rsp

    Intercept just requests:
    > ic requests
    > ic req

    Intercept just responses:
    > ic responses
    > ic rsp

    Be totally useless:
    > ic

Repeater
--------

This feature is like Burp's repeater (yes, really). You choose a request
and Pappy will open vim in a split window with your request on the left
and the original response on the right. You can make changes to the
request and then run ":RepeaterSubmitBuffer" to submit the modified
request. The response will be displayed on the right. This command is
bound to ``<leader>f`` by default, but you can rebind it in your vimrc
(I think, dunno if vim will complain if it's undefined). This command
will submit whatever buffer your cursor is in, so make sure it's in the
request buffer.

To drop a request, delete everything, save and quit (``ggdG:wq``).

When you're done with repeater, run ":qa!" to avoid having to save
changes to nonexistent files.

+---------------+----------------+----------------------------------------------+
| Command       | Aliases        | Description                                  |
+===============+================+==============================================+
| ``rp <id>``   | repeater, rp   | Open the specified request in the repeater   |
+---------------+----------------+----------------------------------------------+

+----------------------------+--------------+----------------------------------------------------------------------------------------------------+
| Vim Command                | Keybinding   | Action                                                                                             |
+============================+==============+====================================================================================================+
| ``RepeaterSubmitBuffer``   | f            | Submit the current buffer, split the windows vertically, and show the result in the right window   |
+----------------------------+--------------+----------------------------------------------------------------------------------------------------+

Logging
-------

You can watch in real-time what requests are going through the proxy.
Verbosisty defaults to 1 which just states when connections are
made/lost and some information on what is happening. If verbosity is set
to 3, it includes all the data which is sent through the proxy and
processed. It will print the raw response from the server, what it
decodes it to, etc. Even if you don't run this command, all the
information is stored in the dubug directory (the directory is cleared
every start though!)

+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Command               | Description                                                                                                                                                                                                                   |
+=======================+===============================================================================================================================================================================================================================+
| ``log [verbosity]``   | View the log at the given verbosity. Default verbosity is 1 which just shows connections being made/lost and some other info, verbosity 3 shows full requests/responses as they pass through and are processed by the proxy   |
+-----------------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
