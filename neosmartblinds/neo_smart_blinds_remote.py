import logging
import socket
import time

import requests

_LOGGER = logging.getLogger(__name__)
LOGGER = logging.getLogger(__name__)


class NeoSmartBlinds:
    commands = {"up": "up", "down": "dn", "micro_up": "mu", "micro_down": "md", "stop": "sp"}
    """
    Commands: 
    Up              = up
    Down            = dn
    Micro Up        = mu
    Micro Down      = md
    Stop            = sp
    To Favorite     = sp (if stopped)
    Set favorite    = pp
    Reverse         = rv
    Confirm(Sync)   = sc
    Limit           = ld
    
    """

    def __init__(self, host, the_id, device, close_time, port=8839):
        self._host = host
        self._port = port
        self._the_id = the_id
        self._device = device
        self._close_time = int(close_time)
        
    def adjust(self, pos):
        if pos == 50:
            self.send_command_new('gp')
            return
        if pos >= 51:
            self.send_command_new('up')
            wait1 = (pos - 50)*2
            wait = (wait1*self._close_time)/100
            LOGGER.warning(wait)
            time.sleep(wait)
            self.send_command_new('sp')
            return            
        if pos <= 49:    
            self.send_command_new('dn')
            wait1 = (50 - pos)*2
            wait = (wait1*self._close_time)/100
            LOGGER.warning(wait)
            time.sleep(wait)
            self.send_command_new('sp')
            return

    def sendCommand_old(self, code):

        # print("Sending: " + code)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            newcode = self._device + code + '\r\n'
            s.connect((self._host, self._port))
            while True:
                s.send(newcode)
        except:
            return

    def send_command_new(self, command):
        URL = "http://192.168.1.168:8838/neo/v1/transmit"

        PARAMS = {'id': self.id, 'command': self.device + "-" + command}

        r = requests.get(url=URL, params=PARAMS)

        print(r)