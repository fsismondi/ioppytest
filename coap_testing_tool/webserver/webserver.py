"""Simple HTTP Server.

This module builds on BaseHTTPServer by implementing the standard GET
and HEAD requests in a fairly straightforward manner.

"""


import os, logging
import posixpath
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib
import html
import yaml
import mimetypes
import re
from pathlib import Path
from coap_testing_tool import TD_COAP,TD_COAP_CFG, TD_6LOWPAN
from coap_testing_tool.test_coordinator.coordinator import TestCase
logger = logging.getLogger(__name__)


td_list = []

tail ="""
"mantainer": "Federico Sismondi",
"mantainer_email": "federico.sismondi@inria.fr"

if you spotted any errors or you want to comment on sth don't hesitate to contact me.
"""

with open(TD_6LOWPAN, "r", encoding="utf-8") as stream:
    yaml_docs = yaml.load_all(stream)
    for yaml_doc in yaml_docs:
        if type(yaml_doc) is TestCase:
            td_list.append(yaml_doc)

# TODO server config files too

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):

    """Simple HTTP request handler with GET and HEAD commands.

    This serves files from the current directory and any of its
    subdirectories.  It assumes that all files are plain text files
    unless they have the extension ".html" in which case it assumes
    they are HTML files.

    The GET and HEAD requests are identical except that the HEAD
    request omits the actual contents of the file.

    """


    def do_GET(self):
        """Serve a GET request."""
        f = self.send_head()
        if f:
            self.copyfile(f, self.wfile)
            f.close()

    def do_HEAD(self):
        """Serve a HEAD request."""
        f = self.send_head()
        if f:
            f.close()

    def send_head(self):
        """Common code for GET and HEAD commands.

        This sends the response code and MIME headers.

        Return value is either a file object (which has to be copied
        to the outputfile by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.

        """

        # check if its a testcase in the ones already loaded
        if self.path.startswith("/tests/"):
            logger.debug('Handling tescase request: %s' % self.path)
            return self.handle_testcase(self.path)

        # check if its a file in the testing tool dir
        path = self.translate_path(self.path)
        f = None

        if os.path.isdir(path):
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break
            else:
                return self.list_directory(path)
        ctype = self.guess_type(path)
        if ctype.startswith('text/'):
            mode = 'r'
        else:
            mode = 'rb'
        try:
            f = open(path, mode)
        except IOError:
            self.send_error(404, "File not found")
            return None
        self.send_response(200)
        self.send_header("Content-type", ctype)
        self.end_headers()
        return f

    def handle_testcase(self, path):
        """
        Helper to produce testcase for paths like : (...)/tests/TD_COAP_(...)
        """
        assert ("/tests/") in path
        tc_name = path.split('/')[-1]
        tc = None
        
        for tc_iter in td_list:
            logger.debug('essai 9 tc_iter : %s' % tc_iter.id.lower())
            logger.debug('essai 9 tc_name : %s' % tc_name.lower())
            if tc_iter.id.lower() == tc_name.lower():
                tc = tc_iter

                break
                  
        if tc is None:
            self.send_error(404, "Testcase couldn't be found")
            return None

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        head= """
    <html>
        <head>
        <meta charset='utf-8'>
        <style>
            h2 {
                font-family: Arial;
                font-size: 25px;
            }
            h2 em{
                font-family: Arial;
                font-size: 20px;
                font-style: normal;
                font-weight: normal;
            }
            p {
                font-family: Arial;
                font-style: normal;
                font-weight: normal;
                font-size: 18px;
            }
            tail {
                font-family: Arial;
                font-style: normal;
                font-weight: normal;
                font-size: 10px;
            }
            p em {
                font-family: Arial;
                font-style: normal;
                font-weight: normal;
                font-size: 15px;
                paddomg-legt 1.8em
            }

            li {
                display: list-item;
                font-family: Arial;
                font-style: normal;
                font-weight: normal;
                font-size: 13px;
                paddomg-legt 1.8em
            }

            table {
                border-collapse: collapse;
                font-family: Arial;
                margin-bottom: 2em;
            }
            table th, table td {
                min-width: 30px;
                padding: 4px 0 4px 10px;
            }
        </style>
        </head>\n

        """
        self.wfile.write(bytes(head, 'utf-8'))
        self.wfile.write(bytes("""<body>\n<basefont face="Arial" size="2" color="#ff0000">""", 'utf-8'))
        self.wfile.write(bytes("<title>Testcase description</title>", 'utf-8'))
        self.wfile.write(bytes("<h2>Testcase identifier: <em>%s</em> </h2>" % tc.id, 'utf-8'))


        # Test case general info
        self.wfile.write(bytes("<h2>Objective: <em>%s</em></h2>\n" % tc.objective, 'utf-8'))
        self.wfile.write(bytes("<h2>Configuration: <em>%s</em></h2>\n" % tc.configuration_id, 'utf-8'))
        self.wfile.write(bytes("<h2>Preconditions: <em>%s</em></h2>\n" % tc.pre_conditions, 'utf-8'))
        self.wfile.write(bytes("<h2>References: <em>%s</em></h2>\n" % tc.references, 'utf-8'))
        self.wfile.write(bytes("<hr>\n", 'utf-8'))

        # test case step sequence
        self.wfile.write(bytes("<h2>Step Sequence:</h2>\n", 'utf-8'))
        self.wfile.write(bytes("<ol>\n", 'utf-8'))
        for step in tc.sequence:
            self.wfile.write(bytes("<p>Step identifier: <em>%s</em></p>\n" % str(step.id), 'utf-8'))
            self.wfile.write(bytes("<p>Type: <em>%s</em></p>\n" % str(step.type), 'utf-8'))
            self.wfile.write(bytes("<p>Description:\n", 'utf-8'))

            # decompose up to two levels of nested list

            if isinstance(step.description,list):
                self.wfile.write(bytes("<ol>\n", 'utf-8'))
                for item in step.description:
                    if isinstance(item, list):
                        self.wfile.write(bytes("<ol>\n", 'utf-8'))
                        for item_of_item in item:
                            self.wfile.write(bytes("<li>%s</li>  \n" % str(item_of_item), 'utf-8'))
                        self.wfile.write(bytes("</ol>\n", 'utf-8'))
                    else:
                        self.wfile.write(bytes("<li>%s</li>"% str(item), 'utf-8'))
                self.wfile.write(bytes("</ol>\n", 'utf-8'))
            else:
                self.wfile.write(bytes("<em>%s</em>\n" % str(step.description), 'utf-8'))

            self.wfile.write(bytes("</p>\n", 'utf-8'))
            self.wfile.write(bytes("<hr>\n", 'utf-8'))


        self.wfile.write(bytes("<tail>%s</tail> </body>\n"%tail, 'utf-8'))
        self.wfile.write(bytes("</html>\n",'utf-8'))
        return

    def list_directory(self, path):
        """Helper to produce a directory listing (absent index.html).

        Return value is either a file object, or None (indicating an
        error).  In either case, the headers are sent, making the
        interface the same as for send_head().
        """


        try:
            list = os.listdir(path)
        except os.error:
            self.send_error(404, "No permission to list directory")
            return None

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        #list.sort(lambda a, b: cmp(a.lower(), b.lower()))
        self.wfile.write(bytes("<title>CoAP Testing Tool directory. dir: %s</title>\n" % self.path, 'utf-8'))
        self.wfile.write(bytes("<h2>CoAP Testing Tool directory</h2>\n", 'utf-8'))
        self.wfile.write(bytes("<h3>dir: %s</h3>\n" % self.path, 'utf-8'))
        self.wfile.write(bytes("<hr>\n<ul>\n", 'utf-8'))
        for name in list:
            fullname = os.path.join(path, name)
            displayname = linkname = name = html.escape(name)
            # Append / for directories or @ for symbolic links
            if os.path.isdir(fullname):
                displayname = name + "/"
                linkname = name + "/"
            if os.path.islink(fullname):
                displayname = name + "@"
                # Note: a link to a directory displays with @ and links with /
            self.wfile.write(bytes('<li><a href="%s">%s</a>\n' % (linkname, displayname), 'utf-8'))
        self.wfile.write(bytes("</ul>\n<hr>\n", 'utf-8'))
        return

    def translate_path(self, path):
        """Translate a /-separated PATH to the local filename syntax.

        Components that mean special things to the local file system
        (e.g. drive or directory names) are ignored.  (XXX They should
        probably be diagnosed.)

        """
        path = posixpath.normpath(urllib.parse.unquote(path))
        words = path.split('/')
        words = filter(None, words)
        path = os.getcwd()
        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.curdir, os.pardir): continue
            path = os.path.join(path, word)
        return path

    def copyfile(self, source, outputfile):
        """Copy all data between two file objects.

        The SOURCE argument is a file object open for reading
        (or anything with a read() method) and the DESTINATION
        argument is a file object open for writing (or
        anything with a write() method).

        The only reason for overriding this would be to change
        the block size or perhaps to replace newlines by CRLF
        -- note however that this the default server uses this
        to copy binary data as well.

        """
        for line in source:
            outputfile.write(bytes(line, 'utf-8'))
        return

    def guess_type(self, path):
        """Guess the type of a file.

        Argument is a PATH (a filename).

        Return value is a string of the form type/subtype,
        usable for a MIME Content-type header.

        The default implementation looks the file's extension
        up in the table self.extensions_map, using text/plain
        as a default; however it would be permissible (if
        slow) to look inside the data to make a better guess.

        """

        base, ext = posixpath.splitext(path)
        if ext is self.extensions_map:
            return self.extensions_map[ext]
        ext = ext.lower()
        if ext in self.extensions_map:
            return self.extensions_map[ext]
        else:
            return self.extensions_map['']

    extensions_map = mimetypes.types_map.copy()
    extensions_map.update({
        '': 'application/octet-stream', # Default
        '.py': 'text/plain',
        '.c': 'text/plain',
        '.h': 'text/plain',
        '.yaml' : 'text/plain',
        '.yml': 'text/plain',
        '.log': 'text/plain',
        })




