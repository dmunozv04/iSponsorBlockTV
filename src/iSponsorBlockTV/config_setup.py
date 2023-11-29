import asyncio
import aiohttp
from . import api_helpers, ytlounge


async def pair_device():
    try:
        lounge_controller = ytlounge.YtLoungeApi("iSponsorBlockTV")
        pairing_code = input("Enter pairing code (found in Settings - Link with TV code): ")
        pairing_code = int(pairing_code.replace("-", "").replace(" ", ""))  # remove dashes and spaces
        print("Pairing...")
        paired = await lounge_controller.pair(pairing_code)
        if not paired:
            print("Failed to pair device")
            return
        device = {
            "screen_id": lounge_controller.auth.screen_id,
            "name": lounge_controller.screen_name,
        }
        print(f"Paired device: {device['name']}")
        return device
    except Exception as e:
        print(f"Failed to pair device: {e}")
        return


def main(config, debug: bool) -> None:
    print("Welcome to the iSponsorBlockTV cli setup wizard")
    loop = asyncio.get_event_loop_policy().get_event_loop()
    if debug:
        loop.set_debug(True)
    asyncio.set_event_loop(loop)
    if hasattr(config, "atvs"):
        print(
            "The atvs config option is deprecated and has stopped working. Please read this for more information on "
            "how to upgrade to V2: \nhttps://github.com/dmunozv04/iSponsorBlockTV/wiki/Migrate-from-V1-to-V2")
        if input("Do you want to remove the legacy 'atvs' entry (the app won't start with it present)? (y/n) ") == "y":
            del config["atvs"]
    devices = config.devices
    while not input(f"Paired with {len(devices)} Device(s). Add more? (y/n) ") == "n":
        task = loop.create_task(pair_device())
        loop.run_until_complete(task)
        device = task.result()
        if device:
            devices.append(device)
    config.devices = devices

    apikey = config.apikey
    if apikey:
        if input("API key already specified. Change it? (y/n) ") == "y":
            apikey = input("Enter your API key: ")
            config["apikey"] = apikey
    else:
        if input("API key only needed for the channel whitelist function. Add it? (y/n) ") == "y":
            print(
                "Get youtube apikey here: https://developers.google.com/youtube/registering_an_application"
            )
            apikey = input("Enter your API key: ")
            config["apikey"] = apikey
    config.apikey = apikey

    skip_categories = config.skip_categories
    if skip_categories:
        if input("Skip categories already specified. Change them? (y/n) ") == "y":
            categories = input(
                "Enter skip categories (space or comma sepparated) Options: [sponsor selfpromo exclusive_access "
                "interaction poi_highlight intro outro preview filler music_offtopic]:\n"
            )
            skip_categories = categories.replace(",", " ").split(" ")
            skip_categories = [x for x in skip_categories if x != '']  # Remove empty strings
    else:
        categories = input(
            "Enter skip categories (space or comma sepparated) Options: [sponsor, selfpromo, exclusive_access, "
            "interaction, poi_highlight, intro, outro, preview, filler, music_offtopic:\n"
        )
        skip_categories = categories.replace(",", " ").split(" ")
        skip_categories = [x for x in skip_categories if x != '']  # Remove empty strings
    config.skip_categories = skip_categories

    channel_whitelist = config.channel_whitelist
    if input("Do you want to whitelist any channels from being ad-blocked? (y/n) ") == "y":
        if not apikey:
            print(
                "WARNING: You need to specify an API key to use this function, otherwise the program will fail to "
                "start.\nYou can add one by re-running this setup wizard.")
        web_session = aiohttp.ClientSession()
        api_helper = api_helpers.ApiHelper(config, web_session)
        while True:
            channel_info = {}
            channel = input("Enter a channel name or \"/exit\" to exit: ")
            if channel == "/exit":
                break

            task = loop.create_task(api_helper.search_channels(channel, apikey, web_session))
            loop.run_until_complete(task)
            results = task.result()
            if len(results) == 0:
                print("No channels found")
                continue

            for i in range(len(results)):
                print(f"{i}: {results[i][1]} - Subs: {results[i][2]}")
            print("5: Enter a custom channel ID")
            print("6: Go back")

            choice = -1
            choice = input("Select one option of the above [0-6]: ")
            while choice not in [str(x) for x in range(7)]:
                print("Invalid choice")
                choice = input("Select one option of the above [0-6]: ")

            if choice == "5":
                channel_info["id"] = input("Enter a channel ID: ")
                channel_info["name"] = input("Enter the channel name: ")
                channel_whitelist.append(channel_info)
                continue
            elif choice == "6":
                continue

            channel_info["id"] = results[int(choice)][0]
            channel_info["name"] = results[int(choice)][1]
            channel_whitelist.append(channel_info)
        # Close web session asynchronously
        loop.run_until_complete(web_session.close())

    config.channel_whitelist = channel_whitelist

    config.skip_count_tracking = not input(
        "Do you want to report skipped segments to sponsorblock. Only the segment UUID will be sent? (y/n) ") == "n"
    print("Config finished")
    config.save()
