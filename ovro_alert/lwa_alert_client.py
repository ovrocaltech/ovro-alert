from time import sleep
from astropy.time import Time
from ovro_alert.alert_client import AlertClient
from mnc import control
import threading


delay = lambda dm, f1, f2: 4.149 * 1e3 * dm * (f2 ** (-2) - f1 ** (-2))

class LWAAlertClient(AlertClient):
    def __init__(self, con):
        super().__init__('lwa')
        self.con = con
        self.pipelines = [p for p in con.pipelines if p.pipeline_id in [2, 3]]

    def poll(self, loop=5):
        """ Poll the relay API for commands.
        """

        ddc0 = self.get(route='chime')
        ddl0 = self.get(route='ligo')
        while True:
            mjd = Time.now().mjd
            ddc = self.get(route='chime')
            ddl = self.get(route='ligo')
            print(".", end="")

            if ddc["command_mjd"] != ddc0["command_mjd"]:
                ddc0 = ddc.copy()

                if ddc["command"] == "observation":   # chime/ligo have command="observation" or "test"
                    print("Received CHIME event")
                    assert all(key in ddc["args"] for key in ["dm", "toa", "position"])
                    if ddc["args"]["known"]:
                        # TODO: check for sources we want to observe (e.g., by name or properties)
                        self.powerbeam(ddc["args"])
                elif ddc["command"] == "test":
                    print("Received CHIME test")

            elif ddl["command_mjd"] != ddl0["command_mjd"]:
                ddl0 = ddl.copy()

                if ddl["command"] == "observation":   # chime/ligo have command="observation" or "test"
                    print("Received LIGO event")
                    # TODO: check for sources we want to observe (e.g., by name or properties)
                    self.trigger()
                elif ddl["command"] == "test":
                    print("Received LIGO test")
                    if 'nsamp' in ddl:
                        self.trigger(nsamp=ddl['nsamp'])
            else:
                sleep(loop)

    def trigger(self, nsamp=None):
        """ Trigger voltage dump
        This method assumes it should trigger and figures out parameters from input.
        """

        # TODO: select on -- is up? HasNS? Terrestrial?

        path_map = {2: '/data0/', 3: '/data1/'}
        if nsamp is not None:
            dt = nsamp/24000
        else:
            dt = delay(1000, 1e9, 50)

        # TODO: check disk space: 2.7 TB per DM=1000 event (at 50 MHz)
        # TODO: calculate length from input dict
        ntime_per_file = int(dt*24000)   # 1/24000=41.666 microsec per sample
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
        d0 = delay(dm, 1e9, 50)

# slow way
#        con.configure_xengine('dr3', calibratebeams=True, full=True)  # get beam control handlers
#        thread = threading.Thread(target=self.con.control_bf, kwargs={'num': 1, 'targetname': (RA, Dec), 'track': True})
#        thread.start()

	#Observe for the delay plus a bit more (duration is in ms)
        self.con.start_dr(recorders=['dr3'], duration=(d0+10)*1e3, time_avg=128)
        con.configure_xengine('dr3', calibratebeams=False, full=False)  # get beam control handlers
#        self.con.control_bf(num=3, targetname=(RA, Dec), track=True)
        thread = threading.Thread(target=self.con.control_bf, kwargs={'num': 3, 'targetname': (RA, Dec), 'track': True})
        thread.start()
        thread.join()

if __name__ == '__main__':
    con = control.Controller()
    client = LWAAlertClient(con)
    client.poll(loop=5)

