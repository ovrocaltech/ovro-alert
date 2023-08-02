from time import sleep

from ovro_alert.alert_client import AlertClient

import pandas as pd

import json

from astropy import time
from astropy.coordinates import SkyCoord
import astropy.units as u

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

import sys
from os import environ

if "SLACK_TOKEN_DSA" in environ:
    cl = WebClient(token=environ["SLACK_TOKEN_DSA"])

class DSAAlertClient(AlertClient):

    def __init__(self, file_path):
        super().__init__('chime')
        with open(file_path, 'r') as json_file:
            self.frbs = json.load(json_file)

    def compare_voevent_with_frbs(self, voevent_dm, voevent_ra, voevent_dec):
        matched_frbs = []
        
        voevent_coord = SkyCoord(ra=voevent_ra*u.deg, dec=voevent_dec*u.deg)
        
        for frb in self.frbs:
            frb_dm = frb['fitburst_dm']
            frb_ra = frb['ra']
            frb_dec = frb['dec']
            
            frb_coord = SkyCoord(ra=frb_ra*u.deg, dec=frb_dec*u.deg)
            
            # Define a threshold for DM and angular distance
            dm_threshold = 5.0
            angular_distance_threshold = 0.1 * u.deg
            
            # Compare DM and angular distance
            dm_difference = abs(voevent_dm - frb_dm)
            angular_distance = voevent_coord.separation(frb_coord)
            
            if dm_difference <= dm_threshold and angular_distance <= angular_distance_threshold:
                matched_frbs.append(frb)
        
        return matched_frbs

    def poll(self, loop=5):
        """ Poll the relay API for commands.
        """
        dd = self.get()
        while True:
            mjd = time.Time.now().mjd
            dd2 = self.get()
            if dd2["command_mjd"] != dd["command_mjd"]:
                dd = dd2.copy()
                #print(f"DD ARGS: {dd['args']}")
                event_no = dd['args'].get('event_no', None)
                voe_dm = dd['args']['dm']
                voe_ra, voe_dec, voe_err = dd['args']['position'].split(',')
                voe_ra = float(voe_ra)
                voe_dec = float(voe_dec)
                voe_err = float(voe_err)
                matched_frbs = self.compare_voevent_with_frbs(voe_dm, voe_ra, voe_dec)

                repeater_of = []
                event_no = []
                for frb in matched_frbs:
                    repeater_of.append(frb['repeater_of'])
                # If repeater association is confirmed, post to slack
                if len(repeater_of) > 1:
                    message = f"CHIME/FRB event {event_no}: \n is associated with repeater {repeater_of[1]}"
                    try:
                        response = cl.chat_postMessage(channel="#candidates", text=message, icon_emoji = ":zap:")
                    except Exception as e: # SlackApiError as e:
                        print(e)
                else:
                    print(f"{event_no} not matched to known repeater")

            else:
                sleep(loop)
                continue
        
    def slew(self):
        """ Slew to new elevation
        """

        pass

if __name__ == '__main__':
    file_path = sys.argv[1]
    client = DSAAlertClient(file_path)
    client.poll(loop=5)
