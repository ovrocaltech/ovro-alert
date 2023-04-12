from time import sleep
from astropy.time import Time
from ovro_alert.alert_client import AlertClient


class LWAAlertClient(AlertClient):
    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.ntime_per_file = 1024
        self.nfile = 1

    def poll(self, loop=5):
        """ Poll the relay API for commands.
        """
        dd = self.get()
        while True:
            mjd = Time.now().mjd
            dd2 = self.get()
            if dd2["command_mjd"] != dd["command_mjd"]:
                dd = dd2.copy()
                if dd2["command"] == "trigger":
                    self.trigger()
            else:
                sleep(loop)
                continue

    def trigger(self):
        """ Trigger voltage dump
        """
        self.pipeline.triggered_dump.trigger(ntime_per_file=self.ntime_per_file, nfile=self.nfile, dump_path='/data0/')

    def powerbeam(self):
        """ Observe with power beam
        """
        pass


if __name__ == '__main__':
    xhosts = ['lxdlwagpu02']
    con = control.Controller('proj/lwa-shell/mnc_python/config/lwa_config_calim.yaml', xhosts=xhosts)
    pipelines = con.pipelines
    p = pipelines[0]
    client = LWAAlertClient(p)
    client.ntime_per_file = 24000
    client.nfile = 1
    client.poll(loop=5)

