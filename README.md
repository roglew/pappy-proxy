The Pappy Proxy
===============
[Documentation](https://roglew.github.io/pappy-proxy/) - [Tutorial](https://roglew.github.io/pappy-proxy/tutorial.html)

Introduction
------------
The Pappy (**P**roxy **A**ttack **P**roxy **P**rox**Y**) Proxy is an intercepting proxy for performing web application security testing. Its features are often similar, or straight up rippoffs from [Burp Suite](https://portswigger.net/burp/). However, Burp Suite is neither open source nor a command line tool, thus making a proxy like Pappy inevitable. The project is still in its early stages, so there are bugs and only the bare minimum features, but it should be able to do some cool stuff soon (I'm already using it for real work).

Contributing
------------
**I am taking any and all feature requests.** If you've used Burp and had any inconvenience with it, tell me about it and I'll do everything in my power to make sure Pappy doesn't have those issues. Or even better, if you want Burp to do something that it doesn't already, let me know so that I can ~~use it to stomp them into the dust~~ improve my project.

If you're brave and want to try and contribute code, please let me know. Right now the codebase is kind of rough and I have refactored it a few times already, but I would be more than happy to find a stable part of the codebase that you can contribute to.

How to Use It
=============

Installation
------------
Pappy supports OS X and Linux (sorry Windows). Installation requires `pip` or some other command that can handle a `setup.py` with requirements. Once the requirements are installed, you can check that it installed correctly by running `pappy -l` to start the proxy.
```
$ git clone --recursive https://github.com/roglew/pappy-proxy.git
$ cd pappy-proxy
$ pip install .
```

Quickstart
----------
Pappy projects take up an entire directory. Any generated scripts, exported responses, etc. will be placed in the current directory so it's good to give your project a directory of its own. To start a project, do something like:

```
$ mkdir test_project
$ cd test_project 
$ pappy
Copying default config to directory
Proxy is listening on port 8000
itsPappyTime> exit
$ ls
data.db      project_config.json
$ 
```

And that's it! The proxy will by default be running on port 8000 and bound to localhost (to keep the hackers out). You can modify the port/interface in `config.json`. You can list all your intercepted requests with `ls`, view a full request with `vfq <reqid>` or view a full response with `vfs <reqid>`. Right now, the only command to delete requests is `filter_prune` which deletes all the requests that aren't in the current context (look at the sections on the context/filter strings for more information on that).

Lite Mode
---------
If you don't want to dirty up a directory, you can run Pappy in "lite" mode. Pappy will use the default configuration settings and will create a temporary data file in `/tmp` to use. When you quit, the file will be deleted. If you want to run Pappy in lite mode, run Pappy with either `-l` or `--lite`.

Example:
```
$ pappy -l
Temporary datafile is /tmp/tmpw4mGv2
Proxy is listening on port 8000
itsPappyTime> quit
Deleting temporary datafile
$ 
```

Adding The CA Cert to Your Browser
----------------------------------
In order for Pappy to view data sent using HTTPS, you need to add a generated CA cert (`certificate.crt`) to your browser. Certificates are generated using the `gencerts` command and are by default stored in `~/.pappy/certs`. This allows Pappy to act as a CA and sign any HTTPS certificate it wants without the browser complaining. This allows Pappy to decrypt and modify HTTPS requests. The certificate installation instructions are different for each browser.

### Firefox
You can add the CA cert to Firefox by going to `Preferences -> Advanced -> View Certificates -> Authorities -> Import` and selecting the `certificate.crt` file in the `certs` directory.

### Chrome
You can add the CA cert to Chrome by going to `Settings -> Show advanced settings -> HTTPS/SSL -> Manage Certificates -> Authorities -> Import` and selecting the `certificate.crt` file in the `certs` directory.

### Safari
For Safari (on macs, obviously), you need to add the CA cert to your system keychain. You can do this by double clicking on the CA cert and following the prompts.

### Internet Explorer
I didn't search too hard for instructions on this (since Pappy doesn't support windows) and I don't own a Windows machine to try this, so if you have trouble, I'm not the one to ask. According to Google you can double-click the cert to install it to the system, or you can do `Tools -> Content -> Certificates -> Trusted Root Certificates -> Import`.

Configuration
-------------
Configuration for each project is done in the `config.json` file. The file is a JSON-formatted dictionary that contains settings for the proxy. The following fields can be used to configure the proxy:

| Key | Value |
|:--|:--|
| `data_file` | The file where requests and images will be stored |
| `debug_dir` (optional) | Where connection debug info should be stored. If not present, debug info is not saved to a file. |
| `cert_dir` | Where the CA cert and the private key for the CA cert are stored |
| `proxy_listeners` | A list of dicts which describe which ports the proxy will listen on. Each item is a dict with "port" and "interface" values which determine which port and interface to listen on. For example, if port=8000 and the interface is 127.0.0.1, the proxy will only accept connections from localhost on port 8000. To accept connections from anywhere, set the interface to 0.0.0.0. |

The following tokens will also be replaced with values:

| Token | Replaced with |
|:--|:--|
| `{DATADIR}` | The directory where Pappy's data files are stored |

See the default `config.json` for examples.

Generating Pappy's CA Cert
--------------------------
In order to intercept and modify requests to sites that use HTTPS, you have to generate and install CA certs to your browser. You can do this by running the `gencerts` command in Pappy. By default, certs are stored `~/.pappy/certs`. This is also the default location that Pappy will look for certificates (unless you specify otherwise in `config.json`.) In addition, you can give the `gencerts` command an argument to have it put the generated certs in a different directory.

| Command | Description |
|:--------|:------------|
| `gencerts [/path/to/put/certs/in]` | Generate a CA cert that can be added to your browser to let Pappy decrypt HTTPS traffic. Also generates the private key for that cert in the same directory. If no path is given, the certs will be placed in the default certificate location. Overwrites any existing certs. |

Browsing Recorded Requests/Responses
------------------------------------
The following commands can be used to view requests and responses

| Command | Aliases | Description |
|:--------|:--------|:------------|
| `ls [a|<num>`]| list, ls |List requests that are in the current context (see Context section). Has information like the host, target path, and status code. With no arguments, it will print the 25 most recent requests in the current context. If you pass 'a' or 'all' as an argument, it will print all the requests in the current context. If you pass a number "n" as an argument, it will print the n most recent requests in the current context. |
| `sm` | sm, site_map | Print a tree showing the site map. It will display all requests in the current context that did not have a 404 response. |
| `viq <id(s)>` | view_request_info, viq | View additional information about requests. Includes the target port, if SSL was used, applied tags, and other information. |
| `vfq <id(s)>` | view_full_request, vfq | [V]iew [F]ull Re[Q]uest, prints the full request including headers and data. |
| `vhq <id(s)>` | view_request_headers, vhq | [V]iew [H]eaders of a Re[Q]uest. Prints just the headers of a request. |
| `vfs <id(s)>` | view_full_response, vfs |[V]iew [F]ull Re[S]ponse, prints the full response associated with a request including headers and data. |
| `vhs <id(s)>` | view_response_headers, vhs | [V]iew [H]eaders of a Re[S]ponse. Prints just the headers of a response associated with a request. |

The table shown by `ls` will have the following columns:

| Label | Description |
|:------|:------------|
| ID | The request ID of that request. Used to identify the request for other commands. |
| Method | The method(/http verb) for the request |
| Host | The host that the request was sent to |
| Path | The path of the request |
| S-Code | The status code of the response |
| Req Len | The length of the data submitted |
| Rsp Len | The length of the data returned in the response |
| Time | The time in seconds it took to complete the request |
| Mngl | If the request or response were mangled with the interceptor. If the request was mangled, the column will show 'q'. If the response was mangled, the column will show 's'. If both were mangled, it will show 'q/s'. |

Tags
----
You can apply tags to a request and use filters to view specific tags. The following commands can be used to apply and remove tags to requests:

| Command | Aliases | Description |
|:--------|:--------|:------------|
| `tag <tag> [id(s)]`  | tag | Apply a tag to the given requests. If no IDs are given, the tag will be applied to all in-context requests. |
| `untag <tag> [id(s)]` | untag | Remove a tag from the given ids. If no IDs are given, the tag is removed from every in-context request. |
| `clrtag <id(s)>` | clrtag | Removes all tags from the given ids. |

Request IDs
-----------
Request IDs are how you identify a request and every command that involves specifying a request will take one or more request IDs. You can see it when you run `ls`. In addition, you can prepend an ID with prefixes to get requests or responses associated with the request (for example if you modified the request or its response with the interceptor, you can get the unmangled versions.) Here are the valid prefixes:

| Prefix | Description |
|:-------|:------------|
| `u` | If the request was mangled, prefixing the ID with `u` will result in the unmangled version of the request. The resulting request will not have an associated response because it was never submitted to the server. |
| `s` | If the response was mangled, prefixing the request ID `s` will result in the same request but its associated response will be the unmangled version. |

I know it sounds kind of unintuitive. Here are some example commands that will hopefully make things clearer. Suppose request 1 had its request mangled, and request 2 had its response mangled.

* `vfq 1` Prints the mangled version of request 1
* `vfq u1` Prints the unmangled version of request 1
* `rp u1` Open the repeater with the unmangled version of request 1
* `vfs u1` Throws an error because the unmangled version was never submitted
* `vfs s1` Throws an error because the response for request 1 was never mangled
* `vfs 2` Prints the mangled response of request 2
* `vfs s2` Prints the unmangled response of request 2
* `vfq u2` Throws an error because request 2's request was never mangled
* `vfs u2` Throws an error because request 2's request was never mangled

### Passing Multiple Request IDs to a Command

Some arguments can take multiple IDs for an argument. To pass multiple IDs to a command, separate the IDs with commas **(no spaces!)**. A few examples:

* `viq 1,2,u3` View information about requests 1, 2, and the unmangled version of 3
* `gma foo 4,5,6` Generate a macro with definitions for requests 4, 5, and 6

Context
-------
The context is a set of filters that define which requests are considered "active". Only requests in the current context are displayed with `ls`. By default, the context includes every single request that passes through the proxy. You can limit down the current context by applying filters. Filters apply rules such as "the response code must equal 500" or "the host must contain google.com". Once you apply one or more filters, only requests/responses which pass every active filter will be a part of the current context.

| Command | Aliases | Description |
|:--------|:------------|:---|
| `f <filter string>` | filter, fl, f |Add a filter that limits which requests are included in the current context. See the Filter String section for how to create a filter string |
| `fc` | filter_clear, fc | Clears the filters and resets the context to contain all requests and responses. Ignores scope |
| `fls` | filter_list, fls | Print the filters that make up the current context |
| `filter_prune` | filter_prune | Delete all the requests that aren't in the current context from the data file |

Filter Strings
--------------
Filter strings define a condition that a request/response pair must pass to be part of the context. Most filter strings have the following format:

```
<field> <comparer> <value>
```

Where `<field>` is some part of the request/response, `<comparer>` is some comparison to `<value>`. For example, if you wanted a filter that only matches requests to `target.org`, you could use the following filter string:

```
host is target.org

field = "host"
comparer = "is"
value = "target.org"
```

Also **if you prefix a comparer with 'n' it turns it into a negation.** Using the previous example, the following will match any request except for ones where the host contains `target.org`:

```
host nis target.org

field = "host"
comparer = "nis"
value = "target.org"
```

For fields that are a list of key/value pairs (headers, get params, post params, and cookies) you can use the following format:

```
<field> <comparer1> <value1>[ <comparer2> <value2>]
```

This is a little more complicated. If you don't give comparer2/value2, the filter will pass any pair where the key or the value matches comparer1 and value1. If you do give comparer2/value2, the key must match comparer1/value1 and the value must match comparer2/value2 For example:

```
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
```

### List of fields
| Field Name | Aliases | Description | Format |
|:--------|:------------|:-----|:------|
| all | all | The entire request represented as one string | String |
| host | host, domain, hs, dm | The target host (ie www.target.com) | String |
| path | path, pt | The path of the url (ie /path/to/secrets.php) | String |
| body | body, data, bd, dt | The body (data section) of either the request or the response | String |
| verb | verb, vb | The HTTP verb of the request (ie GET, POST) | String |
| param | param, pm | Either the get or post parameters | Key/Value |
| header | header, hd | An HTTP header (ie User-Agent, Basic-Authorization) in the request or response | Key/Value |
| rawheaders | rawheaders, rh | The entire header section (as one string) of either the head or the response | String |
| sentcookie | sentcookie, sck | A cookie sent in a request | Key/Value |
| setcookie | setcookie, stck | A cookie set by a response | Key/Value |
| statuscode | statuscode, sc, responsecode | The response code of the response | Numeric |
| tag | tag | Any of the tags applied to the request | String |

### List of comparers
| Field Name | Aliases | Description |
|:--------|:------------|:-----|
| is | is | Exact string match | 
| contains | contains, ct | A contain B is true if B is a substring of A |
| containsr | containsr, ctr | A containr B is true if A matches regexp B |
| exists | exists, ex | A exists B if A is not an empty string (likely buggy) |
| Leq | Leq | A Leq B if A's length equals B (B must be a number) |
| Lgt | Lgt | A Lgt B if A's length is greater than B (B must be a number ) |
| Llt | Llt | A Llt B if A's length is less than B (B must be a number) |
| eq | eq | A eq B if A = B (A and B must be a number) |
| gt | gt | A gt B if A > B (A and B must be a number) |
| lt | lt | A lt B if A < B (A and B must be a number) |

Scope
-----
Scope is a set of rules to define whether Pappy should mess with a request. You define the scope by setting the context to what you want the scope to be and running `scope_save`. The scope is saved in the data file and is automatically restored when using the same project directory.

Any requests which don't match all the filters in the scope will be passed straight to the browser and will not be caught by the interceptor or recorded in the data file. This is useful to make sure you don't accidentally do something like log in to your email through the proxy and have your plaintext username/password stored.

| Command | Aliases | Description |
|:--------|:--------|:------------|
| `scope_save` |`scope_save`| Set the current context to be the scope |
| `sr` |`scope_reset`, `sr`| Set the current context to the scope |
| `scope_delete` |`scope_delete`| Clear the scope (everything's in scope!) |
| `scope_list` |`scope_list`, `sls`| List all the filters that are applied to the scope |

### Built-In Filters
Pappy also includes some built in filters that you can apply. These are things that you may want to filter by but may be too tedius to type out. The `fbi` command also supports tab completion.

| Filter | Description |
|:--|:--|
| `not_image` | Matches anything that isn't an image. |
| `not_jscss` | Matches anything that isn't JavaScript or CSS. |

| Command | Aliases | Description |
|:--------|:--------|:------------|
| `fbi <filter>` | `builtin_filter`, `fbi` | Apply a built-in filter to the current context |

Interceptor
-----------
This feature is like Burp's proxy with "Intercept Mode" turned on, except it's not turned on unless you explicitly turn it on. When the proxy gets a request while in intercept mode, it lets you edit it before forwarding it to the server. In addition, it can stop responses from the server and let you edit them before they get forwarded to the browser. When you run the command, you can pass `req` and/or `rsp` as arguments to say whether you would like to intercept requests and/or responses. Only in-scope requests/responses will be intercepted (see Scope section).

The interceptor will use your EDITOR variable to decide which editor to edit the request/response with. If no editor variable is set, it will default to `vi`.

To forward a request, edit it, save the file, then quit.

| Command | Aliases | Description |
|:--------|:--------|:------------|
| `ic <req,rsp>+` | `intercept`, `ic` | Begins interception mode. Press enter to leave interception mode and return to the command prompt. Pass in `request` to intercept requests, `response` to intercept responses, or both to intercept both. |

```
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
```

To drop a request, delete everything, save and quit.

Repeater
--------
This feature is like Burp's repeater (yes, really). You choose a request and Pappy will open vim in a split window with your request on the left and the original response on the right. You can make changes to the request and then run ":RepeaterSubmitBuffer" to submit the modified request. The response will be displayed on the right. This command is bound to `<leader>f` by default, but you can bind it to something else too in your vimrc (I think, dunno if vim will complain if the function undefined which it will be for regular files). This command will submit whatever buffer your cursor is in, so make sure it's in the request buffer.

When you're done with repeater, run ":qa!" to avoid having to save changes to nonexistent files.

| Command | Aliases | Description |
|:--------|:--------|:------------|
| `rp <id>` | repeater, rp | Open the specified request in the repeater |

| Vim Command | Keybinding | Action |
|:--------|:-----------|:-------|
| `RepeaterSubmitBuffer` | <leader>f | Submit the current buffer, split the windows vertically, and show the result in the right window |

Macros
------
Macros are Pappy's version of Burp's intruder. You can use macros to make automated requests through the proxy and save them to the data file. A macro file is any python script file in the current directory that is in the form `macro_<name>.py`. An example project directory with macros would be:

```
$ ls -l
-rw-r--r-- 1 scaryhacker wheel     150 Nov 26 11:17 config.json
-rw------- 1 scaryhacker wheel 2639872 Nov 26 17:18 data.db
-rw-r--r-- 1 scaryhacker wheel     471 Nov 26 18:42 macro_blank.py
-rw-r--r-- 1 scaryhacker wheel     264 Nov 26 18:49 macro_hackthensa.py
-rw-r--r-- 1 scaryhacker wheel    1261 Nov 26 18:37 macro_testgen.py
-rw-r--r-- 1 scaryhacker wheel     241 Nov 26 17:18 macro_test.py
```

In this case we have a `blank`, `hackthensa`, `testgen`, and `test` macro. A macro script is any python script that defines a `run_macro(args)` function and a `MACRO_NAME` variable. For example, a simple macro would be:

```
--- macro_print.py

MACRO_NAME = 'Print Macro'

def run_macro(args):
    if args:
        print "Hello, %s!" % args[0]
    else:
        print "Hello, Pappy!"
```

You can place this macro in your project directory then load and run it from Pappy. When a macro is run, arguments are passed from the command line. Arguments are separated the same way as they are on the command line, so if you want to use spaces in your argument, you have to put quotes around it.

```
$ pappy
Proxy is listening on port 8000
itsPappyTime> lma
Loaded "<Macro Test Macro (tm/test)>"
Loaded "<Macro Macro 6494496 (testgen)>"
Loaded "<Macro Print Macro (print)>"
Loaded "<Macro Hack the NSA (htnsa/hackthensa)>"
Loaded "<Macro Macro 62449408 (blank)>"
itsPappyTime> rma print
Hello, Pappy!
itsPappyTime> rma print NSA
Hello, NSA!
itsPappyTime> rma print Idiot Slayer
Hello, Idiot!
itsPappyTime> rma print "Idiot Slayer"
Hello, Idiot Slayer!
```

You'll need to run `lma` every time you make a change to the macro in order to reload it. In addition, any code outside of the `run_macro` function will be run when it the macro gets loaded.

### Generating Macros From Requests

You can also generate macros that have Pappy `Request` objects created with the same information as requests you've already made. For example:

```
$ pappy
Proxy is listening on port 8000
itsPappyTime> ls
ID  Verb  Host         Path               S-Code  Req Len  Rsp Len  Time  Mngl
5   GET   vitaly.sexy  /esr1.jpg          200 OK  0        17653    --    --
4   GET   vitaly.sexy  /netscape.gif      200 OK  0        1135     --    --
3   GET   vitaly.sexy  /construction.gif  200 OK  0        28366    --    --
2   GET   vitaly.sexy  /vitaly2.jpg       200 OK  0        2034003  --    --
1   GET   vitaly.sexy  /                  200 OK  0        1201     --    --
itsPappyTime> gma sexy 1
Wrote script to macro_sexy.py
itsPappyTime> quit
$ cat macro_sexy.py
from pappyproxy.http import Request, get_request, post_request

MACRO_NAME = 'Macro 94664581'
SHORT_NAME = ''

###########
## Requests

req0 = Request((
'GET / HTTP/1.1\r\n'
'Host: vitaly.sexy\r\n'
'User-Agent: Mozilla/5.0 (Windows NT 6.3; WOW64; rv:36.0) Gecko/20100101 Firefox/36.0\r\n'
'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n'
'Accept-Language: en-US,en;q=0.5\r\n'
'Accept-Encoding: gzip, deflate\r\n'
'Connection: keep-alive\r\n'
'Pragma: no-cache\r\n'
'Cache-Control: no-cache\r\n'
'\r\n'
))


def run_macro(args):
    # Example:
    # req = req0.copy() # Copy req0
    # req.submit() # Submit the request to get a response
    # print req.response.raw_headers # print the response headers
    # req.save() # save the request to the data file
    # or copy req0 into a loop and use string substitution to automate requests
    pass
```

If you enter in a value for `SHORT_NAME`, you can use it as a shortcut to run that macro. So if in a macro you set `SHORT_NAME='tm'` you can run it by running `itsPappyTime> rma tm`.

| Command | Aliases | Description |
|:--------|:--------|:------------|
| `lma [dir]` | `load_macros`, `lma` | Load macros from a directory. If `dir` is not given, use the current directory (the project directory) |
| `rma <macro name>` | `run_macro`, `rma` | Run a macro with the given name. You can use the shortname, filename, or long name. |
| `gma <name> [id(s)]` | `generate_macro`, `gma` | Generate a macro with the given name. If request IDs are given, the macro will contain request objects that contain each request. |
| `rpy <id(s)>` | `rpy` | Print the Python object definitions for each of the given ids |

### Request Objects

The main method of interacting with the proxy is through `Request` objects. You can submit a request with `req.sumbit()` and save it to the data file with `req.save()`. The objects also have attributes which can be used to modify the request in a high-level way. Unfortunately, I haven't gotten around to writing full docs on the API and it's still changing every once in a while so I apologize if I pull the carpet out from underneath you.

Dict-like objects are represented with a custom class called a `RepeatableDict`. I haven't gotten around to writing docs on it yet, so just interact with it like a dict and don't be surprised if it's missing some methods you would expect a dict to have.

Here is a quick list of attributes that you can use with `Request` objects:

| Attribute | Settable? | Data Type | Description |
|:--|:--|:--|:--|
| cookies | Yes | RepeatableDict | Cookies sent in the request |
| fragment | Yes | String | The url fragment (The text after the #) |
| full_path | No | String | The path including url params and the fragment |
| full_request | No | String | The full request including headers and data |
| headers | Yes | RepeatableDict | The headers of the request |
| host | Yes | String | The host that the request is sent to |
| is_ssl | Yes | Bool | Whether the request is/was sent over SSL |
| path | Yes | String | The document path (ie www.a.com/this/is/the/path) |
| port | Yes | Integer | The port the request is/was sent to |
| post_params | Yes | RepeatableDict | Post parameters |
| raw_data | Yes | String | The data part of the request |
| raw_headers | No | String | The text of the headers section of the request |
| reqid | Yes | Integer | The ID of the request. If set when save() is called, it replaces the request with the same id in the database |
| response | Yes | Response | The associated response for the request |
| rsptime | No | Datetime Delta | The time it took to complete the request. Set when submit() is called |
| status_line | Yes | String | The status line of the request (ie 'GET / HTTP/1.1') |
| time_end | Yes | Datetime | The time when the request was completed |
| time_start | Yes | Datetime | The time when the request was started |
| unmangled | Yes | Request | If the request was mangled, the unmangled version of the request |
| url | Yes | String | The URL of the request (ie 'https://www.google.com') |
| url_params | Yes | RepeatableDict | The URL parameters of the request |
| verb | Yes | String | The verb used for the request (ie GET, POST, PATCH, HEAD, etc). Doesn't have to be a valid verb. |
| version | Yes | String | The version part of the status line (ie 'HTTP/1.1') |

Request methods:

| Function | Description |
|:--|:--|
| submit() | Submit the request through the proxy. Does not save the request to the data file |
| save() | Save the request, its unmangled version, its associated response, and the unmangled version of the response to the database |

And here is a quick list of attributes that you can use with `Response` objects:

| Attribute | Settable? | Data Type | Description |
|:--|:--|:--|:--|
| cookies | Yes | RepeatableDict | Cookies set by the response |
| headers | Yes | RepeatableDict | The headers of the response |
| response_code | Yes | Integer | The response code of the response |
| response_text | Yes | String | The text associated with the response code (ie OK, NOT FOUND)
| rspid | Yes | Integer | The response id of the response. If this is the same as another response in the database, calling save() on the associated request will replace that response in the database |
| unmangled | Yes | Response | If the response was mangled, this will refer to the unmangled version of the response. Otherwise it is None |
| version | Yes | String | The version part of the status line of the response (ie 'HTTP/1.1') |
| raw_headers | No | String | A text version of the headers of the response |
| status_line | Yes | String | The status line of the response |
| raw_data | Yes | String | The data portion of the response |
| full_response | No | String | The full text version of the response including headers and data |

Like I said, these interfaces are prone to change and will probably crash when you use them. If you get a traceback, send me an email so I can fix it.

### Useful Functions

There are also a few functions which could be useful for creating requests in macros.

| Function | Description |
|:--|:--|
| get_request(url, url_params={}) | Returns a Request object that contains a GET request to the given url with the given url params |
| post_request(url, post_params={}, url_params={}) | Returns a Request object that contains a POST request to the given url with the given url and post params |

Intercepting Macros
-------------------
Intercepting macros let you mangle requests as they pass through the proxy. Similarly to normal macros, an intercepting macro is any python script with an "int" prefix. For example, `int_name.py` would be a valid intercepting macro name. They are also loaded with the `lma` command. An intercepting macro can define two functions: `mangle_request` or `mangle_response`. Both requests only take a `Request` object as a parameter. `mangle_request` returns either a new, modified Request object to change it, or it can return the original object to not mangle it. The `mange_response` must return a `Response` (not request!) object. The request passed in to `mangle_response` will have an associated response with it. If you want to modify the response, copy `request.response`, make modifications, then return it. If you would like to pass it through untouched, just return `request.response`.

Note, that due to twisted funkyness, *you cannot save requests from intercepting macros*. Technically you **can**, but to do that you'll have to define `async_mangle_request` (or response) instead of `mangle_request` (or response) then use `Request.async_deep_save` which generates a deferred, then generate a deferred from `async_mangle_requests` (inline callbacks work too). If you've never used twisted before, please don't try. Twisted is hard. Plus the mangled request will be saved before it is submitted anyways.

Confusing? Here are some example intercepting macros:

```
## int_cloud2butt.py

import string

MACRO_NAME = 'Cloud to Butt'

def mangle_response(request):
    r = request.response.copy()
    r.raw_data = string.replace(r.raw_data, 'cloud', 'butt')
    r.raw_data = string.replace(r.raw_data, 'Cloud', 'Butt')
    return r
```

```
## int_donothing.py

import string

MACRO_NAME = 'Do Nothing'

def mangle_request(request):
    return request

def mangle_response(request):
    return request.response
```

```
## int_adminplz.py

from base64 import base64encode as b64e

MACRO_NAME = 'Admin Session'

def mangle_request(request):
    r = request.copy()
    r.headers['Authorization'] = 'Basic %s' % b64e('Admin:Password123')
    return r
```

### Enabling/Disabling Intercepting Macros
You can use the following commands to start/stop intercepting macros

| Command | Aliases | Description |
|:--------|:--------|:------------|
| `lma [dir]` | `load_macros`, `lma` | Load macros from a directory. If `dir` is not given, use the current directory (the project directory) |
| `rim <macro name>` | `run_int_macro`, `rim` | Run an intercepting macro. Similarly to normal macros you can use the name, short name, or file name of the macro. |
| `sim <macro name>` | `stop_int_macro`, `sim` | Stop an intercepting macro. |
| `lim` | `list_int_macros`, `lim` | List all enabled/disabled intercepting macros |
| `gima <name>` | `generate_int_macro`, `gima` | Generate an intercepting macro with the given name. |

Logging
-------
You can watch in real-time what requests are going through the proxy. Verbosisty defaults to 1 which just states when connections are made/lost and some information on what is happening. If verbosity is set to 3, it includes all the data which is sent through the proxy and processed. It will print the raw response from the server, what it decodes it to, etc. Even if you don't run this command, all the information is stored in the dubug directory (the directory is cleared every start though!)

| Command | Description |
|:--------|:------------|
| `log [verbosity]` | View the log at the given verbosity. Default verbosity is 1 which just shows connections being made/lost and some other info, verbosity 3 shows full requests/responses as they pass through and are processed by the proxy |

Additional Commands
-------------------
This is a list of other random stuff you can do that isn't categorized under anything else. These are mostly commands that I found that I needed while doing a test and just added. They likely don't do a ton of error checking.

| Command | Aliases | Description |
|:--------|:--------|:------------|
| `dump_response <reqid> [filename]` | `dump_response` | Dumps the data from the response to the given filename (useful for images, .swf, etc). If no filename is given, it uses the name given in the path. |
| `export <req|rsp> <reqid>` | `export` | Writes either the full request or response to a file in the current directory. |

