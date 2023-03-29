from os import environ
from typing import Union
from fastapi import FastAPI
from pydantic import BaseModel
from astropy import time

if "RELAY_KEY" in environ:
    RELAY_KEY = environ["RELAY_KEY"]
else:
    RELAY_KEY = input("enter RELAY_KEY")

app = FastAPI()

dd = {"dsa": {"command": None, "command_mjd": None},
      "lwa": {"command": None, "command_mjd": None},
      "swift": {"command": None, "command_mjd": None},
      "sprite": {"command": None, "command_mjd": None}}

class Command(BaseModel):
    command: str
    command_mjd: float
    args: dict

@app.get("/")
def get_root():
    return "ovro-alert: An API for alert-driven OVRO observations"


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
        return f"Set dsa command: {command.command} with {command.args}"
    else:
        return "Bad key"


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


@app.get("/swift")
def get_swift(key):
    if key == RELAY_KEY:
        dd2 = {"read_mjd": time.Time.now().mjd}
        dd2.update(dd["swift"])
        return dd2
    else:
        return "Bad key"


@app.put("/swift")
def set_swift(command: Command, key: str):
    if key == RELAY_KEY:
        dd['swift'] = {"command": command.command, "command_mjd": command.command_mjd,
                       "args": command.args}
        return f"Set swift command: {command.command} with {command.args}"
    else:
        return "Bad key"


@app.get("/sprite")
def get_sprite():
    pass


@app.put("/sprite")
def set_sprite():
    pass
