import gcn
import datetime
from ovro_alert import alert_client
#import ligo.skymap.io
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from os import environ
import sys
import logging

logger = logging.getLogger(__name__)
logHandler = logging.StreamHandler(sys.stdout)
logFormat = logging.Formatter('%(asctime)s [%(levelname)-8s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logHandler.setFormatter(logFormat)
logger.addHandler(logHandler)
logger.setLevel(logging.DEBUG)


if "SLACK_TOKEN_CR" in environ:
    slack_token = environ["SLACK_TOKEN_CR"]
    slack_channel = "#alert-driven-astro"  # use your actual Slack channel (TBD)
    client = WebClient(token=slack_token)
    logger.debug("Created slack client")
else:
    logger.debug("Created slack client")

send_to_slack = True  # global variable to control whether to send to Slack

ligoc = alert_client.AlertClient('ligo')

# Define thresholds
FAR_THRESH = 3.17e-9 # 1 event per decade
ASTRO_PROB_THRESH = 0.9 # not Terrestrial
HAS_NS_THRESH = 0.5 # HasNS probability
BNS_NSBH_THRESH = 0 # Either BNS or NSBH probability



def post_to_slack(channel, message):
    """Post a message to a Slack channel."""
    try:
        response = client.chat_postMessage(channel=channel, text=message)
    except SlackApiError as e:
        logger.error(f"Error sending to Slack: {e.response['error']}")

# Function to call every time a GCN is received.
# Run only for notices of type
# LVC_EARLY_WARNING, LVC_PRELIMINARY, LVC_INITIAL, LVC_UPDATE, or LVC_RETRACTION.

@gcn.handlers.include_notice_types(
    gcn.notice_types.LVC_EARLY_WARNING,  # <-- new notice type here
    gcn.notice_types.LVC_PRELIMINARY,
    gcn.notice_types.LVC_INITIAL,
#    gcn.notice_types.LVC_UPDATE,
    gcn.notice_types.LVC_RETRACTION)

def process_gcn(payload, root, write=True):
    
    # Read all of the VOEvent parameters from the "What" section.
    params = {elem.attrib['name']:
              elem.attrib['value']
              for elem in root.iterfind('.//Param')}

    
    # Respond to both 'test' in case of EarlyWarning alert or 'observation' 
    condition1 = root.attrib['role'] == 'test' and params['AlertType'] == 'EarlyWarning'
    condition2 = root.attrib['role'] == 'observation' # IMPORTANT! for real observations set to 'observation'
    if not (condition1 or condition2):
        logger.debug("Received test event")
        return

    # If event is retracted, print it.
    if params['AlertType'] == 'Retraction':
        logger.info(params['GraceID'], 'was retracted')
        return

    # Respond only to 'CBC' events. Change 'CBC' to 'Burst'
    # to respond to only unmodeled burst events.
    if params['Group'] != 'CBC':
        return
    
    # Define trigger conditions
    trig_cond1 = float(params['FAR']) <= FAR_THRESH
    trig_cond2 = (1 - float(params['Terrestrial'])) >= ASTRO_PROB_THRESH
    trig_cond3 = float(params['HasNS']) >= HAS_NS_THRESH
    trig_cond4 = float(params['BNS']) + float(params['NSBH']) > BNS_NSBH_THRESH
    
    # Trigger the buffer if all conditions above are met
#    if params['AlertType'] in ['Initial', 'Preliminary']:    # trigger often
    logger.debug(f"Trigger criteria: {trig_cond1}, {trig_cond2}, {trig_cond3}, {trig_cond4}")
    if trig_cond1 and trig_cond2 and trig_cond3 and trig_cond4:
        
        # Create a datetime object with the current time in UTC
        now = datetime.datetime.utcnow()

        # Send to relay
        # for EarlyWarning type of Alerts
        role = "observation" if condition1 else root.attrib["role"]
        msg_start = "sending EarlyWarning type of alert" if condition1 else "sending alert"

        logger.info(f'{msg_start} to ligo relay server with role {role}')
        ligoc.set(role, args={'FAR': params['FAR'], 'BNS': params['BNS'],
                              'HasNS': params['HasNS'], 'Terrestrial': params['Terrestrial'],
                              'GraceID': params['GraceID'], 'AlertType': params['AlertType']})

        message = f"LIGO {params['AlertType']} alert with GraceID: {params['GraceID']}" \
                        f", Parameters: FAR {params['FAR']}, BNS {params['BNS']}, HasNS {params['HasNS']}" \
                        f", Terrestrial {params['Terrestrial']}. Message sent at (UTC): {now.strftime('%Y-%m-%d %H:%M:%S')}."
        logger.info(message)
        if send_to_slack:
            post_to_slack(slack_channel, message)


        # Save bayestar map
        if ('skymap_fits' in params) and False:  # turn this off for now
            # Read the HEALPix sky map and the FITS header.
            skymap, _ = ligo.skymap.io.read_sky_map(params['skymap_fits'])

            # Write the skymap to a file
            skymap_file_name = params['GraceID'] + '_skymap.fits'
            ligo.skymap.io.write_sky_map(skymap_file_name, skymap, overwrite=True)

            # TODO: do we need to select on whether target is up?

    else:
        logger.info(f'{params["AlertType"]} event {params["GraceID"]} did not pass selection: FAR {params["FAR"]}, BNS {params["BNS"]}, Terrestrial {params["Terrestrial"]}.')
            
gcn.listen(handler=process_gcn)
