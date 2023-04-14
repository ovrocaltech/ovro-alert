from time import sleep
from astropy.time import Time
from ovro_alert.alert_client import AlertClient
from mnc import control

class LWAAlertClient(AlertClient):
    def __init__(self, pipelines):
	super().__init__('lwa')
        self.pipelines = [p for p in pipelines if p.pipeline_id in [2, 3]]
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
	path_map = {2: '/data0/', 3: '/data1/'}
	for pipeline in self.pipelines:
		if pipeline.pipeline_id in path_map:
        		path = path_map[pipeline.pipeline_id]
            		pipeline.triggered_dump.trigger(ntime_per_file=self.ntime_per_file, nfile=self.nfile, dump_path=path)


    def powerbeam(self):
        """ Observe with power beam
        """
        pass


if __name__ == '__main__':
    con = control.Controller()
    pipelines = con.pipelines
    client = LWAAlertClient(pipelines)
    client.ntime_per_file = 24000
    client.nfile = 1
    client.poll(loop=5)

