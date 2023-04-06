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



