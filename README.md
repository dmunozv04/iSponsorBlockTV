# iSponsorBlockTV

Skip sponsor segments in YouTube videos playing on an Apple TV.

This project is written in asycronous python and should be pretty quick.

# Installation

## Docker
### Setup

You need to set up several things before you can run the project.
Create blank config file: `touch config.json`
Run:
```sh
docker run --rm -it \
--network=host \
--entrypoint /opt/venv/bin/python3 \
-v /PATH_TO_YOUR_CONFIG.json:/app/config.json \
ghcr.io/dmunozv04/isponsorblocktv \
/app/create_config.py
```
## Run
```sh
docker pull ghcr.io/dmunozv04/isponsorblocktv
docker run -d \
--name iSponsorBlockTV \
--restart=unless-stopped \
--network=host \
-v /PATH_TO_YOUR_CONFIG.json:/app/config.json \
ghcr.io/dmunozv04/isponsorblocktv
```
## From source

You need to install [python](https://www.python.org/downloads/) first, and to make it available in your PATH. After, clone the repo.
Then you need to download the dependencies with pip: 
```python3 -m pip install -r requirements.txt```
Lastly, run ```main.py```

### Setup

You need to retrieve airplay keys to be able to connect to the Apple TV. (It will be made simpler in the future)
For now, use `atvremote`, a script included in pyatv:
1. atvremote scan
2. atvremote pair --protocol airplay --id `identifier you got on the previous step`

Get  [YouTube api key](https://developers.google.com/youtube/registering_an_application)

Edit config.json.template and save it as config.json
# Usage

Run iSponsorBLockTV in the same network as the Apple TV.

It connect to the Apple TV, watch its activity and skip any sponsor segment using the [SponsorBlock](https://sponsor.ajay.app/) API.

The last 5 videos' segments are cached to limit the number on queries on SponsorBlock and YouTube.


# Libraries used
- [pyatv](https://github.com/postlund/pyatv) Used to connect to the Apple TV
- [asyncio] and [aiohttp]
- [async_lru]
- [json]

# Contributing

1. Fork it (<https://github.com/dmunozv04/iSponsorBlockTV/fork>)
2. Create your feature branch (`git checkout -b my-new-feature`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin my-new-feature`)
5. Create a new Pull Request

## Contributors

- [dmunozv04](https://github.com/dmunozv04) - creator and maintainer
- [HaltCatchFire](https://github.com/HaltCatchFire) - updated dependencies and improved skip logic
# License
[![GNU GPLv3](https://www.gnu.org/graphics/gplv3-127x51.png)](https://www.gnu.org/licenses/gpl-3.0.en.html)
