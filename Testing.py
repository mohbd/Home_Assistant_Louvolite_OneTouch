import socket
import time

import requests

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
)

import homeassistant.helpers.config_validation as cv

host = "192.168.1.168"
port = "8838"
id = "34002d000e47393032323330"
device = "044.171-01"
close_time = 10

testing = vol.Schema({ATTR_ENTITY_ID: cv.comp_entity_ids})


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
    print(url)

    params = {'id': id, 'command': device + "-" + command, 'hash': str(time.time()).strip(".")[-7:]}

    r = requests.get(url=url, params=params)

    print(r)

print(testing)

# print(str(time.time())[:7])

for i in range(1):
    send_command_new("gp")
    #time.sleep(9)
    #send_command_new("sp")


# tester = NeoSmartBlinds("192.168.1.168", device, port, close_time)
# tester.adjust(50)
