The Pappy Proxy
===============
[Documentation](https://roglew.github.io/pappy-proxy/) - [Tutorial](https://roglew.github.io/pappy-proxy/tutorial.html)

Table of Contents
=================

  * [Overview](#overview)
    * [Introduction](#introduction)
    * [Contributing](#contributing)
    * [I still like Burp, but Pappy looks interesting, can I use both?](#i-still-like-burp-but-pappy-looks-interesting-can-i-use-both)
  * [How to Use It](#how-to-use-it)
    * [Installation](#installation)
    * [Quickstart](#quickstart)
    * [Lite Mode](#lite-mode)
    * [Adding The CA Cert to Your Browser](#adding-the-ca-cert-to-your-browser)
      * [Firefox](#firefox)
      * [Chrome](#chrome)
      * [Safari](#safari)
      * [Internet Explorer](#internet-explorer)
    * [Configuration](#configuration)
    * [General Console Techniques](#general-console-techniques)
      * [Run a shell command](#run-a-shell-command)
      * [Running Python Code](#running-python-code)
      * [Redirect Output To File](#redirect-output-to-file)
    * [Generating Pappy's CA Cert](#generating-pappys-ca-cert)
    * [Browsing Recorded Requests/Responses](#browsing-recorded-requestsresponses)
    * [Tags](#tags)
    * [Request IDs](#request-ids)
      * [Passing Multiple Request IDs to a Command](#passing-multiple-request-ids-to-a-command)
    * [Context](#context)
    * [Filter Strings](#filter-strings)
      * [List of fields](#list-of-fields)
      * [List of comparers](#list-of-comparers)
      * [Special form filters](#special-form-filters)
    * [Scope](#scope)
      * [Built-In Filters](#built-in-filters)
    * [Decoding Strings](#decoding-strings)
    * [Interceptor](#interceptor)
    * [Repeater](#repeater)
    * [Macros](#macros)
      * [Generating Macros From Requests](#generating-macros-from-requests)
      * [Request Objects](#request-objects)
      * [Useful Functions](#useful-functions)
    * [Intercepting Macros](#intercepting-macros)
      * [Enabling/Disabling Intercepting Macros](#enablingdisabling-intercepting-macros)
    * [Logging](#logging)
    * [Additional Commands and Features](#additional-commands-and-features)
      * [Response streaming](#response-streaming)
    * [Viewing Responses In Browser](#viewing-responses-in-browser)
    * [Plugins](#plugins)
      * [Should I Write a Plugin or a Macro?](#should-i-write-a-plugin-or-a-macro)
    * [Global Settings](#global-settings)
    * [Using an HTTP Proxy](#using-an-http-proxy)
    * [Using a SOCKS Proxy](#using-a-socks-proxy)
    * [Transparent Host Redirection](#transparent-host-redirection)
    * [FAQ](#faq)
      * [Why does my request have an id of --?!?!](#why-does-my-request-have-an-id-of---)
    * [Boring, Technical Stuff](#boring-technical-stuff)
      * [Request Cache / Memory usage](#request-cache--memory-usage)
    * [Changelog](#changelog)

Overview
========

Introduction
------------
The Pappy (**P**roxy **A**ttack **P**roxy **P**rox**Y**) Proxy is an intercepting proxy for performing web application security testing. Its features are often similar, or straight up rippoffs from [Burp Suite](https://portswigger.net/burp/). However, Burp Suite is neither open source nor a command line tool, thus making a proxy like Pappy inevitable. The project is still in its early stages, so there are bugs and only the bare minimum features, but it can already do some cool stuff.

Contributing
------------
**I am taking any and all feature requests.** If you've used Burp and had any inconvenience with it, tell me about it and I'll do everything in my power to make sure Pappy doesn't have those issues. Or even better, if you want Burp to do something that it doesn't already, let me know so that I can ~~use it to stomp them into the dust~~ improve my project.

If you're brave and want to try and contribute code, please let me know. Right now the codebase is kind of rough and I have refactored it a few times already, but I would be more than happy to find a stable part of the codebase that you can contribute to.

Another option is to try writing a plugin. It might be a bit easier than contributing code and plugins are extremely easy to integrate as a core feature. So you can also contribute by writing a plugin and letting me know about it. You can find out more by looking at [the official plugin docs](https://roglew.github.io/pappy-proxy/pappyplugins.html).

You can find ideas for features to add on [the contributing page in the docs](https://roglew.github.io/pappy-proxy/contributing.html).

I still like Burp, but Pappy looks interesting, can I use both?
---------------------------------------------------------------
Yes! If you don't want to go completely over to Pappy yet, you can configure Burp to use Pappy as an upstream proxy server. That way, traffic will go through both Burp and Pappy and you can use whichever you want to do your testing.

How to have Burp forward traffic through Pappy:

1. Open Burp
2. Go to `Options -> Connections -> Upstream Proxy Servers`
3. Click `Add`
4. Leave `Destination Host` blank, but put `127.0.0.1` in `Proxy Host` and `8000` into `Port` (assuming you're using the default listener)
5. Configure your browser to use Burp as a proxy

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
Pappy projects take up an entire directory. Any generated scripts, exported responses, plugin data, etc. will be placed in the current directory so it's good to give your project a directory of its own. To start a project, do something like:

```
$ mkdir test_project
$ cd test_project 
$ pappy
Copying default config to directory
Proxy is listening on port 8000
pappy> exit
$ ls
data.db      project_config.json
$ 
```

And that's it! The proxy will by default be running on port 8000 and bound to localhost (to keep the hackers out). You can modify the port/interface in `config.json`. You can list all your intercepted requests with `ls`, view a full request with `vfq <reqid>` or view a full response with `vfs <reqid>`. Right now, the only command to delete requests is `filter_prune` which deletes all the requests that aren't in the current context (look at the sections on the context/filter strings for more information on that).

Here's everything you need to know to get the basics done:

* This quickstart assumes you've used Burp Suite
* Make a directory for your project and `cd` into it in the terminal. Type `pappy` into the terminal and hit enter
* Commands are entered into the prompt that appears
* The proxy starts listening on port 8000 once the program starts
* Use `ls` to look at recent requests, `ls a` to look at the entire history
* You will use the number in the `id` column to perform actions on that request
* Use `vfq <id>` and `vfs <id>` to view full requests/responses
* Use `ic` to modify requests with a text editor as they go through the proxy or `ic req rsp` to modify both requests and responses
* Use `rp <id>` to send a request to the repeater. In the repeater, use `<leader>f` to send the current buffer (you may need to configre a leader key in vim). Use `:qa!` to quit the repeater.

If you want to do more, I highly suggest reading the whole readme!


Lite Mode
---------
If you don't want to dirty up a directory, you can run Pappy in "lite" mode. Pappy will use the default configuration settings and will create a temporary data file in `/tmp` to use. When you quit, the file will be deleted. If you want to run Pappy in lite mode, run Pappy with either `-l` or `--lite`.

Example:
```
$ pappy -l
Temporary datafile is /tmp/tmpw4mGv2
Proxy is listening on port 8000
pappy> quit
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
| `socks_proxy` | A dictionary with details on how to connect to an upstream SOCKS proxy to send all in-scope requests through. See the secion on upstream SOCKS proxies for more information. |
| `http_proxy` | A dictionary with details on how to connect to an upstream http proxy to send all in-scope requests through. See the section on upstream http proxies for more information. |

The following tokens will also be replaced with values:

| Token | Replaced with |
|:--|:--|
| `{DATADIR}` | The directory where Pappy's data files are stored |

See the default `config.json` for examples.

General Console Techniques
--------------------------
There are a few tricks you can use in general when using Pappy's console. Most of these are provided by the [cmd](https://docs.python.org/2/library/cmd.html) and [cmd2](https://pythonhosted.org/cmd2/index.html).

### Run a shell command

You can run a shell command with `!`:

```
pappy> ls
ID  Verb  Host         Path               S-Code            Req Len  Rsp Len  Time  Mngl
5   GET   vitaly.sexy  /netscape.gif      304 Not Modified  0        0        0.08  --
4   GET   vitaly.sexy  /esr1.jpg          304 Not Modified  0        0        0.07  --
3   GET   vitaly.sexy  /construction.gif  304 Not Modified  0        0        0.07  --
2   GET   vitaly.sexy  /vitaly2.jpg                         0        N/A      --    --
1   GET   vitaly.sexy  /                  304 Not Modified  0        0        0.07  --
pappy> !ls
cmdhistory  config.json  data.db
pappy>
```

### Running Python Code

You can use the `py` command to either run python code or to drop down to a Python shell.

```
pappy> py print ':D '*10
:D :D :D :D :D :D :D :D :D :D
pappy> py
Python 2.7.6 (default, Jun 22 2015, 17:58:13)
[GCC 4.8.2] on linux2
Type "help", "copyright", "credits" or "license" for more information.
(ProxyCmd)

        py <command>: Executes a Python command.
        py: Enters interactive Python mode.
        End with ``Ctrl-D`` (Unix) / ``Ctrl-Z`` (Windows), ``quit()``, '`exit()``.
        Non-python commands can be issued with ``cmd("your command")``.
        Run python code from external files with ``run("filename.py")``

>>> from pappyproxy import pappy
>>> pappy.session.config.config_dict
{u'data_file': u'./data.db', u'history_size': 1000, u'cert_dir': u'{DATADIR}/certs', u'proxy_listeners': [{u'interface': u'127.0.0.1', u'port': 8000}]}
>>> exit()
pappy>
```

### Redirect Output To File

You can use `>` to direct output to a file. However, a number of commands use colored output. If you just redirect these to a file, there will be additional bytes which represent the ANSI color codes. To get around this, use the `nocolor` command to remove the color from the command output.

```
pappy> ls > ls.txt
pappy> !xxd -c 32 -g 4 ls.txt
0000000: 1b5b316d 1b5b346d 49442020 56657262 2020486f 73742020 20202020 20202050  .[1m.[4mID  Verb  Host         P
0000020: 61746820 20202020 20202020 20202020 2020532d 436f6465 20202020 20202020  ath               S-Code
0000040: 20202020 52657120 4c656e20 20527370 204c656e 20205469 6d652020 20204d6e      Req Len  Rsp Len  Time    Mn
0000060: 676c2020 1b5b306d 0a352020 201b5b33 366d4745 541b5b30 6d202020 1b5b3931  gl  .[0m.5   .[36mGET.[0m   .[91
0000080: 6d766974 616c792e 73657879 1b5b306d 20201b5b 33366d1b 5b306d2f 1b5b3334  mvitaly.sexy.[0m  .[36m.[0m/.[34
00000a0: 6d6e6574 73636170 652e6769 661b5b30 6d202020 2020201b 5b33356d 33303420  mnetscape.gif.[0m      .[35m304
00000c0: 4e6f7420 4d6f6469 66696564 1b5b306d 20203020 20202020 20202030 20202020  Not Modified.[0m  0        0
00000e0: 20202020 302e3038 20202020 2d2d2020 20200a34 2020201b 5b33366d 4745541b      0.08    --    .4   .[36mGET.
0000100: 5b306d20 20201b5b 39316d76 6974616c 792e7365 78791b5b 306d2020 1b5b3336  [0m   .[91mvitaly.sexy.[0m  .[36
0000120: 6d1b5b30 6d2f1b5b 33346d65 7372312e 6a70671b 5b306d20 20202020 20202020  m.[0m/.[34mesr1.jpg.[0m
0000140: 201b5b33 356d3330 34204e6f 74204d6f 64696669 65641b5b 306d2020 30202020   .[35m304 Not Modified.[0m  0
0000160: 20202020 20302020 20202020 2020302e 30372020 20202d2d 20202020 0a332020       0        0.07    --    .3
0000180: 201b5b33 366d4745 541b5b30 6d202020 1b5b3931 6d766974 616c792e 73657879   .[36mGET.[0m   .[91mvitaly.sexy
00001a0: 1b5b306d 20201b5b 33366d1b 5b306d2f 1b5b3334 6d636f6e 73747275 6374696f  .[0m  .[36m.[0m/.[34mconstructio
00001c0: 6e2e6769 661b5b30 6d20201b 5b33356d 33303420 4e6f7420 4d6f6469 66696564  n.gif.[0m  .[35m304 Not Modified
00001e0: 1b5b306d 20203020 20202020 20202030 20202020 20202020 302e3037 20202020  .[0m  0        0        0.07
0000200: 2d2d2020 20200a32 2020201b 5b33366d 4745541b 5b306d20 20201b5b 39316d76  --    .2   .[36mGET.[0m   .[91mv
0000220: 6974616c 792e7365 78791b5b 306d2020 1b5b3336 6d1b5b30 6d2f1b5b 33346d76  italy.sexy.[0m  .[36m.[0m/.[34mv
0000240: 6974616c 79322e6a 70671b5b 306d2020 20202020 201b5b33 366d3230 30204f4b  italy2.jpg.[0m       .[36m200 OK
0000260: 1b5b306d 20202020 20202020 20202020 30202020 20202020 20323033 34303033  .[0m            0        2034003
0000280: 20203135 352e3131 20202d2d 20202020 0a312020 201b5b33 366d4745 541b5b30    155.11  --    .1   .[36mGET.[0
00002a0: 6d202020 1b5b3931 6d766974 616c792e 73657879 1b5b306d 20201b5b 33366d1b  m   .[91mvitaly.sexy.[0m  .[36m.
00002c0: 5b306d2f 1b5b3334 6d1b5b30 6d202020 20202020 20202020 20202020 2020201b  [0m/.[34m.[0m                  .
00002e0: 5b33356d 33303420 4e6f7420 4d6f6469 66696564 1b5b306d 20203020 20202020  [35m304 Not Modified.[0m  0
0000300: 20202030 20202020 20202020 302e3037 20202020 2d2d2020 20200a                0        0.07    --    .
pappy> nocolor ls > ls2.txt
pappy> !xxd -c 32 -g 4 ls2.txt
0000000: 49442020 56657262 2020486f 73742020 20202020 20202050 61746820 20202020  ID  Verb  Host         Path
0000020: 20202020 20202020 2020532d 436f6465 20202020 20202020 20202020 52657120            S-Code            Req
0000040: 4c656e20 20527370 204c656e 20205469 6d652020 20204d6e 676c2020 0a352020  Len  Rsp Len  Time    Mngl  .5
0000060: 20474554 20202076 6974616c 792e7365 78792020 2f6e6574 73636170 652e6769   GET   vitaly.sexy  /netscape.gi
0000080: 66202020 20202033 3034204e 6f74204d 6f646966 69656420 20302020 20202020  f      304 Not Modified  0
00000a0: 20203020 20202020 20202030 2e303820 2020202d 2d202020 200a3420 20204745    0        0.08    --    .4   GE
00000c0: 54202020 76697461 6c792e73 65787920 202f6573 72312e6a 70672020 20202020  T   vitaly.sexy  /esr1.jpg
00000e0: 20202020 33303420 4e6f7420 4d6f6469 66696564 20203020 20202020 20202030      304 Not Modified  0        0
0000100: 20202020 20202020 302e3037 20202020 2d2d2020 20200a33 20202047 45542020          0.07    --    .3   GET
0000120: 20766974 616c792e 73657879 20202f63 6f6e7374 72756374 696f6e2e 67696620   vitaly.sexy  /construction.gif
0000140: 20333034 204e6f74 204d6f64 69666965 64202030 20202020 20202020 30202020   304 Not Modified  0        0
0000160: 20202020 20302e30 37202020 202d2d20 2020200a 32202020 47455420 20207669       0.07    --    .2   GET   vi
0000180: 74616c79 2e736578 7920202f 76697461 6c79322e 6a706720 20202020 20203230  taly.sexy  /vitaly2.jpg       20
00001a0: 30204f4b 20202020 20202020 20202020 30202020 20202020 20323033 34303033  0 OK            0        2034003
00001c0: 20203135 352e3131 20202d2d 20202020 0a312020 20474554 20202076 6974616c    155.11  --    .1   GET   vital
00001e0: 792e7365 78792020 2f202020 20202020 20202020 20202020 20202033 3034204e  y.sexy  /                  304 N
0000200: 6f74204d 6f646966 69656420 20302020 20202020 20203020 20202020 20202030  ot Modified  0        0        0
0000220: 2e303720 2020202d 2d202020 200a0a                                        .07    --    ..
pappy>
```

If you want to write the contents of a request or response to a file, don't use `nocolor` with `vfq` or `vfs`. Use just the `vbq` or `vbs` commands.

| Command | Description |
|:--------|:------------|
| `nocolor` | Run a command and print its output without ASCII escape codes. Intended for use when redirecting output to a file. Should only be used with text and not with binary data. |


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
| `ls [a|<num>]`| list, ls |List requests that are in the current context (see Context section). Has information like the host, target path, and status code. With no arguments, it will print the 25 most recent requests in the current context. If you pass 'a' or 'all' as an argument, it will print all the requests in the current context. If you pass a number "n" as an argument, it will print the n most recent requests in the current context. |
| `sm [p]` | sm, site_map | Print a tree showing the site map. It will display all requests in the current context that did not have a 404 response. This has to go through all of the requests in the current context so it may be slow. If the `p` option is given, it will print the paths as paths rather than as a tree. | | `viq <id(s)>` | view_request_info, viq | View additional information about requests. Includes the target port, if SSL was used, applied tags, and other information. |
| `vfq <id(s)>` | view_full_request, vfq, kjq | [V]iew [F]ull Re[Q]uest, prints the full request including headers and data. |
| `vbq <id(s)>` | view_request_bytes, vbq | [V]iew [B]ytes of Re[Q]uest, prints the full request including headers and data without coloring or additional newlines. Use this if you want to write a request to a file. |
| `ppq <format> <id(s)> ` | pretty_print_request, ppq | Pretty print a request with a specific format. See the table below for a list of formats. |
| `vhq <id(s)>` | view_request_headers, vhq | [V]iew [H]eaders of a Re[Q]uest. Prints just the headers of a request. |
| `vfs <id(s)>` | view_full_response, vfs, kjs |[V]iew [F]ull Re[S]ponse, prints the full response associated with a request including headers and data. |
| `vhs <id(s)>` | view_response_headers, vhs | [V]iew [H]eaders of a Re[S]ponse. Prints just the headers of a response associated with a request. |
| `vbs <id(s)>` | view_response_bytes, vbs | [V]iew [B]ytes of Re[S]ponse, prints the full response including headers and data without coloring or additional newlines. Use this if you want to write a response to a file. |
| `pps <format> <id(s)>` | pretty_print_response, pps | Pretty print a response with a specific format. See the table below for a list of formats. |
| `pprm <id(s)>` | print_params, pprm | Print a summary of the parameters submitted with the request. It will include URL params, POST params, and/or cookies |
| `pri [ct] [key(s)]` | param_info, pri | Print a summary of the parameters and values submitted by in-context requests. You can pass in keys to limit which values will be shown. If you also provide `ct` as the first argument, it will include any keys that are passed as arguments. |
| `watch` | watch | Print requests and responses in real time as they pass through the proxy. |

Available formats for `ppq` and `pps` commands:

| Format | Description |
|:-------|:------------|
| `form` | Print POST data submitted from a form (normal post data) |
| `json` | Print as JSON |

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

In addition, you can pass in a wildcard to include all in context requests.

* `viq *` View information about all in-context requests
* `dump_response *` Dump the responses of all in-context requests (will overwrite duplicates)

Context
-------
The context is a set of filters that define which requests are considered "active". Only requests in the current context are displayed with `ls`. By default, the context includes every single request that passes through the proxy. You can limit down the current context by applying filters. Filters apply rules such as "the response code must equal 500" or "the host must contain google.com". Once you apply one or more filters, only requests/responses which pass every active filter will be a part of the current context.

| Command | Aliases | Description |
|:--------|:------------|:---|
| `f <filter string>` | filter, fl, f |Add a filter that limits which requests are included in the current context. See the Filter String section for how to create a filter string |
| `fc` | filter_clear, fc | Clears the filters and resets the context to contain all requests and responses. Ignores scope |
| `fu` | filter_up, fu | Removes the most recently applied filter |
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
| reqbody | qbody, qdata, qbd, qdt | The body (data section) of th request | String |
| rspbody | sbody, sdata, sbd, sdt | The body (data section) of th response | String |
| verb | verb, vb | The HTTP verb of the request (ie GET, POST) | String |
| param | param, pm | Either the get or post parameters | Key/Value |
| header | header, hd | An HTTP header (ie User-Agent, Basic-Authorization) in the request or response | Key/Value |
| reqheader | reqheader, qhd | An HTTP header in the request | Key/Value |
| rspheader | rspheader, shd | An HTTP header in the response | Key/Value |
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

### Special form filters
A few filters don't conform to the field, comparer, value format. You can still negate these.

| Format | Aliases | Description |
|:--|:--|:--|
| before <reqid> | before, bf, b4 | Filters out any request that is not before the given request. Filters out any request without a time. |
| after <reqid> | after, af | Filters out any request that is not before the given request. Filters out any request without a time. |
| inv <filter string> | inf | Inverts a filter string. Anything that matches the filter string will not pass the filter. |

Examples:

```
Only show requests before request 1234
  f b4 1234

Only show requests after request 1234
  f af 1234

Show requests without a csrf parameter
  f inv param ct csrf
```

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

Decoding Strings
----------------
These features try to fill a similar role to Burp's decoder. Each command will automatically copy the results to the clipboard. In addition, if no string is given, the commands will encode/decode whatever is already in the clipboard. Here is an example of how to base64 encode/decode a string.

```
pappy> b64e "Hello World!"
SGVsbG8gV29ybGQh
pappy> b64d
Hello World!
pappy>
```

And if the result contains non-printable characters, a hexdump will be produced instead

```
pappy> b64d ImALittleTeapot=
0000  22 60 0b 8a db 65 79 37 9a a6 8b                  "`...ey7...

pappy>
```

The following commands can be used to encode/decode strings:

| Command | Aliases | Description |
|:--------|:--------|:------------|
|`base64_decode`|`base64_decode`, `b64d` | Base64 decode a string |
|`base64_encode`|`base64_encode`, `b64e` | Base64 encode a string |
|`asciihex_decode`|`asciihex_decode`, `ahd` | Decode an ASCII hex string |
|`asciihex_encode`|`asciihex_encode`, `ahe` | Encode an ASCII hex string |
|`html_decode`|`html_decode`, `htmld` | Decode an html encoded string |
|`html_encode`|`html_encode`, `htmle` | Encode a string to html encode all of the characters |
|`url_decode`|`url_decode`, `urld` | Url decode a string |
|`url_encode`|`url_encode`, `urle` | Url encode a string |
|`gzip_decode`|`gzip_decode`, `gzd` | Gzip decompress a string. Probably won't work too well since there's not a great way to get binary data passed in as an argument. I'm working on this. |
|`gzip_encode`|`gzip_encode`, `gze` | Gzip compress a string. Result doesn't get copied to the clipboard. |
|`base64_decode_raw`|`base64_decode_raw`, `b64dr` | Same as `base64_decode` but will not print a hexdump if it contains non-printable characters. It is suggested you use `>` to redirect the output to a file. |
|`base64_encode_raw`|`base64_encode_raw`, `b64er` | Same as `base64_encode` but will not print a hexdump if it contains non-printable characters. It is suggested you use `>` to redirect the output to a file. |
|`asciihex_decode_raw`|`asciihex_decode_raw`, `ahdr` | Same as `asciihex_decode` but will not print a hexdump if it contains non-printable characters. It is suggested you use `>` to redirect the output to a file. |
|`asciihex_encode_raw`|`asciihex_encode_raw`, `aher` | Same as `asciihex_encode` but will not print a hexdump if it contains non-printable characters. It is suggested you use `>` to redirect the output to a file. |
|`html_decode_raw`|`html_decode_raw`, `htmldr` | Same as `html_decode` but will not print a hexdump if it contains non-printable characters. It is suggested you use `>` to redirect the output to a file. |
|`html_encode_raw`|`html_encode_raw`, `htmler` | Same as `html_encode` but will not print a hexdump if it contains non-printable characters. It is suggested you use `>` to redirect the output to a file. |
|`url_decode_raw`|`url_decode_raw`, `urldr` | Same as `url_decode` but will not print a hexdump if it contains non-printable characters. It is suggested you use `>` to redirect the output to a file. |
|`url_encode_raw`|`url_encode_raw`, `urler` | Same as `url_encode` but will not print a hexdump if it contains non-printable characters. It is suggested you use `>` to redirect the output to a file. |
|`gzip_decode_raw`|`gzip_decode_raw`, `gzdr` | Same as `gzip_decode` but will not print a hexdump if it contains non-printable characters. It is suggested you use `>` to redirect the output to a file. |
|`gzip_encode_raw`|`gzip_encode_raw`, `gzer` | Same as `gzip_encode` but will not print a hexdump if it contains non-printable characters. It is suggested you use `>` to redirect the output to a file. |
|`unixtime_decode`| `unixtime_decode`, `uxtd` | Take in a unix timestamp and print a human readable timestamp |

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
| `RepeaterSubmitBuffer` | `<leader>f` | Submit the current buffer, split the windows vertically, and show the result in the right window |

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

In this case we have a `blank`, `hackthensa`, `testgen`, and `test` macro. A macro script is any python script that defines a `run_macro(args)` function and a `MACRO_NAME` variable. To start with, we'll write a macro to iterate over a numbered image to try and find other images. We will take the following steps to do it:

1. Make a request to the image
2. Generate a macro using the `gma` command
3. Write a loop to copy the original request, modify it, then submit it with different numbers
4. Load the macro in Pappy with the `lma` command
5. Run the macro with the `rma` command

### Generating Macros From Requests

You can also generate macros that have Pappy `Request` objects created with the same information as requests you've already made. For example:

```
$ pappy
Proxy is listening on port 8000
pappy> ls
ID  Verb  Host         Path               S-Code  Req Len  Rsp Len  Time  Mngl
5   GET   vitaly.sexy  /esr1.jpg          200 OK  0        17653    --    --
4   GET   vitaly.sexy  /netscape.gif      200 OK  0        1135     --    --
3   GET   vitaly.sexy  /construction.gif  200 OK  0        28366    --    --
2   GET   vitaly.sexy  /vitaly2.jpg       200 OK  0        2034003  --    --
1   GET   vitaly.sexy  /                  200 OK  0        1201     --    --
pappy> gma sexy 1
Wrote script to macro_sexy.py
pappy> quit
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

If you enter in a value for `SHORT_NAME`, you can use it as a shortcut to run that macro. So if in a macro you set `SHORT_NAME='tm'` you can run it by running `pappy> rma tm`.

### Passing Arguments to Macros

When you run the macro, any additional command line arguments will be passed to the run_macro function in the `args` argument. For example, if you run your macro using

```
pappy> rma foo thisis an "amazing argument"
```

The `args` argument of run_macro will be `["thisis", "an", "amazing argument"]`. If no arguments are give, `args` will be an empty list.

### Macro Commands

| Command | Aliases | Description |
|:--------|:--------|:------------|
| `lma [dir]` | `load_macros`, `lma` | Load macros from a directory. If `dir` is not given, use the current directory (the project directory) |
| `rma <macro name>` | `run_macro`, `rma` | Run a macro with the given name. You can use the shortname, filename, or long name. |
| `gma <name> [id(s)]` | `generate_macro`, `gma` | Generate a macro with the given name. If request IDs are given, the macro will contain request objects that contain each request. |
| `rpy <id(s)>` | `rpy` | Print the Python object definitions for each of the given ids |

### Request Objects

The main method of interacting with the proxy is through `Request` objects. You can submit a request with `req.sumbit()` and save it to the data file with `req.save()`. The objects also have attributes which can be used to modify the request in a high-level way. You can see the [full documentation](https://roglew.github.io/pappy-proxy/pappyproxy.html#module-pappyproxy.http) for more details on using these objects.

Dict-like objects are represented with a custom class called a `RepeatableDict`. Again, look at the docs for details. For the most part, you can interact with it like a normal dictionary, but don't be surprised if it's missing some methods you would expect.

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

There are also a few functions which could be useful for creating requests in macros. It's worth pointing out that `request_by_id` is useful for passing request objects as arguments. For example, here is a macro that lets you resubmit a request with the Google Bot user agent:

```
## macro_googlebot.py

from pappyproxy.http import Request, get_request, post_request, request_by_id
from pappyproxy.context import set_tag
from pappyproxy.iter import *

MACRO_NAME = 'Submit as Google'
SHORT_NAME = ''

def run_macro(args):
    req = request_by_id(args[0])
    req.headers['User-Agent'] = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    req.submit()
    req.save()
```

| Function | Description |
|:--|:--|
| get_request(url, url_params={}) | Returns a Request object that contains a GET request to the given url with the given url params |
| post_request(url, post_params={}, url_params={}) | Returns a Request object that contains a POST request to the given url with the given url and post params |
| request_by_id(reqid) | Get a request object from its id. |

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

In addition, you can use an `init(args)` function to get arguments from the command line. If no arguments are passed, args will be an empty list. Here is an example macro that does a search and replace:

```
## int_replace.py

MACRO_NAME = 'Find and Replace'
SHORT_NAME = ''
runargs = []

def init(args):
    global runargs
    runargs = args

def mangle_request(request):
    global runargs
    if len(runargs) < 2:
        return request
    request.body = request.body.replace(runargs[0], runargs[1])
    return request

def mangle_response(request):
    global runargs
    if len(runargs) < 2:
        return request.response
    request.response.body = request.response.body.replace(runargs[0], runargs[1])
    return request.response
```

You can use this macro to do any search and replace that you want. For example, if you wanted to replace "Google" with "Skynet", you can run the macro like this:

```
pappy> lma
Loaded "<InterceptingMacro Find and Replace (replace)>"
pappy> rim replace Google Skynet
"Find and Replace" started
pappy> 
```

Now every site that you visit will be a little bit more accurate.

### Enabling/Disabling Intercepting Macros
You can use the following commands to start/stop intercepting macros

| Command | Aliases | Description |
|:--------|:--------|:------------|
| `lma [dir]` | `load_macros`, `lma` | Load macros from a directory. If `dir` is not given, use the current directory (the project directory) |
| `rim <macro name>` | `run_int_macro`, `rim` | Run an intercepting macro. Similarly to normal macros you can use the name, short name, or file name of the macro. |
| `sim <macro name> [args]` | `stop_int_macro`, `sim` | Stop an intercepting macro. If arguments are given, they will be passed to the macro's `init(args)` function if it exists. |
| `lim` | `list_int_macros`, `lsim` | List all enabled/disabled intercepting macros |
| `gima <name>` | `generate_int_macro`, `gima` | Generate an intercepting macro with the given name. |

Logging
-------
You can watch in real-time what requests are going through the proxy. Verbosisty defaults to 1 which just states when connections are made/lost and some information on what is happening. If verbosity is set to 3, it includes all the data which is sent through the proxy and processed. It will print the raw response from the server, what it decodes it to, etc. Even if you don't run this command, all the information is stored in the dubug directory (the directory is cleared every start though!)

| Command | Description |
|:--------|:------------|
| `log [verbosity]` | View the log at the given verbosity. Default verbosity is 1 which just shows connections being made/lost and some other info, verbosity 3 shows full requests/responses as they pass through and are processed by the proxy |

Additional Commands and Features
--------------------------------
This is a list of other random stuff you can do that isn't categorized under anything else. These are mostly commands that I found that I needed while doing a test and just added. They likely don't do a ton of error checking.

| Command | Aliases | Description |
|:--------|:--------|:------------|
| `dump_response <reqid> [filename]` | `dump_response` | Dumps the data from the response to the given filename (useful for images, .swf, etc). If no filename is given, it uses the name given in the path. |
| `export <req|rsp> <reqid>` | `export` | Writes either the full request or response to a file in the current directory. |
| `merge <dbfile>` | `merge` | Add all the requests from another datafile to the current datafile |

### Response streaming

If you don't have any intercepting macros running, Pappy will forward data to the browser as it gets it. However, if you're trying to mangle messages/responses, Pappy will need to download the entire message first.

Viewing Responses In Browser
----------------------------
You can view responses in your browser by visiting `http://pappy/rsp/<rspid>` (NOT pappy.com) in your browser while connected to the proxy. For example, if you want to view the response to request 123, you can visit `http://pappy/rsp/123` to view the response. Pappy will return a response with the same body as the original response and will not make a request to the server. The response will not have the same headers as the original response (aside from the Content-Type header). In addition, Pappy doesn't modify any URLs in the page which means your browser will still fetch external resources like images, JavaScript etc from external servers.

Plugins
-------
Note that this section is a very quick overview of plugins. For a full description of how to write them, please see [the official docs](https://roglew.github.io/pappy-proxy/pappyplugins.html).

It is also possible to write plugins which are reusable across projects. Plugins are simply Python scripts located in `~/.pappy/plugins`. Plugins are able to create new console commands and maintain state throughout a Pappy session. They can access the same API as macros, but the plugin system is designed to allow you to create general purpose commands as compared to macros which are meant to be project-specific scripts. Still, it may not be a bad idea to try building a macro to do something in a quick and dirty way before writing a plugin since plugins are more complicated to write.

A simple hello world plugin could be something like:

```
## hello.py
import shlex

def hello_world(line):
    if line:
        args = shlex.split(line)
        print 'Hello, %s!' % (', '.join(args))
    else:
        print "Hello, world!"

###############
## Plugin hooks

def load_cmds(cmd):
    cmd.set_cmds({
        'hello': (hello_world, None),
    })
    cmd.add_aliases([
        ('hello', 'hlo'),
        ('hello', 'ho'),
    ])
```

You can also create commands which support autocomplete:

```
import shlex

_AUTOCOMPLETE_NAMES = ['alice', 'allie', 'sarah', 'mallory', 'slagathor']

def hello_world(line):
    if line:
        args = shlex.split(line)
        print 'Hello, %s!' % (', '.join(args))
    else:
        print "Hello, world!"
        
def complete_hello_world(text, line, begidx, endidx):
    return [n for n in _AUTOCOMPLETE_NAMES if n.startswith(text)]
        
###############
## Plugin hooks

def load_cmds(cmd):
    cmd.set_cmds({
        'hello': (hello_world, complete_hello_world),
    })
    cmd.add_aliases([
        ('hello', 'hlo'),
    ])
```

Then when you run Pappy you can use the ``hello`` command:

```
$ pappy -l
Temporary datafile is /tmp/tmpBOXyJ3
Proxy is listening on port 8000
pappy> ho
Hello, world!
pappy> ho foo bar baz
Hello, foo, bar, baz!
pappy> ho foo bar "baz lihtyur"
Hello, foo, bar, baz lihtyur!
pappy>
```

### Should I Write a Plugin or a Macro?

A lot of the time, you can get away with writing a macro. However, you may consider writing a plugin if:

* You find yourself copying one macro to multiple projects
* You want to write a general tool that can be applied to any website
* You need to maintain state during the Pappy session

My guess is that if you need one quick thing for a project, you're better off writing a macro first and seeing if you end up using it in future projects. Then if you find yourself needing it a lot, write a plugin for it. You may also consider keeping a `mine.py` plugin where you can write out commands that you use regularly but may not be worth creating a dedicated plugin for.

Global Settings
---------------
There are some settings that apply to Pappy as a whole and are stored in `~/.pappy/global_config.json`. These settings are generally for tuning performance or modifying behavior on a system-wide level. No information about projects is put in here since it is world readable. You can technically add settings in here for plugins that you write, but if it's at all possible, please keep settings in the normal project config.

Settings included in `~/.pappy/global_config.json`:

| Setting | Description |
|:--------|:------------|
| cache_size | The number of requests from history that will be included in memory at any given time. Set to -1 to keep everything in memory. See the request cache section for more info. |

Using an HTTP Proxy
-------------------
Pappy allows you to use an upstream HTTP proxy. You can do this by adding an `http_proxy` value to config.json. You can use the following for anonymous access to the proxy:

```
    "http_proxy": {"host":"httpproxy.proxy.host", "port":5555}
```

To use credentials you add a `username` and `password` value to the dictionary:

```
    "http_proxy": {"host":"httpproxy.proxy.host", "port":5555, "username": "mario", "password":"ilovemushrooms"}
```

At the moment, only basic auth is supported. Anything in-scope that passes through any of the active listeners will use the proxy. Out of scope requests will not be sent through the proxy.

Using a SOCKS Proxy
-------------------
Pappy allows you to use an upstream SOCKS proxy. You can do this by adding a `socks_proxy` value to config.json. You can use the following for anonymous access to the proxy:

```
    "socks_proxy": {"host":"socks.proxy.host", "port":5555}
```

To use credentials you add a `username` and `password` value to the dictionary:

```
    "socks_proxy": {"host":"socks.proxy.host", "port":5555, "username": "mario", "password":"ilovemushrooms"}
```

Any in-scope requests that pass through any of the active listeners will use the proxy. Out of scope requests will not be sent through the proxy.

Transparent Host Redirection
----------------------------
Sometimes you get a frustrating thick client that doesn’t let you mess with proxy settings to get it to go through a proxy. However, if you can redirect where it sends its traffic to localhost, you can get Pappy to take that traffic and redirect it to go where it should.

It takes root permissions to listen on low numbered ports. As a result, we’ll need to do some root stuff to listen on ports 80 and 443 and get the data to Pappy. There are two ways to get the traffic to Pappy. The first is to set up port forwarding as root to send traffic from localhost:80 to localhost:8080 and localhost:443 to localhost:8443 (since we can listen on 8080 and 8443 without root). Or you can YOLO, run Pappy as root and just have it listen on 80 and 443.

According to Google you can use the following command to forward port 80 on localhost to 8080 on Linux:

```
iptables -t nat -A PREROUTING -i ppp0 -p tcp --dport 80 -j REDIRECT --to-ports 8080
```

Then to route 443 to 8443:

```
iptables -t nat -A PREROUTING -i ppp0 -p tcp --dport 443 -j REDIRECT --to-ports 8443
```

Of course, both of these need to be run as root.

Then on mac it’s

```
echo "
rdr pass inet proto tcp from any to any port 80 -> 127.0.0.1 port 8080
rdr pass inet proto tcp from any to any port 443 -> 127.0.0.1 port 8443
" | sudo pfctl -ef -
Then to turn it off on mac it’s
sudo pfctl -F all -f /etc/pf.conf
```

Then modify the listener settings in the project’s config.json to be:

```
"proxy_listeners": [
        {"port": 8080, "interface": "127.0.0.1", "forward_host": "www.example.faketld"},
        {"port": 8443, "interface": "127.0.0.1", "forward_host_ssl": "www.example.faketld"},
    ]
```

This configuration will cause Pappy to open a port on 8080 that will accept connections normally and a port on 8443 which will accept SSL connections. The forward_host setting tells Pappy to redirect any requests sent to the port to the given host. It will also update the request’s host header. forward_host_ssl does the same thing, but it listens for SSL connections and forces the connection to use SSL.

Or if you’re going to YOLO it do the same thing then listen on port 80/443 directly. I do not suggest you do this.

```
"proxy_listeners": [
        {"port": 80, "interface": "127.0.0.1", "forward_host": "www.example.faketld"},
        {"port": 443, "interface": "127.0.0.1", "forward_host_ssl": "www.example.faketld"},
    ]
```

Pappy will automatically use this host to make the connection and forward the request to the new server.

FAQ
---

### Why does my request have an id of `--`?!?!
You can't do anything with a request/response until it is decoded and saved to disk. In between the time when a request is decoded and when it's saved to disk, it will have an ID of `--`. So just wait a little bit and it will get an ID you can use.

Boring, Technical Stuff
-----------------------
I do some stuff to try and keep speed and memory usage to reasonable levels. Unfortunately, things might seem slow in some areas. This is where I try and explain why those exist. Honestly, you probably don't care about this, but I'd rather have it written down and have nobody read it than just leave people in the dark.

### Request Cache / Memory usage
For performance reasons, Pappy by default will not store every request in memory. The cache will store a certain number of the most recently accessed requests in memory. This means that if you go through all of history, it could be slow (for example running `ls a` or `sm`). If you have enough RAM to keep everything in memory, you can set the request cache size to -1 to just keep everything in memory. However, even if the cache size is unlimited, it still won't load a request into memory untill you access it. So if you want to load everything in memory, run `ls a`.

By default, Pappy will cache 2000 requests. This is kind of heavy, but it's assumed you're doing testing on a reasonably specced laptop. Personally, I live on the edge and use -1 until I run into memory issues.


Changelog
---------
The boring part of the readme

* 0.2.10
    * Add wildcard support for requests that can take in multiple request ids
    * Update dump_response to dump multiple requests at the same time
    * More autocompleters (macro commands, field for filters)
    * Add non-async function to get in-context request IDs. Now macros can scan over all in-context stuff and do things with them.
    * Improve sessions to be used to maintain state with macros
    * Bugfixes
* 0.2.9
    * Fix bugs/clean up some code
* 0.2.8
    * Upstream HTTP proxy support
    * Usability improvements
    * Docs docs docs
    * Bugfixes, unit tests
    * Add http://pappy functionality to view responses in the browser
* 0.2.7
    * boring unit tests
    * should make future releases more stable I guess
    * Support for upstream SOCKS servers
    * `print_params` command
    * `inv` filter
    * `param_info` command
    * Filters by request/response only headers/body
    * Transparent host redirection
    * Some easier to type aliases for common commands
* 0.2.6
    * Fix pip being dumb
    * `watch` command to watch requests/responses in real time
    * Added `pp[qs] form <id>` to print POST data
    * Bugfixes
* 0.2.5
    * Requests sent with repeater now are given `repeater` tag
    * Add ppq and pps commands
    * Look at the pretty prompt
    * Bugfixes
* 0.2.4
    * Add command history saving between sessions
    * Add html encoder/decoder
    * All the bugs were fixed so I added some more for 0.2.5
* 0.2.3
    * Decoder functions
    * Add `merge` command
    * Bugfixes
* 0.2.2
    * COLORS
    * Performance improvements
    * Bugfixes (duh)
* 0.2.1
    * Improve memory usage
    * Tweaked plugin API
* 0.2.0
    * Lots of refactoring
    * Plugins
    * Bugfixes probably
    * Change prompt to make Pappy look more professional (but it will always be pappy time in your heart, I promise)
    * Create changelog
    * Add response streaming if no intercepting macros are active
* 0.1.1
    * Start using sane versioning system
    * Did proxy things