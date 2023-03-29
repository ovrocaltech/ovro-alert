from time import sleep
from ovro_alert.alert_client import AlertClient


class DSAAlertClient(AlertClient):
    def poll(self, loop=5):
        """ Poll the relay API for commands.
        """

        dd = self.get()
        while True:
            mjd = time.Time.now().mjd
            dd2 = self.get()
            if dd2["command_mjd"] != dd["command_mjd"]:
                dd = dd2.copy()
                print(f"New command: {dd}")
            else:
                sleep(loop)
                continue
        
    def slew(self):
        """ Slew to new elevation
        """

        pass
