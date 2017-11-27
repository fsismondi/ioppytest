"""Simple HTTP Server.

This module builds on BaseHTTPServer by implementing the standard GET
and HEAD requests in a fairly straightforward manner.

"""

import os
import html
import glob
import json
import yaml
import urllib
import shutil
import logging
import posixpath
import mimetypes
from jinja2 import Template

from ioppytest import TD_COAP, TD_COAP_CFG, TD_6LOWPAN, RESULTS_DIR, AUTO_DISSECTION_FILE, PROJECT_DIR
from ioppytest.test_coordinator.testsuite import TestCase

from http.server import BaseHTTPRequestHandler, HTTPServer
COMPONENT_ID = 'webserver'

logger = logging.getLogger(COMPONENT_ID)

td_list = []
FILENAME_HTML_REPORT = 'testsuite_results.html'

tail = """
"mantainer": "Federico Sismondi",
"mantainer_email": "federico.sismondi@inria.fr"

if you spotted any errors or you want to comment on sth don't hesitate to contact me.
"""


with open(TD_COAP, "r", encoding="utf-8") as stream:
    yaml_docs = yaml.load_all(stream)
    for yaml_doc in yaml_docs:
        if type(yaml_doc) is TestCase:
            td_list.append(yaml_doc)

with open(TD_6LOWPAN, "r", encoding="utf-8") as stream:
    yaml_docs = yaml.load_all(stream)
    for yaml_doc in yaml_docs:
        if type(yaml_doc) is TestCase:
            td_list.append(yaml_doc)


def create_html_test_results():
    resp = None
    with open(FILENAME_HTML_REPORT, 'w+') as file:
        items = []
        for filename in glob.iglob(RESULTS_DIR + '/*_verdict.json'):
            try:
                with open(filename, 'r') as jsonfile:
                    an_item = json.loads(jsonfile.read())
            except:
                an_item = {'description': 'error importing'}
            items.append(an_item)
        resp = template_test_vedict.render(items=items)
        file.write(resp)
    return resp

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
        if self.path.startswith('/tests/') or self.path.startswith('/ioppytest/tests/'):
            logger.debug('Handling TESTCASE request: %s' % self.path)
            return self.handle_testcase(self.path)
        elif self.path.startswith('/ioppytest/pcaps'):
            logger.debug('Handling PCAP request: %s' % self.path)
            return self.handle_pcaps(self.path)
        elif self.path.startswith('/ioppytest/results'):
            logger.debug('Handling RESULTS request: %s' % self.path)
            return self.handle_results(self.path)
        elif self.path.startswith('/ioppytest/packets'):
            logger.debug('Handling PACKETS dissection request: %s' % self.path)
            return self.handle_packets(self.path)

        else:  # allow introspection of project directory
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

    def handle_pcaps(self, path):
        logger.info('Handling data: %s' % path)
        assert '/pcaps' in path

        if 'IEEE802_15_4' in path:
            file = os.path.join(PROJECT_DIR, 'ioppytest', 'test_analysis_tool', 'tmp', 'DLT_IEEE802_15_4.pcap')
        elif 'DLT_RAW' in path:
            file = os.path.join(PROJECT_DIR, 'ioppytest', 'test_analysis_tool', 'tmp', 'DLT_RAW.pcap')
        else:
            file = os.path.join(PROJECT_DIR, 'ioppytest', 'test_analysis_tool', 'tmp', 'DLT_IEEE802_15_4.pcap')

        with open(file, 'rb') as f:
            self.send_response(200)
            self.send_header("Content-Type", 'application/octet-stream')
            self.send_header("Content-Disposition", 'attachment; filename="{}"'.format(os.path.basename(file)))
            fs = os.fstat(f.fileno())
            self.send_header("Content-Length", str(fs.st_size))
            self.end_headers()
            # self.copyfile(f, self.wfile)
            shutil.copyfileobj(f, self.wfile)

    def handle_results(self, path):
        assert "/results" in path
        # tc_name = path.split('/')[-1]


        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        resp = create_html_test_results()
        self.wfile.write(bytes(resp, 'utf-8'))

    def handle_packets(self, path):
        assert "/packets" in path
        # tc_name = path.split('/')[-1]
        items = ''

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        with open('session_dissections.html', 'w+') as file:

            try:
                with open(AUTO_DISSECTION_FILE, 'r') as jsonfile:
                    frames = json.loads(jsonfile.read())

            except Exception as e:
                frames = {'description': 'error importing',
                          'error': str(e)
                          }

            resp = template_frame_list.render(items=frames)
            file.write(resp)

        self.wfile.write(bytes(resp, 'utf-8'))

    def handle_testcase(self, path):
        """
        Helper to produce testcase for paths like : (...)/tests/TD_COAP_(...)
        """
        assert ("/tests/") in path
        tc_name = path.split('/')[-1]
        tc = None

        for tc_iter in td_list:

            if tc_iter.id.lower() == tc_name.lower():
                tc = tc_iter

                break

        if tc is None:
            self.send_error(404, "Testcase couldn't be found")
            return None

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        head = """
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
        self.wfile.write(bytes("<h2>Notes: <em>%s</em></h2>\n" % tc.notes, 'utf-8'))
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

            if isinstance(step.description, list):
                self.wfile.write(bytes("<ol>\n", 'utf-8'))
                for item in step.description:
                    if isinstance(item, list):
                        self.wfile.write(bytes("<ol>\n", 'utf-8'))
                        for item_of_item in item:
                            self.wfile.write(bytes("<li>%s</li>  \n" % str(item_of_item), 'utf-8'))
                        self.wfile.write(bytes("</ol>\n", 'utf-8'))
                    else:
                        self.wfile.write(bytes("<li>%s</li>" % str(item), 'utf-8'))
                self.wfile.write(bytes("</ol>\n", 'utf-8'))
            else:
                self.wfile.write(bytes("<em>%s</em>\n" % str(step.description), 'utf-8'))

            self.wfile.write(bytes("</p>\n", 'utf-8'))
            self.wfile.write(bytes("<hr>\n", 'utf-8'))

        self.wfile.write(bytes("<tail>%s</tail> </body>\n" % tail, 'utf-8'))
        self.wfile.write(bytes("</html>\n", 'utf-8'))
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

        # list.sort(lambda a, b: cmp(a.lower(), b.lower()))
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
        '': 'application/octet-stream',  # Default
        '.py': 'text/plain',
        '.c': 'text/plain',
        '.h': 'text/plain',
        '.yaml': 'text/plain',
        '.yml': 'text/plain',
        '.log': 'text/plain',
        '.json': 'text/plain',
    })


template_frame_list = Template("""
        <!DOCTYPE html>
        <html>
        <head>
        <style>
        * {
            font-family:Arial !important
            text-align: center  !important
        }
        </style>
        </head>

        <body>

        <table style="width:100%;text-align: center"; border="1">
          <tr>
            <th style="width:10%">Frame Info</th>
            <th style="width:25%">Frame Dissection</th>
          </tr>

        {% for frame in items %}

        <tr>
           <td class="c1">frame id: {{frame.id}}<br>frame timestamp: {{frame.timestamp}}<br>frame error: {{frame.error}}</td>
           <td class="c1">  
           <table style="width:100%;text-align: center"; border="0.1">
           {% for layer in frame.protocol_stack %}
            <tr>
                <th style="width:5%">{{layer._protocol}}</th>
                <td style="width:25%">{{layer}} </td>
            </tr>
            {% endfor %}
           </table>
           </td>
        </tr>
        {% endfor %}
        </table>
        </body>""")

template_test_vedict = Template("""
        <!DOCTYPE html>
        <html>
        <head>
        <style>
        * {
            font-family:Arial !important
            text-align: center  !important
        }
        </style>
        </head>

        <body>
        <ul>
            <li><a href="http://127.0.0.1:8080/results/COAP_CORE">COAP_CORE</a>
            <li><a href="http://127.0.0.1:8080/results/LINK">LINK</a>
            <li><a href="http://127.0.0.1:8080/results/BLOCK">BLOCK</a>
            <li><a href="http://127.0.0.1:8080/results/OBSERVE">OBSERVE</a>
            <li><a href="http://127.0.0.1:8080/results/DTLS">DTLS</a>
        </ul>
        
        <table style="width:100%;text-align: center"; border="1">
          <tr>
            <th style="width:10%">Testcase ID</th>
            <th style="width:25%">Objective</th>
            <th style="width:5%">State</th>
            <th style="width:10%">Verdict</th>
            <th style="width:50%">Partial verdicts</th>
          </tr>

        {% for item in items %}
        <tr>
           <td class="c1"><a href={{item.testcase_ref}}>{{item.testcase_id}}</a></td>
           <td class="c2">{{item.objective}}</td>
           <td class="c3">{{item.state}}</td>
            {% if item.verdict == 'error' %}
                <td class="c4" bgcolor="#FF0000">{{ item.verdict.upper()  }}</td>
             {% elif item.verdict == 'pass' %}
                <td class="c4" bgcolor="#00FF00">{{ item.verdict.upper()  }}</td>
            {% elif item.verdict == 'inconc' %}
                <td class="c4" bgcolor="#FFFF00">{{ item.verdict.upper()  }}</td>
            {% elif item.verdict == 'inconclusive' %}
                <td class="c4" bgcolor="#FFFF00">{{ item.verdict.upper()  }}</td>
            {% endif %}
           <td class="c5">
              <table style="width:100%"; border="1">
              {% for subitem in item.partial_verdicts %}
                       <tr class="c6"">
                          <td class="c7">{{subitem[0]}}</td>
                          <td class="c8">{{subitem[1]}}</td>
                          <td class="c9">{{subitem[2]}}</td>
                       </tr>
              {% endfor %}
              </table>
           </tr>
           </td>
        </tr>
        {% endfor %}
        </table>
        </body>""")

template_test_vedict_menu = Template("""
        <!DOCTYPE html>
        <html>
        <head>
        <style>
        * {
            font-family:Arial !important
            text-align: center  !important
        }
        </style>
        </head>

        <body>
        <ul>
            <li><a href="http://127.0.0.1:8080/results/COAP_CORE">COAP_CORE</a>
            <li><a href="http://127.0.0.1:8080/results/LINK">LINK</a>
            <li><a href="http://127.0.0.1:8080/results/BLOCK">BLOCK</a>
            <li><a href="http://127.0.0.1:8080/results/OBSERVE">OBSERVE</a>
            <li><a href="http://127.0.0.1:8080/results/DTLS">DTLS</a>
        </ul>
        </body>""")
