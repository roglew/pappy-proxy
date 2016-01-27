Contributing
************

.. contents:: Table of Contents
   :local:

Contributing
============

Want to help out? Awesome! This page will give you some ideas on features you can implement. Make sure to read the docs on `writing plugins <pappyplugins>`_ before starting since most of these features are implemented as plugins

Feature Wishlist
================

This is a wish-list of features that I haven't gotten around to implementing, but could probably be done without too much trouble. I would prefer that you try and implement something via plugin because the core code tends to get changed up pretty regularly. If you build something via plugin, worst case scenario a few API calls break. If you try and implement something in the core, worst case scenario everything changes and your efforts are lost because the function you were modifying doesn't exist any more.

If you need to save data to the disk, just save a JSON object to disk for your plugin. When you submit the pull request, I will make changes to plugin/schema to store the data in the datafile.

Anyways, here's some ideas for things you could implement:

* Creds management
    When doing a test, the client may give you a number of usernames/passwords. It would be great if you can implement a system to easily copy/paste usernames and passwords from the console so you don't have to keep opening up creds.txt and copying from there. My suggestion is to add a command to coppy a username or a password and let people tab complete the username.
* Session management
    Add a system to manage sessions and easily swap between them. I already started on a sessions class in pappyproxy/sessions.py which might help you get started.
* Scan history for easy findings
    Some findings are as simple as checking whether a header exists or not. Implement a pluging to go through history and list off some of the easier to find findings. For example you could search for things like

    * Secure/httponly flag not set on cookies (mainly session cookies)
    * Lack of HSTS headers
    * Pasword fields with auto-complete

* Perform an SSL config check on a host (ie similar functionality to an `ssllabs scan <https://www.ssllabs.com/>`_ without having to go through a website)
    Find a library to perform some kind of check for weak ciphers, etc on a host and print out any issues that are found.
* Add a SQLMap button
    Make it easy to pass a request to SQLMap to check for SQLi. Make sure you can configure which fields you do/don't want tested and by default just give either "yes it looks like SQLi" or "no it doesn't look like SQLi"
* Additional macro templates
    Write some commands for generating additional types of macros. For example let people generate an intercepting macro that does search/replace or modifies a header. Save as much typing as possible for common actions.
* Show requests/responses real-time as they go through the proxy
    Let people watch requests as they pass through the proxy. It's fine to implement this as an intercepting macro since people watching the requests aren't going to notice response streaming being disabled.
* Vim plugin to make editing HTTP messages easier
    Implement some functionality to make editing HTTP messages easier. It would be great to have a plugin to automatically add to vim when using the interceptor/repeater to make editing requests easier. Look at burp's request editor and try to implement anything you miss from it.
* Request Diff
    Add some way to compare requests. Preferably both a "diff" mode and a "just look at 2 at once" mode. Probably want to implement it as a vim plugin for consistency.

Feel free to contact me with ideas if you want to add something to this list.
