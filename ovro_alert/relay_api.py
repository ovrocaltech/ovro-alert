from os import environ
from typing import Union

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel

from astropy import time
from slack_sdk import WebClient


if "SLACK_TOKEN_CR" in environ:
    cl = WebClient(token=environ["SLACK_TOKEN_CR"])
else:
    print("No slack token found. Will not push to slack.")
    cl = None

if "RELAY_KEY" in environ:
    RELAY_KEY = environ["RELAY_KEY"]
else:
    RELAY_KEY = input("enter RELAY_KEY")

app = FastAPI()
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*.caltech.edu"])

dd = {"dsa": {"command": None, "command_mjd": None},#, "test_mjd": None},
      "lwa": {"command": None, "command_mjd": None},#, "test_mjd": None},
      "ligo": {"command": None, "command_mjd": None},#, "test_mjd": None},
      "chime": {"command": None, "command_mjd": None},#, "test_mjd": None}}
      "gcn": {"command": None, "command_mjd": None}}#, "test_mjd": None}}


class Command(BaseModel):
    command: str   # type?
    command_mjd: float
    args: dict

@app.get("/")
def get_root():
    return "ovro-alert: An API for alert-driven OVRO observations"


@app.get("/lwa")
def get_lwa(key):
    if key == RELAY_KEY:
        dd2 = {"read_mjd": time.Time.now().mjd}
        dd2.update(dd["lwa"])
        return dd2
    else:
        return "Bad key"


@app.put("/lwa")
def set_lwa(command: Command, key: str):
    if key == RELAY_KEY:
        dd['lwa'] = {"command": command.command, "command_mjd": command.command_mjd,
                     "args": command.args}
        return f"Set lwa command: {command.command} with {command.args}"

    else:
        return "Bad key"


@app.get("/dsa")
def get_dsa(key):
    if key == RELAY_KEY:
        dd2 = {"read_mjd": time.Time.now().mjd}
        dd2.update(dd["dsa"])
        return dd2
    else:
        return "Bad key"


@app.put("/dsa")
def set_dsa(command: Command, key: str):
    if key == RELAY_KEY:
        dd['dsa'] = {"command": command.command, "command_mjd": command.command_mjd,
                     "args": command.args}

        if command.command == 'observation' and cl is not None:
            res = cl.chat_postMessage(channel='#alert-driven-astro', text=f'DSA-110 event with args: {command.args}')

        return f"Set dsa command: {command.command} with {command.args}"
    else:
        return "Bad key"


@app.get("/ligo")
def get_ligo(key):
    if key == RELAY_KEY:
        dd2 = {"read_mjd": time.Time.now().mjd}
        dd2.update(dd["ligo"])
        return dd2
    else:
        return "Bad key"

@app.put("/ligo")
def set_ligo(command: Command, key: str):
    if key == RELAY_KEY:
#        if command.command == 'test':
#            dd["ligo"].update({"test_mjd": command.command_mjd})
#            return f"Set LIGO test"
#        else:
        dd["ligo"] = {"command": command.command, "command_mjd": command.command_mjd,
                      "args": command.args}

        if command.command == 'observation' and cl is not None:
            res = cl.chat_postMessage(channel='#alert-driven-astro', text=f'LIGO event with args: {command.args}')

        return f"Set LIGO event: {command.command} with {command.args}"
    else:
        return "Bad key"


@app.get("/chime")
def get_chime(key):
    if key == RELAY_KEY:
        dd2 = {"read_mjd": time.Time.now().mjd}
        dd2.update(dd["chime"])
        return dd2
    else:
        return "Bad key"


@app.put("/chime")
def set_chime(command: Command, key: str):
    if key == RELAY_KEY:
#        if command.command == 'test':
#            dd["chime"].update({"test_mjd": command.command_mjd})
#            return f"Set CHIME test"
#        else:
        dd['chime'] = {"command": command.command, "command_mjd": command.command_mjd,
                       "args": command.args}

        if command.command == 'observation' and cl is not None:
            res = cl.chat_postMessage(channel='#alert-driven-astro', text=f'CHIME/FRB event with args: {command.args}')

        return f"Set CHIME event: {command.command} with {command.args}"
    else:
        return "Bad key"


@app.get("/gcn")
def get_gcn(key):
    if key == RELAY_KEY:
        dd2 = {"read_mjd": time.Time.now().mjd}
        dd2.update(dd["gcn"])
        return dd2
    else:
        return "Bad key"


@app.put("/gcn")
def set_gcn(command: Command, key: str):
    if key == RELAY_KEY:
#        if command.command == 'test':
#            dd["chime"].update({"test_mjd": command.command_mjd})
#            return f"Set CHIME test"
#        else:
        dd['gcn'] = {"command": command.command, "command_mjd": command.command_mjd,
                       "args": command.args}

        if command.command == 'observation' and cl is not None:
            res = cl.chat_postMessage(channel='#alert-driven-astro', text=f'GCN event with args: {command.args}')

        return f"Set GCN event: {command.command} with {command.args}"
    else:
        return "Bad key"
