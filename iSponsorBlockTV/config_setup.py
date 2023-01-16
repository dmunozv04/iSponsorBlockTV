import pyatv
import json
import asyncio
from pyatv.const import DeviceModel
import sys


def save_config(config, config_file):
    with open(config_file, "w") as f:
        json.dump(config, f)


# Taken from postlund/pyatv atvremote.py
async def _read_input(loop: asyncio.AbstractEventLoop, prompt: str):
    sys.stdout.write(prompt)
    sys.stdout.flush()
    user_input = await loop.run_in_executor(None, sys.stdin.readline)
    return user_input.strip()


async def find_atvs(loop):
    devices = await pyatv.scan(loop)
    if not devices:
        print("No devices found")
        return
    atvs = []
    for i in devices:
        # Only get Apple TV's
        if i.device_info.model in [
            DeviceModel.Gen4,
            DeviceModel.Gen4K,
            DeviceModel.AppleTV4KGen2,
        ]:
            # if i.device_info.model in [DeviceModel.AppleTV4KGen2]: #FOR TESTING
            if input("Found {}. Do you want to add it? (y/n) ".format(i.name)) == "y":

                identifier = i.identifier

                pairing = await pyatv.pair(
                    i, loop=loop, protocol=pyatv.Protocol.AirPlay
                )
                await pairing.begin()
                if pairing.device_provides_pin:
                    pin = await _read_input(loop, "Enter PIN on screen: ")
                    pairing.pin(pin)

                await pairing.finish()
                if pairing.has_paired:
                    creds = pairing.service.credentials
                    atvs.append(
                        {"identifier": identifier, "airplay_credentials": creds}
                    )
                    print("Pairing successful")
                await pairing.close()
    return atvs


def main(config, config_file, debug):
    try:
        num_atvs = len(config["atvs"])
    except:
        num_atvs = 0
    if (
        input("Found {} Apple TV(s) in config.json. Add more? (y/n) ".format(num_atvs))
        == "y"
    ):
        loop = asyncio.get_event_loop_policy().get_event_loop()
        if debug:
            loop.set_debug(True)
        asyncio.set_event_loop(loop)
        task = loop.create_task(find_atvs(loop))
        loop.run_until_complete(task)
        atvs = task.result()
        try:
            for i in atvs:
                config["atvs"].append(i)
            print("done adding")
        except:
            print("rewriting atvs (don't worry if none were saved before)")
            config["atvs"] = atvs

    try:
        apikey = config["apikey"]
    except:
        apikey = ""
    if apikey != "":
        if input("Apikey already specified. Change it? (y/n) ") == "y":
            apikey = input("Enter your API key: ")
            config["apikey"] = apikey
    else:
        print(
            "get youtube apikey here: https://developers.google.com/youtube/registering_an_application"
        )
        apikey = input("Enter your API key: ")
        config["apikey"] = apikey

    try:
        skip_categories = config["skip_categories"]
    except:
        skip_categories = []

    if skip_categories != []:
        if input("Skip categories already specified. Change them? (y/n) ") == "y":
            categories = input(
                "Enter skip categories (space sepparated)(don't add a comma in between) Options: [sponsor selfpromo exclusive_access interaction poi_highlight intro outro preview filler music_offtopic:\n"
            )
            skip_categories = categories.split(" ")
    else:
        categories = input(
            "Enter skip categories (space sepparated) Options: [sponsor, selfpromo, exclusive_access, interaction, poi_highlight, intro, outro, preview, filler, music_offtopic:\n"
        )
        skip_categories = categories.split(" ")
    config["skip_categories"] = skip_categories

    print("config finished")
    save_config(config, config_file)
