import gcn
import datetime
from ovro_alert import alert_client


lwac = alert_client.AlertClient('lwa')
ligoc = alert_client.AlertClient('ligo')

# Define thresholds
FAR_THRESH = 3.17e-9 # 1 event per decade
ASTRO_PROB_THRESH = 0.9 # not Terrestrial
HAS_NS_THRESH = 0.9 # HasNS probability
BNS_NSBH_THRESH = 0 # Either BNS or NSBH probability


# Function to call every time a GCN is received.
# Run only for notices of type
# LVC_EARLY_WARNING, LVC_PRELIMINARY, LVC_INITIAL, LVC_UPDATE, or LVC_RETRACTION.

@gcn.handlers.include_notice_types(
    gcn.notice_types.LVC_EARLY_WARNING,  # <-- new notice type here
    gcn.notice_types.LVC_PRELIMINARY,
    gcn.notice_types.LVC_INITIAL,
    gcn.notice_types.LVC_UPDATE,
    gcn.notice_types.LVC_RETRACTION)

def process_gcn(payload, root, write=False):
    
    # Read all of the VOEvent parameters from the "What" section.
    params = {elem.attrib['name']:
              elem.attrib['value']
              for elem in root.iterfind('.//Param')}
    
    
    # Respond to both 'test' in case of EarlyWarning alert or 'observation' 
    condition1 = root.attrib['role'] == 'test' and params['AlertType'] == 'EarlyWarning'
    condition2 = root.attrib['role'] == 'test' # IMPORTANT! for real observations set to 'observation' 
    if not (condition1 or condition2):
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

        # Open a new file in write mode
        if write:
            file_name = params['GraceID']+'_ligo.txt'
            with open(file_name, "w") as f:
                # Write the text "Trigger the buffer,"
                f.write("Trigger the buffer,\n")

                # Write the current time in UTC in a human-readable format
                f.write("Created at (UTC): " + now.strftime("%Y-%m-%d %H:%M:%S"))

        # Send to relay
        print('sending to lwa relay server as "trigger"')
        lwac.set("trigger", args={'FAR': params['FAR'], 'BNS': params['BNS']})
        print(f'sending to ligo relay server with role {root.attrib["role"]}')
        ligoc.set(root.attrib['role'], args={'FAR': params['FAR'], 'BNS': params['BNS']})
gcn.listen(handler=process_gcn)







