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

    def poll(self, loop=5):
        """ Poll the relay API for commands.
        """

        ddc0 = self.get('chime')
        ddl0 = self.get('ligo')
        while True:
            mjd = Time.now().mjd
            ddc = self.get('chime')
            ddl = self.get('ligo')
            print(".", end="")

            if ddc["command_mjd"] != ddc0["command_mjd"]:
                ddc0 = ddc.copy()

                if ddc["command"] == "observation":   # chime/ligo have command="observation" or "test"
                    print("Receive CHIME event")
                    assert all(key in ddc["args"] for key in ["dm", "toa", "position"])
                    if "known" in ddc["args"]:
                        # TODO: check for sources we want to observe (e.g., by name or properties)
                        self.powerbeam(ddc["args"])
                elif ddc["command"] == "test":
                    print("Received CHIME test")

            elif ddl["command_mjd"] != ddl0["command_mjd"]:
                ddl0 = ddl.copy()

                if ddl["command"] == "observation":   # chime/ligo have command="observation" or "test"
                    print("Received LIGO event")
                    # TODO: check for sources we want to observe (e.g., by name or properties)
                    self.trigger(ddl)
                elif ddl["command"] == "test":
                    print("Received LIGO test")

            else:
                sleep(loop)
                continue

    def trigger(self, dd):
        """ Trigger voltage dump
        This method assumes it should trigger and figures out parameters from input.
        """

        path_map = {2: '/data0/', 3: '/data1/'}

        # TODO: calculate length from input dict
        ntime_per_file = 24000
        nfile = 1

        for pipeline in self.pipelines:
            if pipeline.pipeline_id in path_map:
                path = path_map[pipeline.pipeline_id]
                pipeline.triggered_dump.trigger(ntime_per_file=ntime_per_file, nfile=nfile, dump_path=path)
        print(f'Triggered {len(self.pipelines)} pipelines')

    def powerbeam(self, dd):
        """ Observe with power beam
        This method assumes it should run beamformer observation and figures out parameters from input.
        """

        position = dd["position"].split(",")  # Parse the position to get ra and dec

        RA = float(position[0])
        Dec = float(position[1])
        dm = dd["dm"]
        toa = dd["toa"]
        max_delay = 4.149*1e3 * dm * 12**(-2) # maximum delay for a specific value of DM at the lowest LWA frequency (12 MHz) in seconds

        con.configure_xengine('dr2', calibratebeams=False, full=False)  # get beam control handlers
# slow way
#        con.configure_xengine('dr2', calibratebeams=True, full=True)  # get beam control handlers
#        thread = threading.Thread(target=self.con.control_bf, kwargs={'num': 1, 'targetname': (RA, Dec), 'track': True})
#        thread.start()

	#Observe for the duration equal to maximum delay (duration is in ms)
        self.con.start_dr(recorders=['dr2'], duration=max_delay*1e3, time_avg=128)

	# Sleep for the duration + 10 sec, then stop the recording and the xengine
        sleep(max_delay + 10)
        self.con.stop_dr(recorders=['dr2'])
#        con.stop_xengine

if __name__ == '__main__':
    con = control.Controller()
    client = LWAAlertClient(con)
    client.poll(loop=5)

