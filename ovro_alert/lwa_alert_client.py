import sys
import logging
import subprocess
import time
from pathlib import Path
from time import sleep
import threading
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from os import environ
from astropy.time import Time
from ovro_alert.alert_client import AlertClient
from mnc import control
from observing import makesdf
from dsautils import dsa_store

ls = dsa_store.DsaStore()


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

RECORDER = 'drt1'

# Slurm: run voltage_beam_pipeline.job two hours after submit_voltagebeam; the job script
# resolves the raw voltage path under /lustre/ubuntu/beam01 (see slurm/voltage_beam_pipeline.job).
# File discovery uses VOLTAGE_BEAM_WINDOW_END_EPOCH + lookback (see _schedule_voltage_beam_pipeline):
# a plain mtime window relative to job start would miss files written at alert time.
VOLTAGE_PIPELINE_BEGIN_DELAY = "now+2hours"
VOLTAGE_PIPELINE_NODELIST = environ.get("OVRO_ALERT_VOLTAGE_PIPELINE_NODELIST", "lwacalim10")

class LWAAlertClient(AlertClient):
    def __init__(self, con):
        super().__init__('lwa')
        self.con = con
        self.pipelines = [p for p in con.pipelines if p.pipeline_id in [2, 3]]
        self.con.configure_xengine(recorders=[RECORDER], full=False, calibratebeams=True, force=True)

    def poll(self, loop=5):
        """ Poll the relay API for commands.
        """

        ddc0 = self.get(route='chime')
        ddcasm0 = self.get(route='casm')
        ddl0 = self.get(route='ligo')
        ddg0 = self.get(route='gcn')
        ddd0 = self.get(route='dsa')
        while True:
            mjd = Time.now().mjd
            ddc = self.get(route='chime')
            ddcasm = self.get(route='casm')
            ddl = self.get(route='ligo')
            ddg = self.get(route='gcn')
            ddd = self.get(route='dsa')
            print(".", end="")

            # TODO: validate ddc and ddl have correct fields (and maybe reject malicious content?)
            if (
                ("command_mjd" not in ddc)
                or ("command_mjd" not in ddcasm)
                or ("command_mjd" not in ddl)
                or ("command_mjd" not in ddg)
                or ("command_mjd" not in ddd)
            ):
                print(f"Could not get complete dict from relay: {ddc}, {ddcasm}, {ddl}, {ddg}, {ddd}.")
                sleep(loop)
                continue

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
                                                       text=f"Starting drt1 beam on CHIME event {ddc['args']['id']} with DM={ddc['args']['dm']}",
                                                       icon_emoji = ":robot_face::")
#                    self.submit_powerbeam(ddc["args"])
                    self.submit_voltagebeam(ddc["args"])
                elif ddc["command"] == "test":
                    logger.info("Received CHIME test")

            elif ddcasm["command_mjd"] != ddcasm0["command_mjd"]:
                ddcasm0 = ddcasm.copy()

                if ddcasm["command"] == "observation":
                    logger.info("Received CASM event")
                    if not all(key in ddcasm["args"] for key in ["dm", "position"]):
                        logger.warning(
                            f"CASM args ({ddcasm['args']}) do not include 'dm' and 'position'. Skipping..."
                        )
                        continue
                    if cl is not None:
                        response = cl.chat_postMessage(
                            channel="#observing",
                            text=(
                                f"Starting drt1 beam on CASM event {ddcasm['args'].get('id', 'unknown')}"
                                f" with DM={ddcasm['args']['dm']}"
                            ),
                            icon_emoji=":robot_face::",
                        )
                    self.submit_voltagebeam(ddcasm["args"])
                elif ddcasm["command"] == "test":
                    logger.info("Received CASM test")

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
            elif ddd["command_mjd"] != ddd0["command_mjd"]:
                ddd0 = ddd.copy()

                if ddd["command"] == "observation":   # TODO; check on types
                    logger.info("Received DSA-110 event.")
                    assert all(key in ddd["args"] for key in ["dm", "ra", "dec"])
                    if cl is not None:
                        response = cl.chat_postMessage(channel="#observing",
                                                       text=f"Starting drt1 beam on DSA-110 event: DM={ddd['args']['dm']}, RA={ddd['args']['ra']}, DEC={ddd['args']['dec']}",
                                                       icon_emoji = ":robot_face::")
                    self.submit_voltagebeam({'dm': ddd['args']['dm'], 'position': f"{ddd['args']['ra']},{ddd['args']['dec']}"})
                elif ddg["command"] == "test":
                    logger.info("Received DSA-110 test")

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

        ntime_per_file = 1000320   # compile time in x-engine?
        ntime = int(dt*24000)   # 1/24000=41.666 microsec per sample
        nfile = max(1, ntime//ntime_per_file)  # trigger at least one file

        for pipeline in self.pipelines:
            if pipeline.pipeline_id in path_map:
                path = path_map[pipeline.pipeline_id]
                pipeline.triggered_dump.trigger(ntime_per_file=ntime_per_file, nfile=nfile, dump_path=path)
        logger.info(f'Triggered {len(self.pipelines)} pipelines to record {nfile} files with {ntime_per_file} samples each ({dt} sec).')

    def submit_voltagebeam(self, dd):
        """ Submit an ASAP voltage beam observation
        """

        position = dd["position"].split(",")
        ra = float(position[0])  # degrees
        dec = float(position[1])
        if 'duration' in dd:
            d0 = float(dd['duration'])
        else:
            assert 'dm' in dd
            dm = float(dd["dm"])
            d0 = delay(dm, 1e9, 50) + 10  # Observe for the delay plus a bit more

        sdffile = '/tmp/trigger_voltagebeam.sdf'
        makesdf.create(sdffile, n_obs=1, sess_mode='VOLT', obs_mode='TRK_RADEC', beam_num=int(RECORDER[-1:]),
                       obs_start='now', obs_dur=int(d0*1e3), int_time=0, ra=ra, dec=dec)
        # TODO: test required parameters for voltage beam from SDF

        ls.put_dict('/cmd/observing/submitsdf', {'filename': sdffile, 'mode': 'asap'})
        self._schedule_voltage_beam_pipeline(dd, d0)

    def _schedule_voltage_beam_pipeline(self, dd, duration_sec):
        """Queue Slurm FRB pipeline; voltage path is chosen inside the job from /lustre/ubuntu/beam01.

        sbatch exports dm always. ``time`` (run_pipeline --duration) is exported only when the
        alert included an explicit ``duration``; otherwise the job derives duration from dm to match
        the dispersion bound used for observations without a fixed length.
        """

        if 'dm' not in dd:
            logger.warning(
                "Skipping voltage beam pipeline Slurm job: dm missing from alert args "
                "(required for run_pipeline.py export)."
            )
            return

        job_path = environ.get("OVRO_ALERT_VOLTAGE_BEAM_JOB")
        if job_path:
            job_path = Path(job_path)
        else:
            job_path = Path(__file__).resolve().parent.parent / "slurm" / "voltage_beam_pipeline.job"
        if not job_path.is_file():
            logger.warning("Skipping voltage beam pipeline Slurm job: script not found at %s", job_path)
            return

        dm_s = str(float(dd["dm"]))
        # Omit time so the batch script derives --duration from dm (dispersion bound), unless the
        # alert fixed a custom recording length—then pass time so run_pipeline matches the file.
        if "duration" in dd:
            export = f"ALL,dm={dm_s},time={str(float(duration_sec))}"
        else:
            export = f"ALL,dm={dm_s}"
        if "VOLTAGE_BEAM_SEARCH_DIR" in environ:
            export += f",VOLTAGE_BEAM_SEARCH_DIR={environ['VOLTAGE_BEAM_SEARCH_DIR']}"
        if "VOLTAGE_BEAM_WINDOW_END_EPOCH" in environ:
            export += f",VOLTAGE_BEAM_WINDOW_END_EPOCH={environ['VOLTAGE_BEAM_WINDOW_END_EPOCH']}"
        else:
            # Anchor search to when the recording should finish (wall time at sbatch), not job start
            # (~2h later). Otherwise find -mmin at job start never sees mtimes from alert time.
            slack_s = 180
            window_end = int(time.time()) + int(duration_sec) + slack_s
            export += f",VOLTAGE_BEAM_WINDOW_END_EPOCH={window_end}"
        if "VOLTAGE_BEAM_LOOKBACK_MIN" in environ:
            export += f",VOLTAGE_BEAM_LOOKBACK_MIN={environ['VOLTAGE_BEAM_LOOKBACK_MIN']}"
        else:
            # Include ~observation start through WINDOW_END_EPOCH (mtime in [end - L*60, end]).
            margin_s = 300
            lookback_min = int((duration_sec + margin_s) / 60) + 1
            export += f",VOLTAGE_BEAM_LOOKBACK_MIN={lookback_min}"

        try:
            proc = subprocess.run(
                [
                    "sbatch",
                    f"--begin={VOLTAGE_PIPELINE_BEGIN_DELAY}",
                    f"--nodelist={VOLTAGE_PIPELINE_NODELIST}",
                    f"--export={export}",
                    str(job_path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=60,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logger.error("sbatch timed out scheduling voltage beam pipeline")
            return
        except OSError as e:
            logger.error("sbatch failed to run: %s", e)
            return

        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        if proc.returncode != 0:
            logger.warning(
                "sbatch failed (exit %s): stdout=%r stderr=%r",
                proc.returncode,
                out,
                err,
            )
            return
        logger.info("Scheduled voltage beam pipeline: %s", out or "(no stdout)")
        if err:
            logger.debug("sbatch stderr: %s", err)

    def submit_powerbeam(self, dd):
        """ Submit an ASAP voltage beam observation
        """

        position = dd["position"].split(",")
        ra = float(position[0])  # degrees
        dec = float(position[1])
        if 'duration' in dd:
            d0 = float(dd['duration'])
        else:
            assert 'dm' in dd
            dm = float(dd["dm"])
            d0 = delay(dm, 1e9, 50) + 10  # Observe for the delay plus a bit more

        sdffile = '/tmp/trigger_powerbeam.sdf'
        makesdf.create(sdffile, n_obs=1, sess_mode='POWER', obs_mode='TRK_RADEC', beam_num=int(RECORDER[-1:]),
                       obs_start='now', obs_dur=d0*1e3, ra=ra, dec=dec, int_time=128)

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

        self.con.start_dr(recorders=[RECORDER], duration=d0*1e3, time_avg=1) # (duration is in ms)
        self.con.configure_xengine(RECORDER, calibratebeams=False, full=False)  # get beam control handlers
#        thread = threading.Thread(target=self.con.control_bf, kwargs={'num': 3, 'coord': (RA, Dec), 'track': True, 'duration': d0})
#        thread.start()
#        thread.join()
        self.con.control_bf(num=int(RECORDER[-1:]), coord=(RAh, Dec), track=True, duration=d0)  # RA must be in decimal hours

if __name__ == '__main__':
#    xhosts = [f'lxdlwagpu0{i}' for i in [3,4,5,6,7,8]]  # remove bad gpus
    con = control.Controller()  # xhosts=xhosts)
    client = LWAAlertClient(con)
    client.poll(loop=5)

