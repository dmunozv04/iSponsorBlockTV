import html
from hashlib import sha256

from aiohttp import ClientSession
from cache import AsyncLRU

from . import constants, dial_client
from .conditional_ttl_cache import AsyncConditionalTTL


def list_to_tuple(function):
    def wrapper(*args):
        args = [tuple(x) if isinstance(x, list) else x for x in args]
        result = function(*args)
        result = tuple(result) if isinstance(result, list) else result
        return result

    return wrapper


# Class that handles all the api calls and their cache
class ApiHelper:
    def __init__(self, config, web_session: ClientSession) -> None:
        self.apikey = config.apikey
        self.skip_categories = config.skip_categories
        self.channel_whitelist = config.channel_whitelist
        self.skip_count_tracking = config.skip_count_tracking
        self.web_session = web_session
        self.num_devices = len(config.devices)

    # Not used anymore, maybe it can stay here a little longer
    @AsyncLRU(maxsize=10)
    async def get_vid_id(self, title, artist, api_key, web_session):
        params = {"q": title + " " + artist, "key": api_key, "part": "snippet"}
        url = constants.Youtube_api + "search"
        async with web_session.get(url, params=params) as resp:
            data = await resp.json()

        if "error" in data:
            return

        for i in data["items"]:
            if i["id"]["kind"] != "youtube#video":
                continue
            title_api = html.unescape(i["snippet"]["title"])
            artist_api = html.unescape(i["snippet"]["channelTitle"])
            if title_api == title and artist_api == artist:
                return i["id"]["videoId"], i["snippet"]["channelId"]
        return

    @AsyncLRU(maxsize=100)
    async def is_whitelisted(self, vid_id):
        if self.apikey and self.channel_whitelist:
            channel_id = await self.__get_channel_id(vid_id)
            # check if channel id is in whitelist
            for i in self.channel_whitelist:
                if i["id"] == channel_id:
                    return True
        return False

    async def __get_channel_id(self, vid_id):
        params = {"id": vid_id, "key": self.apikey, "part": "snippet"}
        url = constants.Youtube_api + "videos"
        async with self.web_session.get(url, params=params) as resp:
            data = await resp.json()

        if "error" in data:
            return
        data = data["items"][0]
        if data["kind"] != "youtube#video":
            return
        return data["snippet"]["channelId"]

    @AsyncLRU(maxsize=10)
    async def search_channels(self, channel):
        channels = []
        params = {
            "q": channel,
            "key": self.apikey,
            "part": "snippet",
            "type": "channel",
            "maxResults": "5",
        }
        url = constants.Youtube_api + "search"
        async with self.web_session.get(url, params=params) as resp:
            data = await resp.json()
        if "error" in data:
            return channels

        for i in data["items"]:
            # Get channel subscription number
            params = {
                "id": i["snippet"]["channelId"],
                "key": self.apikey,
                "part": "statistics",
            }
            url = constants.Youtube_api + "channels"
            async with self.web_session.get(url, params=params) as resp:
                channel_data = await resp.json()

            if channel_data["items"][0]["statistics"]["hiddenSubscriberCount"]:
                sub_count = "Hidden"
            else:
                sub_count = int(
                    channel_data["items"][0]["statistics"]["subscriberCount"]
                )
                sub_count = format(sub_count, "_")

            channels.append(
                (i["snippet"]["channelId"], i["snippet"]["channelTitle"], sub_count)
            )
        return channels

    @list_to_tuple  # Convert list to tuple so it can be used as a key in the cache
    @AsyncConditionalTTL(
        time_to_live=300, maxsize=10
    )  # 5 minutes for non-locked segments
    async def get_segments(self, vid_id):
        if await self.is_whitelisted(vid_id):
            return (
                [],
                True,
            )  # Return empty list and True to indicate
            # that the cache should last forever
        vid_id_hashed = sha256(vid_id.encode("utf-8")).hexdigest()[
            :4
        ]  # Hashes video id and gets the first 4 characters
        params = {
            "category": self.skip_categories,
            "actionType": constants.SponsorBlock_actiontype,
            "service": constants.SponsorBlock_service,
        }
        headers = {"Accept": "application/json"}
        url = constants.SponsorBlock_api + "skipSegments/" + vid_id_hashed
        async with self.web_session.get(
            url, headers=headers, params=params
        ) as response:
            response_json = await response.json()
        if response.status != 200:
            response_text = await response.text()
            print(
                f"Error getting segments for video {vid_id}, hashed as {vid_id_hashed}."
                f" Code: {response.status} - {response_text}"
            )
            return [], True
        for i in response_json:
            if str(i["videoID"]) == str(vid_id):
                response_json = i
                break
        return self.process_segments(response_json)

    @staticmethod
    def process_segments(response):
        segments = []
        ignore_ttl = True
        try:
            response_segments = response["segments"]
            # sort by end
            response_segments.sort(key=lambda x: x["segment"][1])
            # extend ends of overlapping segments to make one big segment
            for i in response_segments:
                for j in response_segments:
                    if j["segment"][0] <= i["segment"][1] <= j["segment"][1]:
                        i["segment"][1] = j["segment"][1]

            # sort by start
            response_segments.sort(key=lambda x: x["segment"][0])
            # extend starts of overlapping segments to make one big segment
            for i in reversed(response_segments):
                for j in reversed(response_segments):
                    if j["segment"][0] <= i["segment"][0] <= j["segment"][1]:
                        i["segment"][0] = j["segment"][0]

            for i in response_segments:
                ignore_ttl = (
                    ignore_ttl and i["locked"] == 1
                )  # If all segments are locked, ignore ttl
                segment = i["segment"]
                UUID = i["UUID"]
                segment_dict = {"start": segment[0], "end": segment[1], "UUID": [UUID]}
                try:
                    # Get segment before to check if they are too close to each other
                    segment_before_end = segments[-1]["end"]
                    segment_before_start = segments[-1]["start"]
                    segment_before_UUID = segments[-1]["UUID"]

                except IndexError:
                    segment_before_end = -10
                if (
                    segment_dict["start"] - segment_before_end < 1
                ):  # Less than 1 second apart, combine them and skip them together
                    segment_dict["start"] = segment_before_start
                    segment_dict["UUID"].extend(segment_before_UUID)
                    segments.pop()
                segments.append(segment_dict)
        except BaseException:
            pass
        return segments, ignore_ttl

    async def mark_viewed_segments(self, uuids):
        """Marks the segments as viewed in the SponsorBlock API
        if skip_count_tracking is enabled.
        Lets the contributor know that someone skipped the segment (thanks)"""
        if self.skip_count_tracking:
            for i in uuids:
                url = constants.SponsorBlock_api + "viewedVideoSponsorTime/"
                params = {"UUID": i}
                await self.web_session.post(url, params=params)

    async def discover_youtube_devices_dial(self):
        """Discovers YouTube devices using DIAL"""
        dial_screens = await dial_client.discover(self.web_session)
        # print(dial_screens)
        return dial_screens
