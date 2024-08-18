import os
import plistlib
import subprocess
from platform import system

from appdirs import user_log_dir


def select_service_manager() -> "ServiceManager":
    platform = system()
    if platform == "Darwin":
        return Launchd
    elif platform == "Linux":
        return Systemd
    else:
        raise NotImplementedError("Unsupported platform")


class ServiceManager:
    def __init__(self, executable_path, *args, **kwargs):
        self.executable_path = executable_path

    def start(self):
        pass

    def stop(self):
        pass

    def restart(self):
        pass

    def status(self):
        pass

    def install(self):
        pass

    def uninstall(self):
        pass

    def enable(self):
        pass

    def disable(self):
        pass


class Launchd(ServiceManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_name = "com.dmunozv04.iSponsorBlockTV"
        self.service_path = (
            os.path.expanduser("~/Library/LaunchAgents/") + self.service_name + ".plist"
        )

    def start(self):
        subprocess.run(["launchctl", "start", self.service_name])

    def stop(self):
        subprocess.run(["launchctl", "stop", self.service_name])

    def restart(self):
        subprocess.run(["launchctl", "restart", self.service_name])

    def status(self):
        subprocess.run(["launchctl", "list", self.service_name])

    def install(self):
        if os.path.exists(self.service_path):
            print("Service already installed")
            return
        logs_dir = user_log_dir("iSponsorBlockTV", "dmunozv04")
        # ensure the logs directory exists
        os.makedirs(logs_dir, exist_ok=True)
        plist = {
            "Label": "com.dmunozv04.iSponsorBlockTV",
            "RunAtLoad": True,
            "StartInterval": 20,
            "EnvironmentVariables": {"PYTHONUNBUFFERED": "YES"},
            "StandardErrorPath": logs_dir + "/iSponsorBlockTV.err",
            "StandardOutPath": logs_dir + "/iSponsorBlockTV.out",
            "Program": self.executable_path,
        }
        with open(self.service_path, "wb") as fp:
            plistlib.dump(plist, fp)
        print("Service installed")
        self.enable()

    def uninstall(self):
        self.disable()
        # Remove the file
        try:
            os.remove(self.service_path)
            print("Service uninstalled")
        except FileNotFoundError:
            print("Service not found")

    def enable(self):
        subprocess.run(["launchctl", "load", self.service_path])

    def disable(self):
        subprocess.run(["launchctl", "stop", self.service_name])
        subprocess.run(["launchctl", "unload", self.service_path])


class Systemd(ServiceManager):
    pass
