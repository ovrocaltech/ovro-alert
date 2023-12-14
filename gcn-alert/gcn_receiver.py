#!/usr/bin/env python
import gcn
from ovro_alert import alert_client
import voeventparse

gc = alert_client.AlertClient('gcn')

# Define your custom handler here.
@gcn.include_notice_types(
    gcn.notice_types.SWIFT_BAT_GRB_POS_ACK,
    gcn.notice_types.SWIFT_BAT_MONITOR,  # test
    gcn.notice_types.FERMI_GBM_FLT_POS,  # test
    )
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
    print(f'Toplevel params: {toplevel_params.keys()}')
    print(f'Grouped params: {grouped_params.keys()}')

    # send it
    args = {'duration': 1800, 'position': f'{ra},{dec},{radius}'}
    role = ve.attrib['role']
    gc.set(role, args)

# Listen for VOEvents until killed with Control-C.
gcn.listen(handler=handler)
