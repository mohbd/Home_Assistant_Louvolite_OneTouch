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
        newcode = device + code + '\r\n'
        test = s.connect((host, port))

        while True:
            print(s.send(newcode.encode()))
    except:
        return


def send_command_new(command):
    url = "http://" + host + ":" + port + "/neo/v1/transmit"

    params = {'id': id, 'command': device + "-" + command, 'hash': str(time.time()).strip(".")[-7:]}

    r = requests.get(url=url, params=params)

    print(r)


# print(str(time.time())[:7])

for i in range(1):
    send_command_new("sp")
    #time.sleep(9)
    #send_command_new("sp")


# tester = NeoSmartBlinds("192.168.1.168", device, port, close_time)
# tester.adjust(50)
