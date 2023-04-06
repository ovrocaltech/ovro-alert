from time import sleep
from astropy.time import Time
from ovro_alert.lwa_alert_client import LWAAlertClient
from mnc import control


xhosts = ['lxdlwagpu02']
con = control.Controller('proj/lwa-shell/mnc_python/config/lwa_config_calim.yaml', xhosts=xhosts)
pipelines = con.pipelines
p = pipelines[0]
client = LWAAlertClient(p)
client.ntime_per_file = 24000
client.nfile = 1
client.poll(loop=5)
