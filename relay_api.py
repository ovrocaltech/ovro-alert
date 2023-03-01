from typing import Union

from fastapi import FastAPI
from pydantic import BaseModel
from astropy import time

app = FastAPI()

dd = {"dsa": None, "lwa": None}

class Command(BaseModel):
    command: str


@app.get("/")
def read_root():
    return "ovro-alert api root"


@app.get("/dsa")
def read_dsa():
    time_mjd = time.Time.now().mjd
    return {"time_read": time_mjd, "project": "dsa", "command": dd["dsa"]}


@app.get("/lwa")
def read_lwa():
    time_mjd = time.Time.now().mjd
    return {"time_read": time_mjd, "project": "lwa", "command": dd["lwa"]}


@app.put("/dsa")
def set_dsa(command: Command):
    dd['dsa'] = command.command
    return {"dsa command": command.command}


@app.put("/lwa")
def set_lwa(command: Command):
    dd['lwa'] = command.command
    return {"lwa command": command.command}
