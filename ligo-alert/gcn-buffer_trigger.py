import gcn
import datetime
from ovro_alert import alert_client
import ligo.skymap.io
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


ligoc = alert_client.AlertClient('ligo')

# Define thresholds
FAR_THRESH = 3.17e-9 # 1 event per decade
ASTRO_PROB_THRESH = 0.9 # not Terrestrial
HAS_NS_THRESH = 0.9 # HasNS probability
BNS_NSBH_THRESH = 0 # Either BNS or NSBH probability

slack_token = "your-slack-token"  # use your actual Slack token
slack_channel = "#your-channel"  # use your actual Slack channel
client = WebClient(token=slack_token)
send_to_slack = False  # global variable to control whether to send to Slack

def post_to_slack(channel, message):
    """Post a message to a Slack channel."""
    try:
        response = client.chat_postMessage(channel=channel, text=message)
    except SlackApiError as e:
        print(f"Error sending to Slack: {e.response['error']}")

# Function to call every time a GCN is received.
# Run only for notices of type
# LVC_EARLY_WARNING, LVC_PRELIMINARY, LVC_INITIAL, LVC_UPDATE, or LVC_RETRACTION.

@gcn.handlers.include_notice_types(
    gcn.notice_types.LVC_EARLY_WARNING,  # <-- new notice type here
    gcn.notice_types.LVC_PRELIMINARY,
    gcn.notice_types.LVC_INITIAL,
    gcn.notice_types.LVC_UPDATE,
    gcn.notice_types.LVC_RETRACTION)

def process_gcn(payload, root, write=True):
    
    # Read all of the VOEvent parameters from the "What" section.
    params = {elem.attrib['name']:
              elem.attrib['value']
              for elem in root.iterfind('.//Param')}
    
    
    # Respond to both 'test' in case of EarlyWarning alert or 'observation' 
    condition1 = root.attrib['role'] == 'test' and params['AlertType'] == 'EarlyWarning'
    condition2 = root.attrib['role'] == 'observation' # IMPORTANT! for real observations set to 'observation'
    condition3 = root.attrib['role'] == 'test' # For testing purposes
    if not (condition1 or condition2 or condition3):
        return

    # If event is retracted, print it.
    if params['AlertType'] == 'Retraction':
        print(params['GraceID'], 'was retracted')
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
    if trig_cond1 and trig_cond2 and trig_cond3 and trig_cond4:
        
        # Create a datetime object with the current time in UTC
        now = datetime.datetime.utcnow()

        # Send to relay
        # for EarlyWarning type of Alerts
        if condition1:
            print(f'sending EarlyWarning type of alert to ligo relay server with role observation')

            ligoc.set("observation", args={'FAR': params['FAR'], 'BNS': params['BNS'],
                                                 'HasNS': params['HasNS'], 'Terrestrial': params['Terrestrial']})
            # Send to slack if necessary
            if send_to_slack:
                # Prepare the message to be sent to Slack
                slack_message = f"GraceID: {params['GraceID']}, AlertType: {params['AlertType']}" \
                                f", Parameters: FAR {params['FAR']}, BNS {params['BNS']}, HasNS {params['HasNS']}" \
                                f", Terrestrial {params['Terrestrial']}. Message sent at (UTC): {now.strftime('%Y-%m-%d %H:%M:%S')}."
                post_to_slack(slack_channel, slack_message)


        # in case of real observation
        elif condition2:

            print(f'sending to ligo relay server with role {root.attrib["role"]}')

            ligoc.set(root.attrib['role'], args={'FAR': params['FAR'], 'BNS': params['BNS'],
                                                     'HasNS': params['HasNS'], 'Terrestrial': params['Terrestrial']})
            # Send to slack if necessary
            if send_to_slack:
                # Prepare the message to be sent to Slack
                slack_message = f"GraceID: {params['GraceID']}, AlertType: {params['AlertType']}" \
                                f", Parameters: FAR {params['FAR']}, BNS {params['BNS']}, HasNS {params['HasNS']}" \
                                f", Terrestrial {params['Terrestrial']}. Message sent at (UTC): {now.strftime('%Y-%m-%d %H:%M:%S')}."
                post_to_slack(slack_channel, slack_message)


        # for testing, send with nsamp parameter
        elif condition3:

            print(f'sending to ligo relay server with role {root.attrib["role"]}')

            ligoc.set(root.attrib['role'], args={'FAR': params['FAR'], 'BNS': params['BNS'],
                                                 'HasNS': params['HasNS'], 'Terrestrial': params['Terrestrial'],
                                                 'nsamp': 24000})


        # Save bayestar map
        if 'skymap_fits' in params:
            # Read the HEALPix sky map and the FITS header.
            skymap, _ = ligo.skymap.io.read_sky_map(params['skymap_fits'])

            # Write the skymap to a file
            skymap_file_name = params['GraceID'] + '_skymap.fits'
            ligo.skymap.io.write_sky_map(skymap_file_name, skymap, overwrite=True)

            # TODO: do we need to select on whether target is up?

    else:
        print(f'Event did not pass selection: FAR {params["FAR"]}, BNS {params["BNS"]}, Terrestrial {params["Terrestrial"]}.')
            
gcn.listen(handler=process_gcn)
