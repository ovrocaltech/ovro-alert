from os import environ
from typing import Union
import logging
import sys

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates

from astropy import time
from slack_sdk import WebClient
from ovro_alert import relay_db


logger = logging.getLogger('fastapi')
logHandler = logging.StreamHandler(sys.stdout)
logFormat = logging.Formatter('%(asctime)s [%(levelname)-8s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logHandler.setFormatter(logFormat)
logger.addHandler(logHandler)
logger.setLevel(logging.DEBUG)

if "SLACK_TOKEN_CR" in environ:
    cl = WebClient(token=environ["SLACK_TOKEN_CR"])
else:
    logger.warning("No slack token found. Will not push to slack.")
    cl = None

if "RELAY_KEY" in environ:
    RELAY_KEY = environ["RELAY_KEY"]
else:
    RELAY_KEY = input("enter RELAY_KEY")

app = FastAPI()
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*.caltech.edu", "localhost"])
templates = Jinja2Templates(directory="templates")

dd = {"dsa": {"command": None, "command_mjd": None},
      "lwa": {"command": None, "command_mjd": None},
      "ligo": {"command": None, "command_mjd": None},
      "chime": {"command": None, "command_mjd": None},
      "gcn": {"command": None, "command_mjd": None}}


@app.on_event("startup")
async def startup_event():
    """Create database on startup."""
    relay_db.create_db()


@app.get("/", response_class=HTMLResponse)
async def get_root(request: Request):
    commands = relay_db.get_commands()
    return templates.TemplateResponse("index.html", context={"request": request, "commands": commands})


@app.get("/lwa")
def get_lwa(key):
    if key == RELAY_KEY:
        dd2 = {"read_mjd": time.Time.now().mjd}
        dd2.update(dd["lwa"])
        return dd2
    else:
        return "Bad key"


@app.put("/lwa")
def set_lwa(command: relay_db.Command, key: str):
    if key == RELAY_KEY:
        dd['lwa'] = {"command": command.command, "command_mjd": command.command_mjd,
                     "args": command.args}
        relay_db.set_command(command)
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
def set_dsa(command: relay_db.Command, key: str):
    if key == RELAY_KEY:
        dd['dsa'] = {"command": command.command, "command_mjd": command.command_mjd,
                     "args": command.args}
        relay_db.set_command(command)

        if command.command == 'observation' and cl is not None:
            if "trigname" in command.args:
                message = f'DSA-110 event {command.args["trigname"]} received'
            else:
                message = f'DSA-110 event received'
            res = cl.chat_postMessage(channel='#alert-driven-astro', text=message)

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
def set_ligo(command: relay_db.Command, key: str):
    if key == RELAY_KEY:
        dd["ligo"] = {"command": command.command, "command_mjd": command.command_mjd,
                      "args": command.args}
        relay_db.set_command(command)

        if command.command == 'observation' and cl is not None:
            if "GraceID" in command.args:
                message = f'LIGO event {command.args["GraceID"]} received'  # more verbose logging by receiver script
            else:
                message = f'LIGO event received'
            res = cl.chat_postMessage(channel='#alert-driven-astro', text=message)

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
def set_chime(command: relay_db.Command, key: str):
    if key == RELAY_KEY:
        dd['chime'] = {"command": command.command, "command_mjd": command.command_mjd,
                       "args": command.args}
        relay_db.set_command(command)

        if command.command == 'observation' and cl is not None:
            if "event_no" in command.args:
                message = f'CHIME/FRB event {command.args["event_no"]} received'  # more detail may be posted by reader client
            else:
                message = f'CHIME/FRB event received: {command.args}'
            res = cl.chat_postMessage(channel='#alert-driven-astro', text=message)

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
def set_gcn(command: relay_db.Command, key: str):
    if key == RELAY_KEY:
        dd['gcn'] = {"command": command.command, "command_mjd": command.command_mjd,
                       "args": command.args}
        relay_db.set_command(command)

        if command.command == 'observation' and cl is not None:
            message = f'GCN event with args: {command.args}'  # TODO: parse this for clarity
            res = cl.chat_postMessage(channel='#alert-driven-astro', text=message)

        return f"Set GCN event: {command.command} with {command.args}"
    else:
        return "Bad key"
