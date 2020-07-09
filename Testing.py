import socket
import time

import requests

from neosmartblinds.neo_smart_blinds_remote import NeoSmartBlinds

host = "192.168.1.168"
port = "8839"
id = "34002d000e47393032323330"
device = "044.171-01"
close_time = 10


def sendCommand(code):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(s.send("test", ))
        newcode = device + code + '\r\n'
        print(newcode)
        test = s.connect((host, port))
        print(test)
        while True:
            print(s.send(newcode.encode()))
    except:
        return


def send_command_new(command):
    URL = "http://192.168.1.168:8838/neo/v1/transmit"

    PARAMS = {'id': id, 'command': device + "-" + command}

    r = requests.get(url=URL, params=PARAMS)

    print(r)


for i in range(1):
    send_command_new("dn")
    time.sleep(9)
    send_command_new("sp")


# tester = NeoSmartBlinds("192.168.1.168", device, port, close_time)
# tester.adjust(50)
