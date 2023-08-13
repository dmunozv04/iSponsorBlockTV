# iSponsorBlockTV

Skip sponsor segments in YouTube videos playing on an Apple TV. Sponsor Block in YouTube for apple TV

This project is written in asycronous python and should be pretty quick.

# Installation
Check the [wiki](https://github.com/dmunozv04/iSponsorBlockTV/wiki/Installation)

Warning: armv7 builds have been deprecated.

# Usage

Run iSponsorBLockTV on the same network as the Apple TV.

It connects to the Apple TV, watches its activity and skips any sponsor segment using the [SponsorBlock](https://sponsor.ajay.app/) API.

The Apple TV does not communicate the YouTube video ID directly, and a YouTube Data API key is needed to get the video ID from the video title and author that Apple TV provides.

The last 5 videos' segments are cached to limit the number on queries on SponsorBlock and YouTube.


# Libraries used
- [pyatv](https://github.com/postlund/pyatv) Used to connect to the Apple TV
- asyncio and [aiohttp](https://github.com/aio-libs/aiohttp)
- [async-cache](https://github.com/iamsinghrajat/async-cache)

# Projects using this proect
- [Home Assistant Addon](https://github.com/bertybuttface/addons/tree/main/isponsorblocktv)

# Contributing

1. Fork it (<https://github.com/dmunozv04/iSponsorBlockTV/fork>)
2. Create your feature branch (`git checkout -b my-new-feature`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin my-new-feature`)
5. Create a new Pull Request

## Contributors

- [dmunozv04](https://github.com/dmunozv04) - creator and maintainer
- [HaltCatchFire](https://github.com/HaltCatchFire) - updated dependencies and improved skip logic
- [Oxixes](https://github.com/oxixes) - added support for channel whitelist and minor improvements
# License
[![GNU GPLv3](https://www.gnu.org/graphics/gplv3-127x51.png)](https://www.gnu.org/licenses/gpl-3.0.en.html)
