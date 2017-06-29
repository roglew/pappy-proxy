The Pappy Proxy
===============
[Tutorial](https://roglew.github.io/pappy-proxy/tutorial.html) - [Website](http://www.pappyproxy.com) - [Blog](http://blog.pappyproxy.com)

Overview
========

Introduction
------------
The Pappy (**P**roxy **A**ttack **P**roxy **P**rox**Y**) Proxy is an intercepting proxy for performing web application security testing. Its features are often similar, or straight up rippoffs from [Burp Suite](https://portswigger.net/burp/). However, Burp Suite is neither open source nor a command line tool, thus making a proxy like Pappy inevitable.

Contributing
------------
**I am taking any and all feature requests.** If you've used Burp and had any inconvenience with it, tell me about it and I'll do everything in my power to make sure Pappy doesn't have those issues. Or even better, if you want Burp to do something that it doesn't already, let me know so that I can ~~use it to stomp them into the dust~~ improve my project.

If you're brave and want to try and contribute code, please let me know and I'll help guide you in the right direction (also consider contributing to the [Go backend used by pappy](https://github.com/roglew/puppy)).

I still like Burp, but Pappy looks interesting, can I use both?
---------------------------------------------------------------
Yes! If you don't want to go completely over to Pappy yet, you can configure Burp to use Pappy as an upstream proxy server. That way, traffic will go through both Burp and Pappy and you can use whichever you want to do your testing.

How to have Burp forward traffic through Pappy:

1. Configure Pappy to listen on port 8000 in your project's config.json
1. Open Burp
1. Go to `Options -> Connections -> Upstream Proxy Servers`
1. Click `Add`
1. Leave `Destination Host` blank, but put `127.0.0.1` in `Proxy Host` and `8000` into `Port`
1. Configure your browser to use Burp as a proxy

How to Use It
=============

Installation
------------
Pappy supports OS X and Linux, and may or may not work in Cygwin or something on Windows. Installation depends on the following commands being available:

* python3
* pip
* virtualenv
* go version 1.3 or higher

To install Pappy:

```
$ cd /path/to/pappy/directory
$ ./install.sh
```

The script will generate a "start" script which can be used to start Pappy. Symlink it somewhere to add it to your PATH.

To install Pappy for development add a -d flag:

```
$ cd /path/to/pappy/directory
$ ./install.sh -d
```

To update, just do the same thing.

To see all install options run `install -h`

Quickstart
----------
Pappy projects take up an entire directory. Any generated scripts, exported responses, etc. will be placed in the current directory so it's good to give your project a directory of its own. To start a project, do something like:

```
$ mkdir test_project
$ cd test_project 
$ pappy
Proxy is listening on port 8080
pappy> exit
$ ls
data.db      config.json
$ 
```

And that's it! The proxy will by default be running on port 8080 and bound to localhost (to keep the hackers out). You can modify the port/interface in `config.json`.

The basics:

* Make a directory for your project and `cd` into it in the terminal. Type `pappy` into the terminal and hit enter
* Commands are entered into the prompt that appears
* The proxy starts listening on port 8080 once the program starts
* Use `ls` to look at recent requests, `ls a` to look at the entire history
* You will use the number in the `id` column to perform actions on that request
* Use `vfq <id>` and `vfs <id>` to view full requests/responses
* Use `ic` to modify requests with a text editor as they go through the proxy or `ic req rsp` to modify both requests and responses
* Use `rp <id>` to send a request to the repeater. In the repeater, use `<leader>f` to send the current buffer (you may need to configre a leader key for vim). Use `:qa!` to quit the repeater.

If you want to do more, read the rest of the README.


Lite Mode
---------
If you don't want to dirty up a directory, you can run Pappy in "lite" mode. Pappy will use the default configuration settings and will create a temporary data file in `/tmp` to use. When you quit, the file will be deleted. If you want to run Pappy in lite mode, run Pappy with either `-l` or `--lite`.

Example:
```
$ pappy -l
Proxy is listening on port 8080
pappy> quit
$ 
```

Adding The CA Cert to Your Browser
----------------------------------
In order for Pappy to view data sent using HTTPS, you need to add a generated CA cert (`server.pem`) to your browser. You will be prompted to generate them on the first startup and they stored in `~/.pappy/certs`. This allows Pappy to act as a CA and sign any HTTPS certificate it wants without the browser complaining. This allows Pappy to decrypt and modify HTTPS requests. The certificate installation instructions are different for each browser.

### Firefox
You can add the CA cert to Firefox by going to `Preferences -> Advanced -> View Certificates -> Authorities -> Import` and selecting the `server.pem` file in the `certs` directory.

### Chrome
You can add the CA cert to Chrome by going to `Settings -> Show advanced settings -> HTTPS/SSL -> Manage Certificates -> Authorities -> Import` and selecting the `server.pem` file in the `certs` directory.

### Safari
For Safari (on macs, obviously), you need to add the CA cert to your system keychain. You can do this by double clicking on the CA cert and following the prompts.

### Internet Explorer
I didn't search too hard for instructions on this (since Pappy doesn't support windows) and I don't own a Windows machine to try this, so if you have trouble, I'm not the one to ask. According to Google you can double-click the cert to install it to the system, or you can do `Tools -> Content -> Certificates -> Trusted Root Certificates -> Import`.

Configuration
-------------
Configuration for each project is done in the `config.json` file. The file is a JSON-formatted dictionary that contains settings for the proxy. The following fields can be used to configure the proxy:

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

### Redirect Output To File

You can use `>` to direct output to a file.

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
pappy>
```


Generating Pappy's CA Cert
--------------------------
In order to intercept and modify requests to sites that use HTTPS, you have to generate and install CA certs to your browser. If no certs exist, you will be prompted to generate them the first time you run Pappy. You can also regenerate them manually by running the `gencerts` command in Pappy. Certs are stored `~/.pappy/certs`.

| Command | Description |
|:--------|:------------|
| `gencerts [/path/to/put/certs/in]` | Generate a CA cert that can be added to your browser to let Pappy decrypt HTTPS traffic. Also generates the private key for that cert in the same directory. If no path is given, the certs will be placed in the default certificate location. Overwrites any existing certs. |

Browsing Recorded Requests/Responses
------------------------------------
The following commands can be used to view requests and responses

| Command | Aliases | Description |
|:--------|:--------|:------------|
| `ls [a|<num>]`| list, ls |List requests that are in the current context (see Context section). Has information like the host, target path, and status code. With no arguments, it will print the 25 most recent requests in the current context. If you pass 'a' or 'all' as an argument, it will print all the requests in the current context. If you pass a number "n" as an argument, it will print the n most recent requests in the current context. |
| `sm [p]` | sm, site_map | Print a tree showing the site map. It will display all requests in the current context that did not have a 404 response. This has to go through all of the requests in the current context so it may be slow. If the `p` option is given, it will print the paths as paths rather than as a tree. |
| `viq <id(s)>` | view_request_info, viq | View additional information about requests. Includes the target port, if SSL was used, applied tags, and other information. |
| `vfq <id(s)>` | view_full_request, vfq, kjq | [V]iew [F]ull Re[Q]uest, prints the full request including headers and data. If the request is part of a websocket handshake, it will also print the messages sent over the websocket. |
| `vbq <id(s)>` | view_request_bytes, vbq | [V]iew [B]ytes of Re[Q]uest, prints the full request including headers and data without coloring or additional newlines. Use this if you want to write a request to a file. |
| `ppq <format> <id(s)> ` | pretty_print_request, ppq | Pretty print a request with a specific format. See the table below for a list of formats. |
| `vhq <id(s)>` | view_request_headers, vhq | [V]iew [H]eaders of a Re[Q]uest. Prints just the headers of a request. |
| `vfs <id(s)>` | view_full_response, vfs, kjs |[V]iew [F]ull Re[S]ponse, prints the full response associated with a request including headers and data. |
| `vhs <id(s)>` | view_response_headers, vhs | [V]iew [H]eaders of a Re[S]ponse. Prints just the headers of a response associated with a request. |
| `vbs <id(s)>` | view_response_bytes, vbs | [V]iew [B]ytes of Re[S]ponse, prints the full response including headers and data without coloring or additional newlines. Use this if you want to write a response to a file. |
| `pps <format> <id(s)>` | pretty_print_response, pps | Pretty print a response with a specific format. See the table below for a list of formats. |
| `pprm <id(s)>` | print_params, pprm | Print a summary of the parameters submitted with the request. It will include URL params, POST params, and/or cookies |
| `pri <reqid(s)> [ct] [key(s)]` | param_info, pri | Print a summary of the parameters and values submitted by the given request(s). You can pass in keys to limit which values will be shown. If you also provide `ct` as the first argument, it will include any keys that are passed as arguments. |
| `urls <id(s)>` | urls | Search the full request and response of the given IDs for urls and prints them. Especially useful with a wildcard (`*`) to find URLs from all history. |
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

You are also able to save and load contexts. When saving a context you pass the command a name. The context can then be loaded with that name. Whenever you load a context, the current context is saved with the name `_` to make it easier to quickly load a context, view requests, then return to the original context.

| Command | Aliases | Description |
|:--------|:------------|:---|
| `sc <name>` | `sc`, `save_context` | Save the current filters with the provided name. |
| `lc <name>` | `lc`, `load_context` | Load a saved context by its name. |
| `dc <name>` | `dc`, `delete_context` | Delete a saved context by its name. |
| `cls` | `cls`, `list_contexts` | Show a list of saved contexts and the filters for each of them. |

Here is an example session demonstrating saving/loading contexts:

```
pappy> ls
ID  Verb  Host                 Path                                      S-Code         Req Len  Rsp Len  Time  Mngl
16  GET   cdn.sstatic.net      /img/developer-story/announcement_ban...  200 OK         0        10515    0.06  --
15  GET   cdn.sstatic.net      /Sites/stackoverflow/img/sprites.svg?...  200 OK         0        8131     0.05  --
14  GET   i.stack.imgur.com    /eoNf5.png                                403 Forbidden  0        173      0.07  --
13  GET   cdn.sstatic.net      /img/developer-story/announcement_ban...  200 OK         0        12919    0.07  --
12  GET   cdn.sstatic.net      /img/favicons-sprite16.png?v=4b071e01...  200 OK         0        66460    0.09  --
11  GET   i.stack.imgur.com    /xqoqk.png                                403 Forbidden  0        173      0.07  --
10  GET   i.stack.imgur.com    /6HFc3.png                                403 Forbidden  0        173      0.06  --
9   GET   i.stack.imgur.com    /tKsDb.png                                403 Forbidden  0        173      0.06  --
8   GET   i.stack.imgur.com    /5d55j.png                                403 Forbidden  0        173      0.08  --
7   GET   cdn.sstatic.net      /Js/full-anon.en.js?v=a65ef7e053bb        200 OK         0        116828   0.27  --
6   GET   cdn.sstatic.net      /img/share-sprite-new.svg?v=78be252218f3  200 OK         0        34771    0.93  --
5   GET   cdn.sstatic.net      /clc/clc.min.js?v=6f49b407ccbc            200 OK         0        6969     0.92  --
4   GET   cdn.sstatic.net      /Sites/stackoverflow/all.css?v=40629f...  200 OK         0        476855   0.07  --
3   GET   cdn.sstatic.net      /Js/stub.en.js?v=5cc84a62e045             200 OK         0        38661    0.08  --
2   GET   ajax.googleapis.com  /ajax/libs/jquery/1.12.4/jquery.min.js    200 OK         0        97163    0.09  --
1   GET   stackoverflow.com    /                                         200 OK         0        244280   0.43  --
pappy> f inv path ctr "(\.js$|\.css$)"
pappy> f inv path ctr "(\.png$|\.jpg$|\.gif$)"
pappy> sc clean
Filters saved to clean:
  inv path ctr "(\.js$|\.css$)"
  inv path ctr "(\.png$|\.jpg$|\.gif$)"
pappy> cls
Saved contexts:
clean
  inv path ctr "(\.js$|\.css$)"
  inv path ctr "(\.png$|\.jpg$|\.gif$)"

pappy> sr
pappy> fls
pappy> f host ct sstatic
pappy> ls
ID  Verb  Host             Path                                      S-Code  Req Len  Rsp Len  Time  Mngl
16  GET   cdn.sstatic.net  /img/developer-story/announcement_ban...  200 OK  0        10515    0.06  --
15  GET   cdn.sstatic.net  /Sites/stackoverflow/img/sprites.svg?...  200 OK  0        8131     0.05  --
13  GET   cdn.sstatic.net  /img/developer-story/announcement_ban...  200 OK  0        12919    0.07  --
12  GET   cdn.sstatic.net  /img/favicons-sprite16.png?v=4b071e01...  200 OK  0        66460    0.09  --
7   GET   cdn.sstatic.net  /Js/full-anon.en.js?v=a65ef7e053bb        200 OK  0        116828   0.27  --
6   GET   cdn.sstatic.net  /img/share-sprite-new.svg?v=78be252218f3  200 OK  0        34771    0.93  --
5   GET   cdn.sstatic.net  /clc/clc.min.js?v=6f49b407ccbc            200 OK  0        6969     0.92  --
4   GET   cdn.sstatic.net  /Sites/stackoverflow/all.css?v=40629f...  200 OK  0        476855   0.07  --
3   GET   cdn.sstatic.net  /Js/stub.en.js?v=5cc84a62e045             200 OK  0        38661    0.08  --
pappy> lc clean
Set the context to:
  inv path ctr "(\.js$|\.css$)"
  inv path ctr "(\.png$|\.jpg$|\.gif$)"
pappy> ls
ID  Verb  Host               Path                                      S-Code  Req Len  Rsp Len  Time  Mngl
16  GET   cdn.sstatic.net    /img/developer-story/announcement_ban...  200 OK  0        10515    0.06  --
15  GET   cdn.sstatic.net    /Sites/stackoverflow/img/sprites.svg?...  200 OK  0        8131     0.05  --
13  GET   cdn.sstatic.net    /img/developer-story/announcement_ban...  200 OK  0        12919    0.07  --
6   GET   cdn.sstatic.net    /img/share-sprite-new.svg?v=78be252218f3  200 OK  0        34771    0.93  --
1   GET   stackoverflow.com  /                                         200 OK  0        244280   0.43  --
pappy> cls
Saved contexts:
_
  host ct sstatic

clean
  inv path ctr "(\.js$|\.css$)"
  inv path ctr "(\.png$|\.jpg$|\.gif$)"

pappy> lc _
Set the context to:
  host ct sstatic
pappy> fls
host ct sstatic
pappy> dc clean
pappy> cls
Saved contexts:
_
  inv path ctr "(\.js$|\.css$)"
  inv path ctr "(\.png$|\.jpg$|\.gif$)"
```

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
    inv cookie contains Ultra

Cookie: SuperSession=abc123
Matches A and C but not B

Cookie: UltraSession=abc123456
Matches both A and B but not C
```

### List of fields
| Field Name | Aliases | Description | Format |
|:--------|:------------|:-----|:------|
| all | all | Anywhere in the request, response, or a websocket message | String |
| reqbody | reqbody, reqbd, qbd, qdata, qdt | The body of the request | String |
| rspbody | rspbody, rspbd, sbd, sdata, sdt | The body of the response | String |
| body | body, bd, data, dt | The body in either the request or the response | String |
| wsmessage | wsmessage, wsm | In a websocket message | String |
| method | method, verb, vb | The request method (GET, POST, etc) | String |
| host | host, domain, hs, dm | The host that the request was sent to | String |
| path | path, pt | The path of the request | String |
| url | url | The full URL of the request | String |
| statuscode | statuscode, sc | The status code of the response (200, 404, etc) | String |
| tag | tag | Any of the tags of the request | String |
| after | after, af | After the request with the given ID | String |
| before | before, b4 | Before the request with the given ID | String |
| reqheader | reqheader, reqhd, qhd | A header in the request | Key/Value |
| rspheader | rspheader, rsphd, shd | A header in the response | Key/Value |
| header | header, hd | A header in the request or the response | Key/Value |
| param | param, pm | Either a URL or a POST parameter | Key/Value |
| urlparam | urlparam, uparam | A URL parameter of the request | Key/Value |
| postparam | postparam, pparam | A post parameter of the request | Key/Value |
| rspcookie | rspcookie, rspck, sck | A cookie set by the response | Key/Value |
| reqcookie | reqcookie, reqck, qck | A cookie submitted by the request | Key/Value |
| cookie | cookie, ck | A cookie sent by the request or a cookie set by the response | Key/Value |

### List of comparers
| Field Name | Aliases | Description |
|:--------|:------------|:-----|
| is | is | Exact string match | 
| contains | contains, ct | A contain B is true if B is a substring of A |
| containsr | containsr, ctr | A containr B is true if A matches regexp B |
| leneq | leneq | A Leq B if A's length equals B (B must be a number) |
| lengt | lengt | A Lgt B if A's length is greater than B (B must be a number ) |
| lenlt | lenlt | A Llt B if A's length is less than B (B must be a number) |

### Special form filters
A few filters don't conform to the field, comparer, value format. You can still negate these.

| Format | Aliases | Description |
|:--|:--|:--|
| invert <filter string> | invert, inv | Inverts a filter string. Anything that matches the filter string will not pass the filter. |

Examples:

```
Show state-changing requests
  f inv method is GET

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
| `ic <req,rsp,ws>+` | `intercept`, `ic` | Begins interception mode. Press enter to leave interception mode and return to the command prompt. Pass in `request` to intercept requests, `response` to intercept responses, or both to intercept both. |

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

Intercept websocket messages:
> ic ws
```

When intercepting websocket messages, the first line will indicate the direction the message is going (either to or from the server) and will be ignored if edited. The message will begin on the line afterwards.

To drop a message, delete everything, save and quit.

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

You can also generate macros that have Pappy `Request` objects created with the same information as requests you've already made.

**Example using new macro API coming soon, I promise. Check out ProxyClient in proxy.py for API implementation**

### Passing Arguments to Macros

When you run the macro, any additional command line arguments will be passed to the run_macro function in the `args` argument.

**Example using new macro API coming soon, I promise. Check out ProxyClient in proxy.py for API implementation**

### Macro Commands

| Command | Aliases | Description |
|:--------|:--------|:------------|
| `lma [dir]` | `load_macros`, `lma` | Load macros from a directory. If `dir` is not given, use the current directory (the project directory) |
| `rma <macro name>` | `run_macro`, `rma` | Run a macro with the given name. You can use the shortname, filename, or long name. |
| `gma <name> [id(s)]` | `generate_macro`, `gma` | Generate a macro with the given name. If request IDs are given, the macro will contain request objects that contain each request. |
| `rpy <id(s)>` | `rpy` | Print the Python object definitions for each of the given ids |

### Request Objects

**Example using new macro API coming soon, I promise. Check out ProxyClient in proxy.py for API implementation**

Intercepting Macros
-------------------
Intercepting macros let you mangle requests as they pass through the proxy. Similarly to normal macros, an intercepting macro is any python script with an "int" prefix. For example, `int_name.py` would be a valid intercepting macro name. They are also loaded with the `lma` command. An intercepting macro can define functions to mangle requests, responses, or websocket messages.

**Example using new macro API coming soon, I promise. Check out ProxyClient in proxy.py for API implementation**


### Enabling/Disabling Intercepting Macros
You can use the following commands to start/stop intercepting macros

| Command | Aliases | Description |
|:--------|:--------|:------------|
| `lma [dir]` | `load_macros`, `lma` | Load macros from a directory. If `dir` is not given, use the current directory (the project directory) |
| `rim <macro name>` | `run_int_macro`, `rim` | Run an intercepting macro. Similarly to normal macros you can use the name, short name, or file name of the macro. |
| `sim <macro name> [args]` | `stop_int_macro`, `sim` | Stop an intercepting macro. If arguments are given, they will be passed to the macro's `init(args)` function if it exists. |
| `lim` | `list_int_macros`, `lsim` | List all enabled/disabled intercepting macros |
| `gima <name>` | `generate_int_macro`, `gima` | Generate an intercepting macro with the given name. |

Resubmitting Groups of Requests
-------------------------------
You can use the `submit` request to resubmit requests. It is suggested that you use this command with a heavy use of filters and using the wildcard (`*`) to submit all in-context requests. Be careful submitting everything in context, remember, if you have to Ctl-C out you will close Pappy and lose all in-memory requests!

| Command | Aliases | Description |
|:--------|:--------|:------------|
| `submit reqids [-m] [-u] [-p] [-c [COOKIES [COOKIES ...]]] [-d [HEADERS [HEADERS ...]]]` | `submit` | Submit a given set of requests. Request IDs must be passed in as the first argument. The wildcard (`*`) selector can be very useful. Resubmitted requests are given a `resubmitted` tag. See the arguments section for information on the arguments. |

### Useful Filters For Selecting Requests to Resubmit

* `before` and `after` to select requests in a time range. You can use the `after` filter on the most recent request, browse the site, then use the `before` filter to select a continuous browsing session.
* `verb` if you only want to select GET requests
* `path ct logout` to avoid logging out
* Use tags to select requests to submit then filter by the tag

### Arguments

There are a few simple parameters you can pass to the command to modify requests. These behave like normal command parameters in the terminal. If you need something more complex (ie getting CSRF tokens, refreshing the session token, reacting to Set-Cookie headers, etc.) you should consider writing a macro and using the `main_context_ids` function to get in-context IDs then iterating over them and handling them however you want.

| Argument | Description |
|:---------|:------------|
| `-c <cookie>=<val>` | Modify a cookie on each request before submitting. Can pass more than one pair to the flag to modify more than one cookie. Does not encode the cookie values in any way. |
| `-d <header>=<val>` | Modify a header on each request before submitting. Can pass more than one pair to the flag to modify more than one header. |
| `-m` | Store requests in memory instead of saving to the data file. |
| `-u` | Only submit one request per endpoint. Will count requests with the same path but different url params as *different* endpoints. |
| `-p` | Only submit one request per endpoint. Will count requests with the same path but different url params as *the same* endpoints. |
| `-o <id>` | Copy the cookies used in another request |

Examples:
```
# Resubmit all in-context requests with the SESSIONID cookie set to 1234 and SESSIONSTATE set to {'admin'='true'}
pappy> submit * -c SESSIONID=1234 SESSIONSTATE=%7B%27admin%27%3A%27true%27%7D

# Resubmit all in-context requests with the User-Agent header set to "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)" then store them in memory
pappy> submit * -m -h "User-Agent=Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"

# Submit requests 123, 124, and 125 with a new user agent and new session cookies and store the submitted requests in memory
pappy> submit 123,124,125 -h "User-Agent=Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)" -c SESSIONID=1234 SESSIONSTATE=%7B%27admin%27%3A%27true%27%7D
```

Saving Messages To Disk
-----------------------

| Command | Aliases | Description |
|:--------|:--------|:------------|
| `save_request <reqid(s)> [filename]` | `save_request`, `savereq` | Save full request to disk. If no filename is given, it's saved with the name `req_<reqid>`. |
| `save_response <reqid(s)> [filename]` | `save_response`, `saversp` | Save full response to disk. If no filename is given, it's saved with the name `req_<reqid>`. |
| `dump_response <reqid> [filename]` | `dump_response` | Save the body portion of a response response to the given filename (useful for images, .swf, etc). If no filename is given, it uses the name given in the path. |


Using an Proxy
-------------------
Pappy allows you to use an upstream SOCKS or HTTP proxy. You can do this by adding an `proxy` value to config.json. You then configure the address of the proxy and whether it is a SOCKS proxy. To use credentials, include "username" and "password" values in the configuration. A Few examples:

```
Do not use a proxy:
    "proxy": {"use_proxy": false, "host": "", "port": 0, "is_socks": false}
Use an HTTP proxy at someproxy.foo port 8080
    "proxy": {"use_proxy": true, "host": "someproxy.foo", "port": 8080, "is_socks": false}
Use a SOCKS proxy at someproxy.foo port 8081
    "proxy": {"use_proxy": true, "host": "someproxy.foo", "port": 8081, "is_socks": true}
Use an HTTP proxy at someproxy.foo port 8080 with a username of Mario and a password of Lu1g1
    "proxy": {"use_proxy": true, "host": "someproxy.foo", "port": 8080, "is_socks": false, "username": "Mario", "password": "Lu1g1"}
```

At the moment, all in and out of scope requests will pass through the proxy.

Transparent Host Redirection
----------------------------
Sometimes you get a frustrating thick client that doesn’t let you mess with proxy settings to get it to go through a proxy. In order to debug applications like this, Pappy can behave like a regular HTTP server and forward any requests it receives to a specific host. That way the application doesn't have to be aware that it is using a proxy. You can redirect the traffic for an application to the proxy through other means such as editing the hosts file.

You can have a listener transparently redirect requests to a specific host by adding a "transparent" value to a listener which determines a host, port, and whether TLS should be used to make the connection.

```
"listeners": [
        {"port": 8080, "interface": "127.0.0.1", "transparent": {"host": "www.example.faketld", "port": 80, use_tls: false},
        {"port": 8443, "interface": "127.0.0.1", "transparent": {"host": "www.example.faketld", "port": 443, use_tls: true},
    ]
```

You should also be aware that it takes root permissions to listen on low numbered ports. As a result, we’ll need to do some root stuff to listen on ports 80 and 443 and get the data to Pappy. There are two ways to get the traffic to Pappy. The first is to set up port forwarding as root to send traffic from localhost:80 to localhost:8080 and localhost:443 to localhost:8443 (since we can listen on 8080 and 8443 without root). Or you can YOLO, run Pappy as root and just have it listen on 80 and 443.

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

FAQ
---

### Text just appeared over my prompt! What do I do?!
Unfortunately I've been a bit lazy when it comes to printing errors to the terminal. A lot of stuff is just printed to stdout using `print`. This has the side effect of printing over your input. I'm very sorry and I'm trying to work on better solutions, but for now:

* Hit Ctl-L to clear the terminal. Your input will be saved.


Changelog
---------
The boring part of the readme

* 0.3.1
    * Borked the git push so it's version 0.3.1 now
* 0.3.0
    * Rewrote large amount of code in Go (see the [puppy repo](https://github.com/roglew/puppy) for all the stuff implemented in Go)
    * Rewrote the rest of the python
    * Moved to python3
    * Deleted python docs because ugh. Will add docs for the new plugin API later.
    * This was too much work and not worth it in any way
* 0.2.14
    * Critical bugfixes
* 0.2.13
    * Refactor proxy core
    * WEBSOCKETS
    * Saved contexts
    * New features in `submit` command
    * Fixed bugs, added bugs
* 0.2.12
    * Add error handling for if creating a connection fails
    * Minor bugfixes
* 0.2.11
    * Project directory compression/encryption. Thanks, onizenso!
    * Add `submit` command
    * Add macro templates
    * Add header replacement and resubmit in-context requests macro templates
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
