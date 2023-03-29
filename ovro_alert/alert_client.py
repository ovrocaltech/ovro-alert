import requests
import json
from os import environ
from astropy import time


if "RELAY_KEY" in environ:
    RELAY_KEY = environ["RELAY_KEY"]
else:
    RELAY_KEY = input("enter RELAY_KEY")


class AlertClient():
    def __init__(self, route):
        """ Client for communicating via relay API.
        route defines channel for commuincation (e.g., sending to OVRO-LWA via "lwa")
        """

        self.ip = '131.215.200.144'  # major
        self.port = '8001'
        self.url = f'http://{ip}:{port}'
        self.route = route
        
        def get(self, password=RELAY_KEY):
            """ Get command from relay server.
            """

            headers = {"Accept": "application/json"}
            resp = requests.get(url=self.url+self.route, headers=headers, params={'key': RELAY_KEY})
            return resp.json()

        def set(self, command, args={}, password=RELAY_KEY):
            """ Put command to relay.
            """

            headers = {"Accept": "application/json", 'Content-Type': 'application/json'}
            mjd = time.Time.now().mjd
            dd = {"command": command, "command_mjd": mjd, "args": args}

            resp = requests.put(url=self.url+self.route, headers=headers, data=json.dumps(dd),
                                params={'key': RELAY_KEY})

            return resp.status_code
