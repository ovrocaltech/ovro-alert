import sys
import logging
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import json
from os import environ
from astropy import time

logger = logging.getLogger(__name__)
logHandler = logging.StreamHandler(sys.stdout)
logFormat = logging.Formatter('%(asctime)s [%(levelname)-8s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logHandler.setFormatter(logFormat)
logger.addHandler(logHandler)
logger.setLevel(logging.DEBUG)


s = Session()
s.headers.update({"Accept": "application/json", 'Content-Type': 'application/json', "Host": "ovro.caltech.edu"})

retry = Retry(total=5, backoff_factor=0.5, allowed_methods={'GET', 'PUT'})
adapter = HTTPAdapter(max_retries=retry)
s.mount("http://", adapter)
s.mount("https://", adapter)

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

    def fullroute(self, route=None):
        """ Get full route as a string with option to overload route at end
        """

        route = route if route is not None else self.route
        return f'http://{self.ip}:{self.port}/{route}'

    def get(self, password=RELAY_KEY, route=None):
        """ Get command from relay server.
        """

        resp = s.get(url=self.fullroute(route=route), params={'key': RELAY_KEY},
                            timeout=9.05)
        if resp.status_code != 200:
            logger.error(f'oops: {resp}')
        return resp.json()

    def set(self, command, args={}, password=RELAY_KEY, route=None):
        """ Put command to relay.
        """

        mjd = time.Time.now().mjd
        dd = {"command": command, "command_mjd": mjd, "args": args}

        resp = s.put(url=self.fullroute(route=route), data=json.dumps(dd),
                            params={'key': RELAY_KEY}, timeout=9.05)

        return resp.status_code
