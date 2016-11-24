#!/usr/bin/env python3

import sys, platform
from os import listdir, path, walk, stat
import glob
from flask import  Flask, Response, request, abort, jsonify, send_from_directory

PCAP_DIR = './data/dumps/'
ALLOWED_EXTENSIONS = set(['pcap'])
LAST_FILENAME="TEST"

import subprocess
import json

app = Flask(__name__)


#for the remote sniffer
@app.route('/sniffer_api/HelloWorld', methods=['GET'])
def get_HelloWorld():
    return Response(json.dumps("HelloWorld"))


#for the remote sniffer
@app.route('/sniffer_api/launchSniffer', methods=['POST'])
def launchSniffer():
    testcase_id = request.args.get('testcase_id', '')
    interface_name = request.args.get('interface', '')
    filter = request.args.get('filter', '')

    if filter is '':
        #defaults
        filter = 'udp port 5683'

    if (interface_name is None ) or (interface_name==''):
        sys_type = platform.system()
        if sys_type == 'Darwin':
            interface_name = 'lo0'
        else:
            interface_name = 'lo'
        # TODO for windows?

        # when coordinator is beeing deployed in a VM it should provide the iterface name ex iminds-> 'eth0.29'


    print("-----------------")
    print("LAUNCHING SNIFFER")
    print("-----------------")

    _launchSniffer(testcase_id,interface_name,filter)
    return Response(json.dumps( ("sniffer","sniffing traffic for " + testcase_id + ' / ' + filter + ' / ' + interface_name)))

#for the remote sniffer
@app.route('/sniffer_api/finishSniffer', methods=['GET','POST'])
def get_finishSniffer():
    global LAST_FILENAME
    print("-----------------")
    print("TERMINATE SNIFFER")
    print("-----------------")
    _finishSniffer()
    return Response(json.dumps("testcase sniffer stopped, dumped file : " + LAST_FILENAME ))

#for the remote sniffer
@app.route('/sniffer_api/getPcap', methods=['GET'])
def get_getPcap():
    global PCAP_DIR
    testcase_id = request.args.get('testcase_id', '')
    print("----------------------------")
    print("PROCESSING GET PCAP REQUEST")
    print("-----------------------------")
    #application/cap
    assert(testcase_id)
    #check if the size is not zero
    assert((stat(PCAP_DIR+ testcase_id + ".pcap",)).st_size != 0 )
    return send_from_directory(PCAP_DIR, testcase_id + ".pcap", as_attachment=True)


#sudo needed?
def _launchSniffer(testcase_id, interface_name, filter):
    # TODO re-implement with subprocess module
    import os
    global LAST_FILENAME
    LAST_FILENAME = PCAP_DIR + testcase_id + ".pcap"

    # -U -w params: as each packet is saved, it will be written to the output
    #               file, rather than being written only when the output buffer
    #               fills.
    cmd = "tcpdump -i " + interface_name + " -s 200 -U -w " + LAST_FILENAME +  " " + filter+ " &"
    print("-----------------")
    print("sniffing:  " + cmd)
    print("-----------------")
    os.system(cmd)


#sudo needed?
def _finishSniffer():
    proc = subprocess.Popen(["pkill", "-INT", "tcpdump"], stdout=subprocess.PIPE)
    proc.wait()

#sudo needed?
def _getSniffedPcap():
    return LAST_FILENAME


if  __name__ == '__main__':
    app.run(host = '0.0.0.0', port = 8081, debug = True)
#_launchSniffer("testcase_id")
