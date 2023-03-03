import requests
import json
from os import environ
from astropy import time


if "RELAY_KEY" in environ:
    RELAY_KEY = environ["RELAY_KEY"]
else:
    RELAY_KEY = input("enter RELAY_KEY")

ip = '131.215.200.144'  # major
port = '8001'
url = f'http://{ip}:{port}'


def get_lwa(password=RELAY_KEY):
    """ Get LWA command from relay.
    """

    path = '/lwa'
    headers = {"Accept": "application/json"}

    resp = requests.get(url=url+path, headers=headers, params={'key': RELAY_KEY})

    return resp.json()


def put_lwa(command, args={}, password=RELAY_KEY):
    """ Put LWA command to relay.
    """

    path = '/lwa'
    headers = {"Accept": "application/json", 'Content-Type': 'application/json'}
    mjd = time.Time.now().mjd
    dd = {"command": command, "command_mjd": mjd, "args": args}

    resp = requests.put(url=url+path, headers=headers, data=json.dumps(dd),
                        params={'key': RELAY_KEY})

    return resp.status_code


def poll_lwa(loop=1):
    """ Poll the relay API for LWA commands.
    """
    
    while True:
        mjd = time.Time.now().mjd
        dd = get_lwa()
        
