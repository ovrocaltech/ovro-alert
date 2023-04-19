import requests
import json
from os import environ
from astropy import time


if "RELAY_KEY" in environ:
    RELAY_KEY = environ["RELAY_KEY"]
else:
    RELAY_KEY = input("enter RELAY_KEY")


class AlertClient():
    def __init__(self, route, ip='131.215.200.144', port='8001'):
        """ Client for communicating via relay API.
        route defines channel for commuincation (e.g., sending to OVRO-LWA via "lwa")
        Default ip:port are for server on major.
        """

        self.ip = ip
        self.port = port
        self.route = route
        self.fullroute = f'http://{self.ip}:{self.port}/{self.route}'
        
    def get(self, password=RELAY_KEY):
        """ Get command from relay server.
        """

        headers = {"Accept": "application/json", "Host": "ovro.caltech.edu"}
        resp = requests.get(url=self.fullroute, headers=headers, params={'key': RELAY_KEY})
        if resp.status_code != 200:
            print(f'oops: {resp}')
        return resp.json()

    def set(self, command, args={}, password=RELAY_KEY):
        """ Put command to relay.
        """

        headers = {"Accept": "application/json", 'Content-Type': 'application/json', "Host": "ovro.caltech.edu"}
        mjd = time.Time.now().mjd
        dd = {"command": command, "command_mjd": mjd, "args": args}

        resp = requests.put(url=self.fullroute, headers=headers, data=json.dumps(dd),
                            params={'key': RELAY_KEY})

        return resp.status_code
