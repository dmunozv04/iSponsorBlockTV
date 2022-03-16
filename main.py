import sys
import asyncio
import pyatv
import aiohttp
from cache import AsyncTTL
import json
import atexit


def listToTuple(function):
    def wrapper(*args):
        args = [tuple(x) if type(x) == list else x for x in args]
        result = function(*args)
        result = tuple(result) if type(result) == list else result
        return result
    return wrapper

class MyPushListener(pyatv.interface.PushListener):
    task = None
    apikey = None
    rc = None
    
    web_session = None
    categories = ["sponsor"]

    def __init__(self, apikey, atv, categories):
        self.apikey = apikey
        self.rc = atv.remote_control
        self.web_session = aiohttp.ClientSession()
        self.categories = categories
        self.atv = atv
        
    
    def playstatus_update(self, updater, playstatus):
        try:
            self.task.cancel()
        except:
            pass
        self.task = asyncio.create_task(process_playstatus(playstatus, self.apikey, self.rc, self.web_session, self.categories, self.atv))
    def playstatus_error(self, updater, exception):
        print(exception)
        print("stopped")

        

async def process_playstatus(playstatus, apikey, rc, web_session, categories, atv):
    if playstatus.device_state == playstatus.device_state.Playing and atv.metadata.app.identifier == "com.google.ios.youtube":
        vid_id = await get_vid_id(playstatus.title, playstatus.artist, apikey, web_session)
        print(vid_id)
        segments, duration = await get_segments(vid_id, web_session, categories)
        print(segments)
        await time_to_segment(segments, playstatus.position, rc)
        

@AsyncTTL(time_to_live=300, maxsize=5)
async def get_vid_id(title, artist, api_key, web_session):
    url = f"https://youtube.googleapis.com/youtube/v3/search?q={title} - {artist}&key={api_key}&maxResults=1"
    async with web_session.get(url) as response:
        response = await response.json()
        vid_id = response["items"][0]["id"]["videoId"]
        return vid_id

@listToTuple
@AsyncTTL(time_to_live=300, maxsize=5)
async def get_segments(vid_id, web_session, categories = ["sponsor"]):
    params = {"videoID": vid_id,
              "category": categories,
              "actionType": "skip",
              "service": "youtube"}
    headers = {'Accept': 'application/json'}
    url = "https://sponsor.ajay.app/api/skipSegments"
    async with web_session.get(url, headers = headers, params = params) as response:
        response = await response.json()
        segments = []
        try:
            duration = response[0]["videoDuration"]
            for i in response:
                segments.append(i["segment"])
        except:
            duration = 0
    return segments, duration


async def time_to_segment(segments, position, rc):
    for segment in segments:
        if position < 2 and (position >= segment[0] and position < segment[1]):
            next_segment = [position, segment[1]]
            break
        if segment[0] > position:
            next_segment = segment
            break
    time_to_next = next_segment[0] - position
    await skip(time_to_next, next_segment[1], rc)

async def skip(time_to, position, rc):
    await asyncio.sleep(time_to)
    await rc.set_position(position)


async def connect_atv(loop, identifier, airplay_credentials):
    """Find a device and print what is playing."""
    print("Discovering devices on network...")
    atvs = await pyatv.scan(loop, identifier = identifier)

    if not atvs:
        print("No device found, will retry")
        return

    config = atvs[0]
    config.set_credentials(pyatv.Protocol.AirPlay, airplay_credentials)

    print(f"Connecting to {config.address}")
    return await pyatv.connect(config, loop)


async def loop_atv(event_loop, atv_config, apikey, categories):
    identifier = atv_config["identifier"]
    airplay_credentials = atv_config["airplay_credentials"]
    atv = await connect_atv(event_loop, identifier, airplay_credentials)
    if atv:
        listener = MyPushListener(apikey, atv, categories)

        atv.push_updater.listener = listener
        atv.push_updater.start()
        print("Push updater started")
    while True:
        await asyncio.sleep(20)
        try:
            atv.metadata.app
        except:
            print("Reconnecting to Apple TV")
            #reconnect to apple tv
            atv = await connect_atv(event_loop, identifier, airplay_credentials)
            if atv:
                listener = MyPushListener(apikey, atv, categories)

                atv.push_updater.listener = listener
                atv.push_updater.start()
                print("Push updater started")
            
            
            


def load_config(config_file="config.json"):
    with open(config_file) as f:
        config = json.load(f)
    return config["atvs"], config["apikey"], config["skip_categories"]
  
def start_async():
    loop = asyncio.get_event_loop_policy().get_event_loop()
    asyncio.set_event_loop(loop)
    atv_configs, apikey, categories = load_config()
    for i in atv_configs:
        loop.create_task(loop_atv(loop, i, apikey, categories))
    loop.run_forever()
              
if __name__ == "__main__":
    print("starting")
    start_async()
