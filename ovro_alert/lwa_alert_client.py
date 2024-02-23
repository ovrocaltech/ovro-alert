import sys
import logging
from time import sleep
from astropy.time import Time
from ovro_alert.alert_client import AlertClient
from mnc import control
import threading
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from os import environ


logger = logging.getLogger(__name__)
logHandler = logging.StreamHandler(sys.stdout)
logFormat = logging.Formatter('%(asctime)s [%(levelname)-8s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logHandler.setFormatter(logFormat)
logger.addHandler(logHandler)
logger.setLevel(logging.DEBUG)

if "SLACK_TOKEN_LWA" in environ:
    cl = WebClient(token=environ["SLACK_TOKEN_LWA"])
else:
    cl = None
    logging.warning("No SLACK_TOKEN_LWA found. No slack updates.")
    
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
                    logger.info("Received CHIME event")
                    if not all(key in ddc["args"] for key in ["dm", "position"]):
                        logger.warning(f"CHIME args ({ddc['args']}) do not include 'dm' and 'position'. Skipping...")
                        continue
#                    if ddc["args"]["known"]:   # TODO: check for sources we want to observe (e.g., by name or properties)
                    if cl is not None:
                        response = cl.chat_postMessage(channel="#observing",
                                                       text=f"Starting power beam on CHIME event {ddc['args']['event_no']} with DM={ddc['args']['dm']}",
                                                       icon_emoji = ":robot_face::")
                    self.powerbeam(ddc["args"])
#                    self.submit_voltagebeam(ddc["args"])
                elif ddc["command"] == "test":
                    logger.info("Received CHIME test")
            elif ddg["command_mjd"] != ddg0["command_mjd"]:
                ddg0 = ddg.copy()

                if ddg["command"] == "observation":   # TODO; check on types
                    logger.info("Received GCN event. Not observing yet")  # TODO: test
                    if not all(key in ddg["args"] for key in ["duration", "position"]):
                        logger.warning(f"GCN args ({ddg['args']}) do not include 'duration' and 'position'. Skipping...")
                        continue
# TO DO: decide on respnonse
#                    self.powerbeam(ddg["args"])
                elif ddg["command"] == "test":
                    logger.info("Received GCN test")

            elif ddl["command_mjd"] != ddl0["command_mjd"]:
                ddl0 = ddl.copy()

                if ddl["command"] == "observation":   # chime/ligo have command="observation" or "test"
                    logger.info("Received LIGO event")
                    nsamp = ddl["args"]["nsamp"] if "nsamp" in ddl["args"] else None
                    if cl is not None:
                        response = cl.chat_postMessage(channel="#observing", text=f"Starting voltage trigger on LIGO event: {ddl['args']}",
                                                       icon_emoji = ":robot_face::")
                    self.trigger(nsamp=nsamp)
                elif ddl["command"] == "test":
                    logger.info("Received LIGO test")
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
        logger.info(f'Triggered {len(self.pipelines)} pipelines to record {nfile} files with {ntime_per_file} samples each.')

    def submit_voltagebeam(self, dd):
        """ Submit an ASAP voltage beam observation
        """

        sdffile = None  # TODO: update template SDF and define here
        ls.put_dict('/cmd/observing/submitsdf', {'filename': sdffile, 'mode': 'asap'})

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

