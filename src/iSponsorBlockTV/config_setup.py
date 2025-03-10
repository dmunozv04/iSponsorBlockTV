import asyncio

import aiohttp

from . import api_helpers, ytlounge

# Constants for user input prompts
ATVS_REMOVAL_PROMPT = (
    "Do you want to remove the legacy 'atvs' entry (the app won't start"
    " with it present)? (y/N) "
)
PAIRING_CODE_PROMPT = "Enter pairing code (found in Settings - Link with TV code): "
ADD_MORE_DEVICES_PROMPT = "Paired with {num_devices} Device(s). Add more? (y/N) "
CHANGE_API_KEY_PROMPT = "API key already specified. Change it? (y/N) "
ADD_API_KEY_PROMPT = (
    "API key only needed for the channel whitelist function. Add it? (y/N) "
)
ENTER_API_KEY_PROMPT = "Enter your API key: "
CHANGE_SKIP_CATEGORIES_PROMPT = "Skip categories already specified. Change them? (y/N) "
ENTER_SKIP_CATEGORIES_PROMPT = (
    "Enter skip categories (space or comma sepparated) Options: [sponsor,"
    " selfpromo, exclusive_access, interaction, poi_highlight, intro, outro,"
    " preview, filler, music_offtopic]:\n"
)
WHITELIST_CHANNELS_PROMPT = (
    "Do you want to whitelist any channels from being ad-blocked? (y/N) "
)
SEARCH_CHANNEL_PROMPT = 'Enter a channel name or "/exit" to exit: '
SELECT_CHANNEL_PROMPT = "Select one option of the above [0-6]: "
ENTER_CHANNEL_ID_PROMPT = "Enter a channel ID: "
ENTER_CUSTOM_CHANNEL_NAME_PROMPT = "Enter the channel name: "
REPORT_SKIPPED_SEGMENTS_PROMPT = (
    "Do you want to report skipped segments to sponsorblock. Only the segment"
    " UUID will be sent? (Y/n) "
)
MUTE_ADS_PROMPT = "Do you want to mute native YouTube ads automatically? (y/N) "
SKIP_ADS_PROMPT = "Do you want to skip native YouTube ads automatically? (y/N) "
AUTOPLAY_PROMPT = "Do you want to enable autoplay? (Y/n) "


def get_yn_input(prompt):
    while choice := input(prompt):
        if choice.lower() in ["y", "n"]:
            return choice.lower()
        print("Invalid input. Please enter 'y' or 'n'.")
    return None


async def create_web_session():
    return aiohttp.ClientSession()


async def pair_device(web_session: aiohttp.ClientSession):
    try:
        lounge_controller = ytlounge.YtLoungeApi()
        await lounge_controller.change_web_session(web_session)
        pairing_code = input(PAIRING_CODE_PROMPT)
        pairing_code = int(
            pairing_code.replace("-", "").replace(" ", "")
        )  # remove dashes and spaces
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
    web_session = loop.run_until_complete(create_web_session())
    if debug:
        loop.set_debug(True)
    asyncio.set_event_loop(loop)
    if hasattr(config, "atvs"):
        print(
            "The atvs config option is deprecated and has stopped working. Please read"
            " this for more information on how to upgrade to V2:"
            " \nhttps://github.com/dmunozv04/iSponsorBlockTV/wiki/Migrate-from-V1-to-V2"
        )
        choice = get_yn_input(ATVS_REMOVAL_PROMPT)
        if choice == "y":
            del config["atvs"]

    devices = config.devices
    choice = get_yn_input(ADD_MORE_DEVICES_PROMPT.format(num_devices=len(devices)))
    while choice == "y":
        device = loop.run_until_complete(pair_device(web_session))
        if device:
            devices.append(device)
        choice = get_yn_input(ADD_MORE_DEVICES_PROMPT.format(num_devices=len(devices)))
    config.devices = devices

    apikey = config.apikey
    if apikey:
        choice = get_yn_input(CHANGE_API_KEY_PROMPT)
        if choice == "y":
            apikey = input(ENTER_API_KEY_PROMPT)
    else:
        choice = get_yn_input(ADD_API_KEY_PROMPT)
        if choice == "y":
            print(
                "Get youtube apikey here:"
                " https://developers.google.com/youtube/registering_an_application"
            )
            apikey = input(ENTER_API_KEY_PROMPT)
    config.apikey = apikey

    skip_categories = config.skip_categories
    if skip_categories:
        choice = get_yn_input(CHANGE_SKIP_CATEGORIES_PROMPT)
        if choice == "y":
            categories = input(ENTER_SKIP_CATEGORIES_PROMPT)
            skip_categories = categories.replace(",", " ").split(" ")
            skip_categories = [
                x for x in skip_categories if x != ""
            ]  # Remove empty strings
    else:
        categories = input(ENTER_SKIP_CATEGORIES_PROMPT)
        skip_categories = categories.replace(",", " ").split(" ")
        skip_categories = [
            x for x in skip_categories if x != ""
        ]  # Remove empty strings
    config.skip_categories = skip_categories

    channel_whitelist = config.channel_whitelist
    choice = get_yn_input(WHITELIST_CHANNELS_PROMPT)
    if choice == "y":
        if not apikey:
            print(
                "WARNING: You need to specify an API key to use this function,"
                " otherwise the program will fail to start.\nYou can add one by"
                " re-running this setup wizard."
            )
        api_helper = api_helpers.ApiHelper(config, web_session)
        while True:
            channel_info = {}
            channel = input(SEARCH_CHANNEL_PROMPT)
            if channel == "/exit":
                break

            task = loop.create_task(
                api_helper.search_channels(channel, apikey, web_session)
            )
            loop.run_until_complete(task)
            results = task.result()
            if len(results) == 0:
                print("No channels found")
                continue

            for i, item in enumerate(results):
                print(f"{i}: {item[1]} - Subs: {item[2]}")
            print("5: Enter a custom channel ID")
            print("6: Go back")

            while choice := input(SELECT_CHANNEL_PROMPT):
                if choice in [str(x) for x in range(7)]:
                    break
                print("Invalid choice")

            if choice == "5":
                channel_info["id"] = input(ENTER_CHANNEL_ID_PROMPT)
                channel_info["name"] = input(ENTER_CUSTOM_CHANNEL_NAME_PROMPT)
                channel_whitelist.append(channel_info)
                continue
            if choice == "6":
                continue

            channel_info["id"] = results[int(choice)][0]
            channel_info["name"] = results[int(choice)][1]
            channel_whitelist.append(channel_info)
        # Close web session asynchronously

    config.channel_whitelist = channel_whitelist

    choice = get_yn_input(REPORT_SKIPPED_SEGMENTS_PROMPT)
    config.skip_count_tracking = choice != "n"

    choice = get_yn_input(MUTE_ADS_PROMPT)
    config.mute_ads = choice == "y"

    choice = get_yn_input(SKIP_ADS_PROMPT)
    config.skip_ads = choice == "y"

    choice = get_yn_input(AUTOPLAY_PROMPT)
    config.auto_play = choice != "n"

    print("Config finished")
    config.save()
    loop.run_until_complete(web_session.close())
