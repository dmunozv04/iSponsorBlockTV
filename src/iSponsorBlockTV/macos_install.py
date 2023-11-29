import plistlib
import os
from . import config_setup
"""Not updated to V2 yet, should still work. Here be dragons"""
default_plist = {
    "Label": "com.dmunozv04iSponsorBlockTV",
    "RunAtLoad": True,
    "StartInterval": 20,
    "EnvironmentVariables": {"PYTHONUNBUFFERED": "YES"},
    "StandardErrorPath": "",  # Fill later
    "StandardOutPath": "",
    "ProgramArguments": "",
    "WorkingDirectory": "",
}


def create_plist(path):
    plist = default_plist
    plist["ProgramArguments"] = [path + "/iSponsorBlockTV-macos"]
    plist["StandardErrorPath"] = path + "/iSponsorBlockTV.error.log"
    plist["StandardOutPath"] = path + "/iSponsorBlockTV.out.log"
    plist["WorkingDirectory"] = path
    launchd_path = os.path.expanduser("~/Library/LaunchAgents/")
    path_to_save = launchd_path + "com.dmunozv04.iSponsorBlockTV.plist"

    with open(path_to_save, "wb") as fp:
        plistlib.dump(plist, fp)


def run_setup(file):
    config = {}
    config_setup.main(config, file, debug=False)


def main():
    correct_path = os.path.expanduser("~/iSponsorBlockTV")
    if os.path.isfile(correct_path + "/iSponsorBlockTV-macos"):
        print("Program is on the right path")
        print("The launch daemon will now be installed")
        create_plist(correct_path)
        run_setup(correct_path + "/config.json")
        print(
            "Launch daemon installed. Please restart the computer to enable it or use:\n launchctl load ~/Library/LaunchAgents/com.dmunozv04.iSponsorBlockTV.plist"
        )
    else:
        if not os.path.exists(correct_path):
            os.makedirs(correct_path)
        print(
            "Please move the program to the correct path: "
            + correct_path
            + "opeing now on finder..."
        )
        os.system("open -R " + correct_path)
