from cache import AsyncTTL, AsyncLRU
from . import constants
from hashlib import sha256
from asyncio import create_task
import html


def listToTuple(function):
    def wrapper(*args):
        args = [tuple(x) if type(x) == list else x for x in args]
        result = function(*args)
        result = tuple(result) if type(result) == list else result
        return result

    return wrapper


@AsyncLRU(maxsize=10)
async def get_vid_id(title, artist, api_key, web_session):
    params = {"q": title + " " + artist, "key": api_key, "part": "snippet"}
    url = constants.Youtube_api + "search"
    async with web_session.get(url, params=params) as resp:
        data = await resp.json()
        
    if "error" in data:
        print(data["error"])
        return

    for i in data["items"]:
        title_api = html.unescape(i["snippet"]["title"])
        artist_api = html.unescape(i["snippet"]["channelTitle"])
        if title_api == title and artist_api == artist:
            return i["id"]["videoId"]
    return


@listToTuple
@AsyncTTL(time_to_live=300, maxsize=5)
async def get_segments(vid_id, web_session, categories=["sponsor"]):
    vid_id_hashed = sha256(vid_id.encode("utf-8")).hexdigest()[
        :4
    ]  # Hashes video id and get the first 4 characters
    params = {
        "category": categories,
        "actionType": constants.SponsorBlock_actiontype,
        "service": constants.SponsorBlock_service,
    }
    headers = {"Accept": "application/json"}
    url = constants.SponsorBlock_api + "skipSegments/" + vid_id_hashed
    async with web_session.get(url, headers=headers, params=params) as response:
        response = await response.json()
    for i in response:
        if str(i["videoID"]) == str(vid_id):
            response = i
            break
    segments = []
    try:
        for i in response["segments"]:
            segment = i["segment"]
            UUID = i["UUID"]
            segment_dict = {"start": segment[0], "end": segment[1], "UUID": [UUID]}
            try:
                # Get segment before to check if they are too close to each other
                segment_before_end = segments[-1]["end"]
                segment_before_start = segments[-1]["start"]
                segment_before_UUID = segments[-1]["UUID"]

            except:
                segment_before_end = -10
            if (
                segment_dict["start"] - segment_before_end < 1
            ):  # Less than 1 second appart, combine them and skip them together
                segment_dict["start"] = segment_before_start
                segment_dict["UUID"].append(segment_before_UUID)
                segments.pop()
            segments.append(segment_dict)
    except:
        pass
    return segments


async def viewed_segments(UUID, web_session):
    url = constants.SponsorBlock_api + "viewedVideoSponsorTime/"
    for i in UUID:
        create_task(mark_viewed_segment(i, web_session))
    return


async def mark_viewed_segment(UUID, web_session):
    url = constants.SponsorBlock_api + "viewedVideoSponsorTime/"
    params = {"UUID": UUID}
    async with web_session.post(url, params=params) as response:
        response_text = await response.text()
    return
