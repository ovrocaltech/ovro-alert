#!/usr/bin/env python
import gcn
from ovro_alert import alert_client
import voeventparse

gc = alert_client.AlertClient('gcn')

# Define your custom handler here.
@gcn.include_notice_types(
    gcn.notice_types.SWIFT_BAT_GRB_POS_ACK,
    )    # maybe also SWIFT_SC_SLEW to get Wait_Time to see if Swift is slewing promptly to event
def handler(payload, root):
    # parse
    ve = voeventparse.loads(payload)

    # get values
    pos = voeventparse.convenience.get_event_position(ve)
    ra = pos.ra
    dec = pos.dec
    radius = pos.err
    dt = voeventparse.convenience.get_event_time_as_utc(ve)
    toplevel_params = voeventparse.get_toplevel_params(ve)
    grouped_params = voeventparse.convenience.get_grouped_params(ve)
    author = ve.Who.Author.shortName

    # Print.
    print(f'Event from {author} at {dt.isoformat()}: RA, Dec = ({ra}, {dec}, radius={radius}.')
    print(f'Bkg_dur: {toplevel_params["Bkg_Dur"]}. Rate_signif: {toplevel_params["Rate_Signif"]}.')

    # send it
    args = {'duration': 1800, 'position': f'{ra},{dec},{radius}'}
    role = ve.attrib['role']
    gc.set(role, args)

# Listen for VOEvents until killed with Control-C.
gcn.listen(handler=handler)
