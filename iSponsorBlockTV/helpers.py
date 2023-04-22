import argparse
from . import config_setup
from . import main
from . import macos_install
import json
import os
import logging
import sys

def load_config(config_file):
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
        except:
            print("Creating config file")
            config = {}
    else:
        if os.getenv("iSPBTV_docker"):
            print(
                "You are running in docker, you have to mount the config file.\nPlease check the README.md for more information."
            )
            sys.exit()
            return
        else:
            print("Creating config file")
            config = {}  # Create blank config to setup
    return config


def app_start():
    parser = argparse.ArgumentParser(description="iSponsorblockTV")
    parser.add_argument("--file", "-f", default="config.json", help="config file")
    parser.add_argument("--setup", "-s", action="store_true", help="setup the program")
    parser.add_argument("--debug", "-d", action="store_true", help="debug mode")
    parser.add_argument("--macos_install", action="store_true", help="install in macOS")
    args = parser.parse_args()

    config = load_config(args.file)
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    if args.setup:  # Setup the config file
        config_setup.main(config, args.file, args.debug)
    elif args.macos_install:
        macos_install.main()

    else:
        try:  # Check if config file has the correct structure
            config["atvs"], config["apikey"], config["skip_categories"], config["channel_whitelist"]
        except:  # If not, ask to setup the program
            print("invalid config file, please run with --setup")
            sys.exit()
        main.main(
            config["atvs"], config["apikey"], config["skip_categories"], config["channel_whitelist"], args.debug
        )
