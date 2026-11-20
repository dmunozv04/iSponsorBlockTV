"""Shared configuration normalization and atomic JSON persistence."""

import copy
import json
import math
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from .constants import SponsorBlock_api, skip_categories

DEFAULT_CONFIG = {
    "devices": [],
    "apikey": "",
    "skip_categories": ["sponsor"],
    "channel_whitelist": [],
    "skip_count_tracking": True,
    "mute_ads": False,
    "skip_ads": False,
    "minimum_skip_length": 1,
    "auto_play": True,
    "join_name": "iSponsorBlockTV",
    "use_proxy": False,
    "sponsorblock_api_url": SponsorBlock_api,
}


def _string(value, field, required=False):
    if not isinstance(value, str) or len(value) > 4096 or (required and not value.strip()):
        raise ValueError(f"{field} must be {'a non-empty' if required else 'a'} string")


def _number(value, field, minimum=None):
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{field} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field} must be at least {minimum}")


def normalize_config(document, *, strict=True):
    """Validate a configuration mapping and fill in default values."""
    if not isinstance(document, dict):
        raise TypeError("Configuration must be a JSON object")
    unknown = document.keys() - DEFAULT_CONFIG.keys()
    if strict and unknown:
        raise ValueError("Configuration contains unsupported fields")
    config = copy.deepcopy(DEFAULT_CONFIG)
    for key, value in document.items():
        if key in DEFAULT_CONFIG:
            config[key] = copy.deepcopy(value)
    if config["skip_categories"] is None:
        config["skip_categories"] = ["sponsor"]
    for field in ("skip_count_tracking", "mute_ads", "skip_ads", "auto_play", "use_proxy"):
        if type(config[field]) is not bool:
            raise ValueError(f"{field} must be true or false")
    for field in ("apikey", "join_name", "sponsorblock_api_url"):
        _string(config[field], field, required=field != "apikey")
    api_url = urlsplit(config["sponsorblock_api_url"])
    if api_url.scheme not in ("http", "https") or not api_url.hostname:
        raise ValueError("sponsorblock_api_url must be an HTTP or HTTPS URL")
    try:
        _ = api_url.port
    except ValueError as error:
        raise ValueError("sponsorblock_api_url must use a valid port") from error
    if api_url.username or api_url.password or api_url.query or api_url.fragment:
        raise ValueError("sponsorblock_api_url cannot contain credentials, query, or fragment")
    config["sponsorblock_api_url"] = config["sponsorblock_api_url"].rstrip("/") + "/"
    _number(config["minimum_skip_length"], "minimum_skip_length", minimum=0)
    for field in ("devices", "channel_whitelist", "skip_categories"):
        if not isinstance(config[field], list) or len(config[field]) > 1000:
            raise ValueError(f"{field} must be a list with at most 1000 entries")
    allowed_categories = {category for _, category in skip_categories}
    if any(
        not isinstance(category, str) or category not in allowed_categories
        for category in config["skip_categories"]
    ):
        raise ValueError("skip_categories contains an unsupported category")
    seen = set()
    normalized_devices = []
    for device in config["devices"]:
        if not isinstance(device, dict):
            raise TypeError("Each device must be a JSON object")
        extra_device_keys = device.keys() - {"screen_id", "name", "offset"}
        if strict and extra_device_keys:
            raise ValueError("Each device must contain only screen_id, name, and offset")
        entry = {
            "screen_id": device.get("screen_id"),
            "name": device.get("name", "YouTube on TV"),
            "offset": device.get("offset", 0),
        }
        _string(entry["screen_id"], "device.screen_id", required=True)
        _string(entry["name"], "device.name")
        _number(entry["offset"], "device.offset")
        if entry["screen_id"] in seen:
            raise ValueError("A device screen_id cannot be added twice")
        seen.add(entry["screen_id"])
        normalized_devices.append(entry)
    config["devices"] = normalized_devices
    normalized_channels = []
    for channel in config["channel_whitelist"]:
        if not isinstance(channel, dict):
            raise TypeError("Each whitelisted channel must be a JSON object")
        extra_channel_keys = channel.keys() - {"id", "name"}
        if strict and extra_channel_keys:
            raise ValueError("Each whitelisted channel must contain only id and name")
        entry = {
            "id": channel.get("id"),
            "name": channel.get("name", ""),
        }
        _string(entry["id"], "channel.id", required=True)
        _string(entry["name"], "channel.name")
        normalized_channels.append(entry)
    config["channel_whitelist"] = normalized_channels
    if config["channel_whitelist"] and not config["apikey"].strip():
        raise ValueError("An API key is required when the channel whitelist is not empty")
    return config


def read_config(path, *, strict=False):
    """Load and normalize a JSON configuration file, returning defaults if missing."""
    try:
        return normalize_config(json.loads(Path(path).read_text(encoding="utf-8")), strict=strict)
    except FileNotFoundError:
        return normalize_config({})


def atomic_write_json(path, data, *, indent=4, prefix=".tmp-"):
    """Atomically write JSON data to path via a same-directory temporary file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=prefix,
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = stream.name
            json.dump(data, stream, indent=indent, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def write_config(path, document):
    """Validate and atomically persist a configuration document."""
    config = normalize_config(document, strict=True)
    atomic_write_json(path, config, indent=4, prefix=".config-")
    return config
