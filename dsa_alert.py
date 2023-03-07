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
path = '/dsa'


def get_dsa(password=RELAY_KEY):
    """ Get DSA command from relay.
    """

    headers = {"Accept": "application/json"}

    resp = requests.get(url=url+path, headers=headers, params={'key': RELAY_KEY})

    return resp.json()


def set_dsa(command, args={}, password=RELAY_KEY):
    """ Set DSA command to relay.
    """

    headers = {"Accept": "application/json", 'Content-Type': 'application/json'}
    mjd = time.Time.now().mjd
    dd = {"command": command, "command_mjd": mjd, "args": args}

    resp = requests.put(url=url+path, headers=headers, data=json.dumps(dd),
                        params={'key': RELAY_KEY})

    return resp.status_code


def poll_dsa(loop=5):
    """ Poll the relay API for DSA commands.
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

