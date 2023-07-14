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
        self.con.configure_xengine(recorders=['dr3'], full=False, calibratebeams=True)

    def poll(self, loop=5):
        """ Poll the relay API for commands.
        """

        ddc0 = self.get(route='chime')
        ddl0 = self.get(route='ligo')
        ddg0 = self.get(route='gcn')
        while True:
            mjd = Time.now().mjd
            ddc = self.get(route='chime')
            ddl = self.get(route='ligo')
            ddg = self.get(route='gcn')
            print(".", end="")

            # TODO: validate ddc and ddl have correct fields (and maybe reject malicious content?)

            if ddc["command_mjd"] != ddc0["command_mjd"]:
                ddc0 = ddc.copy()

                if ddc["command"] == "observation":   # chime/ligo have command="observation" or "test"
                    print("Received CHIME event")
                    assert all(key in ddc["args"] for key in ["dm", "position"])
#                    if ddc["args"]["known"]:   # TODO: check for sources we want to observe (e.g., by name or properties)
                    self.powerbeam(ddc["args"])
                elif ddc["command"] == "test":
                    print("Received CHIME test")
            elif ddg["command_mjd"] != ddg0["command_mjd"]:
                ddg0 = ddg.copy()

                if ddg["command"] == "observation":   # TODO; check on types
                    print("Received GCN event. Not observing yet")  # TODO: test
                    assert all(key in ddg["args"] for key in ["duration", "position"])
#                    self.powerbeam(ddg["args"])
                elif ddg["command"] == "test":
                    print("Received GCN test")

            elif ddl["command_mjd"] != ddl0["command_mjd"]:
                ddl0 = ddl.copy()

                if ddl["command"] == "observation":   # chime/ligo have command="observation" or "test"
                    print("Received LIGO event")
                    nsamp = ddl["args"]["nsamp"] if "nsamp" in ddl["args"] else None
                    self.trigger(nsamp=nsamp)
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

        path_map = {2: '/data0/', 3: '/data1/'}
        if nsamp is not None:
            dt = nsamp/24000
        else:
            dt = delay(1000, 1e9, 50)

        # TODO: check disk space: 2.7 TB per DM=1000 event (at 50 MHz)
        # TODO: calculate length from input dict

        ntime_per_file = 1000000   # compile time in x-engine?
        ntime = int(dt*24000)   # 1/24000=41.666 microsec per sample
        nfile = max(1, ntime//ntime_per_file)  # trigger at least one file

        for pipeline in self.pipelines:
            if pipeline.pipeline_id in path_map:
                path = path_map[pipeline.pipeline_id]
                pipeline.triggered_dump.trigger(ntime_per_file=ntime_per_file, nfile=nfile, dump_path=path)
        print(f'Triggered {len(self.pipelines)} pipelines to record {nfile} files with {ntime_per_file} samples each.')

    def powerbeam(self, dd):
        """ Observe with power beam
        This method assumes it should run beamformer observation and figures out parameters from input.
        keys in dd: 'dm' or 'duration' and 'position'.
        """

        position = dd["position"].split(",")  # Parse the position to get ra and dec

        RAd = float(position[0])
        RAh = RAd/15
        Dec = float(position[1])
        toa = dd["toa"]  # maybe useful for logging?
        if 'duration' in dd:
            d0 = float(dd['duration'])
        else:
            assert 'dm' in dd
            dm = float(dd["dm"])
            d0 = delay(dm, 1e9, 50) + 10  # Observe for the delay plus a bit more

        self.con.start_dr(recorders=['dr3'], duration=d0*1e3, time_avg=128) # (duration is in ms)
        self.con.configure_xengine('dr3', calibratebeams=False, full=False)  # get beam control handlers
#        thread = threading.Thread(target=self.con.control_bf, kwargs={'num': 3, 'coord': (RA, Dec), 'track': True, 'duration': d0})
#        thread.start()
#        thread.join()
        self.con.control_bf(num=3, coord=(RAh, Dec), track=True, duration=d0)  # RA must be in decimal hours

if __name__ == '__main__':
#    xhosts = [f'lxdlwagpu0{i}' for i in [3,4,5,6,7,8]]  # remove bad gpus
    con = control.Controller()  # xhosts=xhosts)
    client = LWAAlertClient(con)
    client.poll(loop=5)

