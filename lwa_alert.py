import requests
import json
from os import environ
from time import sleep
from astropy import time


if "RELAY_KEY" in environ:
    RELAY_KEY = environ["RELAY_KEY"]
else:
    RELAY_KEY = input("enter RELAY_KEY")

ip = '131.215.200.144'  # major
port = '8001'
url = f'http://{ip}:{port}'
path = '/lwa'


def get_lwa(password=RELAY_KEY):
    """ Get LWA command from relay.
    """

    headers = {"Accept": "application/json"}

    resp = requests.get(url=url+path, headers=headers, params={'key': RELAY_KEY})

    return resp.json()


def set_lwa(command, args={}, password=RELAY_KEY):
    """ Put LWA command to relay.
    """

    headers = {"Accept": "application/json", 'Content-Type': 'application/json'}
    mjd = time.Time.now().mjd
    dd = {"command": command, "command_mjd": mjd, "args": args}

    resp = requests.put(url=url+path, headers=headers, data=json.dumps(dd),
                        params={'key': RELAY_KEY})

    return resp.status_code


def poll_lwa(loop=5):
    """ Poll the relay API for LWA commands.
    """

    dd = get_lwa()
    while True:
        mjd = time.Time.now().mjd
        dd2 = get_lwa()
        if dd2["command_mjd"] != dd["command_mjd"]:
            dd = dd2.copy()
            print(f"New command: {dd}")
        else:
            sleep(loop)
            continue
        
