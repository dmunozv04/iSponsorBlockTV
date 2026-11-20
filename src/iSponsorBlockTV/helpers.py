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
        if len(self.screen_id) == 26:
            logging.getLogger().warning(
                "The screen id %s is 26 characters long, which is the old format.YouTube is "
                "revoking the old format screen ids; it's likely that this device has stopped "
                "working or will stop working soon. Pair the device again to get the new id. "
                "Please read this for more information on how to do so and what this means: "
                f"{github_wiki_base_url}/new-screen-ID-format",
                self.screen_id,
            )


class Config:
    """Application configuration loaded from and persisted to config.json."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.config_file = data_dir + "/config.json"
        self.devices = []
        self._has_deprecated_atvs = False

        self.__load()

    def to_dict(self):
        """Serialize configuration fields back to a JSON-compatible dict."""
        document = {
            key: value
            for key, value in self.__dict__.items()
            if key not in config_file_blacklist_keys and not key.startswith("_")
        }
        document["devices"] = [
            {**device.__dict__, "offset": device.offset * 1000}
            if isinstance(device, Device)
            else device
            for device in self.devices
        ]
        return document

    def validate(self):
        """Validate configuration fields and instantiate Device objects."""
        if self._has_deprecated_atvs:
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
        from .config_store import normalize_config

        normalized = normalize_config(self.to_dict(), strict=False)
        self.__dict__.update(normalized)
        self.devices = [Device(device) for device in normalized["devices"]]

    def __load(self):
        from .config_store import normalize_config

        try:
            with open(self.config_file, encoding="utf-8") as stream:
                raw = json.load(stream)
            if isinstance(raw, dict) and "atvs" in raw:
                self._has_deprecated_atvs = True
            self.__dict__.update(normalize_config(raw, strict=False))
        except FileNotFoundError:
            if not os.path.exists(self.data_dir):
                if not os.getenv("iSPBTV_docker"):
                    os.makedirs(self.data_dir)
                else:
                    print(
                        "Running in docker without mounting the data dir, check the"
                        " wiki for more information: "
                        f"{github_wiki_base_url}/Installation#Docker"
                    )
                    print(
                        ("This image has recently been updated to v2, and requires changes."),
                        ("Please read this for more information on how to upgrade to V2:"),
                        f"{github_wiki_base_url}/Migrate-from-V1-to-V2",
                    )
                    print("Exiting in 10 seconds...")
                    time.sleep(10)
                    sys.exit()
            self.__dict__.update(normalize_config({}))

    def save(self):
        """Atomically persist the current configuration to disk."""
        from .config_store import write_config

        write_config(self.config_file, self.to_dict())

    def __eq__(self, other):
        if not isinstance(other, Config):
            return NotImplemented
        return self.data_dir == other.data_dir and self.to_dict() == other.to_dict()

    __hash__ = None


@click.group(invoke_without_command=True)
@click.option(
    "--data",
    "-d",
    default=lambda: os.getenv("iSPBTV_data_dir") or user_data_dir("iSponsorBlockTV", "dmunozv04"),
    help="data directory",
)
@click.option("--debug", is_flag=True, help="debug mode")
@click.option("--http-tracing", is_flag=True, help="Enable HTTP request/response tracing")
@click.option("--watch-config", is_flag=True, help="Reload when the configuration file changes")
# legacy commands as arguments
@click.option("--setup", is_flag=True, help="Setup the program graphically", hidden=True)
@click.option(
    "--setup-cli",
    is_flag=True,
    help="Setup the program in the command line",
    hidden=True,
)
@click.pass_context
def cli(ctx, data, debug, http_tracing, watch_config, setup, setup_cli):
    """iSponsorblockTV"""
    ctx.ensure_object(dict)
    ctx.obj["data_dir"] = data
    ctx.obj["debug"] = debug
    ctx.obj["http_tracing"] = http_tracing
    ctx.obj["watch_config"] = watch_config

    logger = logging.getLogger()
    ctx.obj["logger"] = logger
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
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
    config_path = config.config_file
    before_mtime_ns = None
    try:
        before_mtime_ns = os.stat(config_path).st_mtime_ns
    except FileNotFoundError:
        pass
    setup_wizard.main(config)
    after_mtime_ns = None
    try:
        after_mtime_ns = os.stat(config_path).st_mtime_ns
    except FileNotFoundError:
        pass
    if after_mtime_ns is None:
        print(f"No config file was saved to {config_path}")
    elif before_mtime_ns is None or after_mtime_ns != before_mtime_ns:
        print(f"Config saved to {config_path}")
    else:
        print(f"Config unchanged at {config_path}")
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
    if not config.devices and not ctx.obj["watch_config"]:
        raise click.ClickException(
            "No devices found. Run setup, or use --watch-config to wait for configuration."
        )
    main.main(config, ctx.obj["debug"], ctx.obj["http_tracing"], ctx.obj["watch_config"])


# Create fake "self" group to show pyapp options in help menu
# Subcommands remove, restore, update
pyapp_group = click.RichGroup("self", help="pyapp options (update, remove, restore)")
pyapp_group.add_command(
    click.RichCommand("update", help="Update the package to the latest version")
)
pyapp_group.add_command(
    click.Command("remove", help="Remove the package, wiping the installation but not the data")
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
