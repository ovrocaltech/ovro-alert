#!/usr/bin/env python
import gcn
from ovro_alert import alert_client

gc = alert_client.AlertClient('gcn')

# Define your custom handler here.
@gcn.include_notice_types(
    gcn.notice_types.SWIFT_BAT_GRB_POS_ACK
    )
def handler(payload, root):
    # Look up right ascension, declination, and error radius fields.
    pos2d = root.find('.//{*}Position2D')
    ra = float(pos2d.find('.//{*}C1').text)
    dec = float(pos2d.find('.//{*}C2').text)
    radius = float(pos2d.find('.//{*}Error2Radius').text)

    # Print.
    print('ra = {:g}, dec={:g}, radius={:g}'.format(ra, dec, radius))
    args = {'duration': 1800, 'position': f'{ra},{dec},{radius}'}
    gc.set('observation', args)

# Listen for VOEvents until killed with Control-C.
gcn.listen(handler=handler)
