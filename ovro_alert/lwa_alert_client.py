from time import sleep
from astropy.time import Time
from ovro_alert.alert_client import AlertClient
from mnc import control
import threading


class LWAAlertClient(AlertClient):
    def __init__(self, con):
        super().__init__('lwa')
        self.con = con
        self.pipelines = [p for p in con.pipelines if p.pipeline_id in [2, 3]]
        self.ntime_per_file = 1024
        self.nfile = 1

    def poll(self, loop=5):
        """ Poll the relay API for commands.
        """
        dd = self.get()
        while True:
            mjd = Time.now().mjd
            dd2 = self.get()
            print('.', end='')
            if dd2["command_mjd"] != dd["command_mjd"]:
                dd = dd2.copy()
                if dd2["command"] == "trigger":
                    self.trigger()
                elif dd2["command"] == "powerbeam":
                    assert all(key in dd2["args"] for key in ["dm", "toa", "position"])
                    self.powerbeam(dd2["args"])
                else:
                    print(f'command {dd2["command"]} not recognized')
            else:
                print(f'no updated time: {dd2["command_mjd"]} {dd["command_mjd"]}')
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

    def powerbeam(self, dd2):
        """ Observe with power beam
        """

        position = dd2["position"].split(",")  # Parse the position to get ra and dec

        RA = float(position[0])
        Dec = float(position[1])
        dm = dd2["dm"]
        toa = dd2["toa"]
        max_delay = 4.149*1e3 * dm * 12**(-2) # maximum delay for a specific value of DM at the lowest LWA frequency (12 MHz) in seconds

        thread = threading.Thread(target=self.con.control_bf, kwargs={'num': 1, 'targetname': (RA, Dec), 'track': True})
        thread.start()

	#Observe for the duration equal to maximum delay (duration is in ms)
        self.con.start_dr(recorders=['dr1'], duration=max_delay*1e3, time_avg=128)

	# Sleep for the duration + 10 sec, then stop the recording and the xengine
        sleep(max_delay + 10)
        self.con.stop_dr(recorders=['dr1'])


if __name__ == '__main__':
    con = control.Controller()
    client = LWAAlertClient(con)
    client.ntime_per_file = 24000
    client.nfile = 1
    client.poll(loop=5)

