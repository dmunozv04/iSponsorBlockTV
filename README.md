# iSponsorBlockTV
Skip sponsor segments in YouTube videos playing on a YouTube TV device (see below for compatibility details).

This project is written in asynchronous python and should be pretty quick.

## Installation
Check the [wiki](https://github.com/dmunozv04/iSponsorBlockTV/wiki/Installation)

Warning: docker armv7 builds have been deprecated. Amd64 and arm64 builds are still available.

## Compatibility
Legend: ✅ = Working, ❌ = Not working, ❔ = Not tested

Open an issue/pull request if you have tested a device that isn't listed here.

| Device             | Status |
|:-------------------|:------:|
| Apple TV           |   ✅    |
| Samsung TV (Tizen) |   ✅    |
| LG TV (WebOS)      |   ✅    |
| Android TV         |   ✅    |
| Chromecast         |   ✅    |
| Google TV          |   ✅    |
| Roku               |   ✅    |
| Fire TV            |   ✅    |
| CCwGTV             |   ✅    |
| Nintendo Switch    |   ✅    |
| Xbox One/Series    |   ✅    |
| Xbox 360           |   ✅    |
| Playstation 4/5    |   ✅    |
| Xfinity            |   ✅    |

## Usage
Run iSponsorBlockTV on a computer that has network access.
Auto discovery will require the computer to be on the same network as the device during setup.
The device can also be manually added to iSponsorBlockTV with a YouTube TV code. This code can be found in the settings page of your YouTube application.

It connects to the device, watches its activity and skips any sponsor segment using the [SponsorBlock](https://sponsor.ajay.app/) API.
It can also skip/mute YouTube ads.

## Libraries used
- [pyytlounge](https://github.com/FabioGNR/pyytlounge) Used to interact with the device
- asyncio and [aiohttp](https://github.com/aio-libs/aiohttp)
- [async-cache](https://github.com/iamsinghrajat/async-cache)
- [Textual](https://github.com/textualize/textual/) Used for the amazing new graphical configurator
- [ssdp](https://github.com/codingjoe/ssdp) Used for auto discovery

## Projects using this project
- [Home Assistant Addon](https://github.com/bertybuttface/addons/tree/main/isponsorblocktv)

## Contributing
1. Fork it (<https://github.com/dmunozv04/iSponsorBlockTV/fork>)
2. Create your feature branch (`git checkout -b my-new-feature`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin my-new-feature`)
5. Create a new Pull Request

## Contributors
- [dmunozv04](https://github.com/dmunozv04) - creator and maintainer
- [HaltCatchFire](https://github.com/HaltCatchFire) - updated dependencies and improved skip logic
- [Oxixes](https://github.com/oxixes) - added support for channel whitelist and minor improvements
## License
[![GNU GPLv3](https://www.gnu.org/graphics/gplv3-127x51.png)](https://www.gnu.org/licenses/gpl-3.0.en.html)
