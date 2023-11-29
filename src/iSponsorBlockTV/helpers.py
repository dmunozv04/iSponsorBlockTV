import argparse
import json
import logging
import os
import sys
import time

from appdirs import user_data_dir

from . import config_setup, main, setup_wizard


class Device:
    def __init__(self, args_dict):
        self.screen_id = ""
        self.offset = 0
        self.__load(args_dict)
        self.__validate()

    def __load(self, args_dict):
        for i in args_dict:
            setattr(self, i, args_dict[i])
        # Change offset to seconds (from milliseconds)
        self.offset = self.offset / 1000

    def __validate(self):
        if not self.screen_id:
            raise ValueError("No screen id found")


class Config:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.config_file = data_dir + "/config.json"

        self.devices = []
        self.apikey = ""
        self.skip_categories = []
        self.channel_whitelist = []
        self.skip_count_tracking = True
        self.mute_ads = False
        self.skip_ads = False
        self.__load()

    def validate(self):
        if hasattr(self, "atvs"):
            print(
                "The atvs config option is deprecated and has stopped working. Please read this for more information "
                "on how to upgrade to V2: \nhttps://github.com/dmunozv04/iSponsorBlockTV/wiki/Migrate-from-V1-to-V2",
            )
            print("Exiting in 10 seconds...")
            time.sleep(10)
            sys.exit()
        if not self.devices:
            print("No devices found, please add at least one device")
            print("Exiting in 10 seconds...")
            time.sleep(10)
            sys.exit()
        self.devices = [Device(i) for i in self.devices]
        if not self.apikey and self.channel_whitelist:
            raise ValueError("No youtube API key found and channel whitelist is not empty")
        if not self.skip_categories:
            self.categories = ["sponsor"]
            print("No categories found, using default: sponsor")

    def __load(self):
        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)
                for i in config:
                    setattr(self, i, config[i])
        except FileNotFoundError:
            print("Could not load config file")
            # Create data directory if it doesn't exist (if we're not running in docker)
            if not os.path.exists(self.data_dir):
                if not os.getenv("iSPBTV_docker"):
                    print("Creating data directory")
                    os.makedirs(self.data_dir)
                else:  # Running in docker without mounting the data dir
                    print("Running in docker without mounting the data dir, check the wiki for more information: "
                          "https://github.com/dmunozv04/iSponsorBlockTV/wiki/Installation#Docker")
                    print("This image has recently been updated to v2, and requires changes.",
                          "Please read this for more information on how to upgrade to V2:",
                          "https://github.com/dmunozv04/iSponsorBlockTV/wiki/Migrate-from-V1-to-V2")
                    print("Exiting in 10 seconds...")
                    time.sleep(10)
                    sys.exit()
            else:
                print("Blank config file created")

    def save(self):
        with open(self.config_file, "w") as f:
            config_dict = self.__dict__
            # Don't save the config file name
            config_file = self.config_file
            del config_dict["config_file"]
            json.dump(config_dict, f, indent=4)
            self.config_file = config_file

    def __eq__(self, other):
        if isinstance(other, Config):
            return self.__dict__ == other.__dict__
        return False


def app_start():
    #If env has a data dir use that, otherwise use the default
    default_data_dir = os.getenv("iSPBTV_data_dir") or user_data_dir("iSponsorBlockTV", "dmunozv04")
    parser = argparse.ArgumentParser(description="iSponsorblockTV")
    parser.add_argument("--data-dir", "-d", default=default_data_dir, help="data directory")
    parser.add_argument("--setup", "-s", action="store_true", help="setup the program graphically")
    parser.add_argument("--setup-cli", "-sc", action="store_true", help="setup the program in the command line")
    parser.add_argument("--debug", action="store_true", help="debug mode")
    args = parser.parse_args()

    config = Config(args.data_dir)
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    if args.setup:  # Set up the config file graphically
        setup_wizard.main(config)
        sys.exit()
    if args.setup_cli:  # Set up the config file
        config_setup.main(config, args.debug)
    else:
        config.validate()
        main.main(config, args.debug)
