import json
import logging
import os
import sys
import time

import rich_click as click
from appdirs import user_data_dir

from . import config_setup, main, setup_wizard
from .constants import config_file_blacklist_keys, github_wiki_base_url


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
        self.skip_categories = []  # These are the categories on the config file
        self.channel_whitelist = []
        self.skip_count_tracking = True
        self.mute_ads = False
        self.skip_ads = False
        self.auto_play = True
        self.join_name = "iSponsorBlockTV"
        self.__load()

    def validate(self):
        if hasattr(self, "atvs"):
            print(
                (
                    "The atvs config option is deprecated and has stopped working."
                    " Please read this for more information "
                    "on how to upgrade to V2:\n"
                    f"{github_wiki_base_url}/Migrate-from-V1-to-V2"
                ),
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
            raise ValueError(
                "No youtube API key found and channel whitelist is not empty"
            )
        if not self.skip_categories:
            self.skip_categories = ["sponsor"]
            print("No categories found, using default: sponsor")

    def __load(self):
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                for i in config:
                    if i not in config_file_blacklist_keys:
                        setattr(self, i, config[i])
        except FileNotFoundError:
            print("Could not load config file")
            # Create data directory if it doesn't exist (if we're not running in docker)
            if not os.path.exists(self.data_dir):
                if not os.getenv("iSPBTV_docker"):
                    print("Creating data directory")
                    os.makedirs(self.data_dir)
                else:  # Running in docker without mounting the data dir
                    print(
                        "Running in docker without mounting the data dir, check the"
                        " wiki for more information: "
                        f"{github_wiki_base_url}/Installation#Docker"
                    )
                    print(
                        (
                            "This image has recently been updated to v2, and requires"
                            " changes."
                        ),
                        (
                            "Please read this for more information on how to upgrade"
                            " to V2:"
                        ),
                        f"{github_wiki_base_url}/Migrate-from-V1-to-V2",
                    )
                    print("Exiting in 10 seconds...")
                    time.sleep(10)
                    sys.exit()
            else:
                print("Blank config file created")

    def save(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            config_dict = self.__dict__
            # Don't save the config file name
            config_file = self.config_file
            data_dir = self.data_dir
            del config_dict["config_file"]
            del config_dict["data_dir"]
            json.dump(config_dict, f, indent=4)
            self.config_file = config_file
            self.data_dir = data_dir

    def __eq__(self, other):
        if isinstance(other, Config):
            return self.__dict__ == other.__dict__
        return False

    def __hash__(self):
        return hash(tuple(sorted(self.items())))


@click.group(invoke_without_command=True)
@click.option(
    "--data",
    "-d",
    default=lambda: os.getenv("iSPBTV_data_dir")
    or user_data_dir("iSponsorBlockTV", "dmunozv04"),
    help="data directory",
)
@click.option("--debug", is_flag=True, help="debug mode")
# legacy commands as arguments
@click.option(
    "--setup", is_flag=True, help="Setup the program graphically", hidden=True
)
@click.option(
    "--setup-cli",
    is_flag=True,
    help="Setup the program in the command line",
    hidden=True,
)
@click.pass_context
def cli(ctx, data, debug, setup, setup_cli):
    """iSponsorblockTV"""
    ctx.ensure_object(dict)
    ctx.obj["data_dir"] = data
    ctx.obj["debug"] = debug

    logger = logging.getLogger()
    ctx.obj["logger"] = logger
    sh = logging.StreamHandler()
    sh.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(sh)

    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    if ctx.invoked_subcommand is None:
        if setup:
            ctx.invoke(setup_command)
        elif setup_cli:
            ctx.invoke(setup_cli_command)
        else:
            ctx.invoke(start)


@cli.command(name="setup")
@click.pass_context
def setup_command(ctx):
    """Setup the program graphically"""
    config = Config(ctx.obj["data_dir"])
    setup_wizard.main(config)
    sys.exit()


@cli.command(name="setup-cli")
@click.pass_context
def setup_cli_command(ctx):
    """Setup the program in the command line"""
    config = Config(ctx.obj["data_dir"])
    config_setup.main(config, ctx.obj["debug"])


@cli.command()
@click.pass_context
def start(ctx):
    """Start the main program"""
    config = Config(ctx.obj["data_dir"])
    config.validate()
    main.main(config, ctx.obj["debug"])


# Create fake "self" group to show pyapp options in help menu
# Subcommands remove, restore, update
pyapp_group = click.RichGroup("self", help="pyapp options (update, remove, restore)")
pyapp_group.add_command(
    click.RichCommand("update", help="Update the package to the latest version")
)
pyapp_group.add_command(
    click.Command(
        "remove", help="Remove the package, wiping the installation but not the data"
    )
)
pyapp_group.add_command(
    click.RichCommand(
        "restore", help="Restore the package to its original state by reinstalling it"
    )
)
if os.getenv("PYAPP"):
    cli.add_command(pyapp_group)


def app_start():
    cli(obj={})
