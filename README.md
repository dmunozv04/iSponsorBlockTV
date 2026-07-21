# iSponsorBlockTV

[![ghcr.io Pulls](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fipitio.github.io%2Fbackage%2Fdmunozv04%2FiSponsorBlockTV%2Fisponsorblocktv.json&query=downloads&logo=github&label=ghcr.io%20pulls&style=flat)](https://ghcr.io/dmunozv04/isponsorblocktv)
[![Docker Pulls](https://img.shields.io/docker/pulls/dmunozv04/isponsorblocktv?logo=docker&style=flat)](https://hub.docker.com/r/dmunozv04/isponsorblocktv/)
[![GitHub Release](https://img.shields.io/github/v/release/dmunozv04/isponsorblocktv?logo=GitHub&style=flat)](https://github.com/dmunozv04/iSponsorBlockTV/releases/latest)
[![GitHub Repo stars](https://img.shields.io/github/stars/dmunozv04/isponsorblocktv?style=flat)](https://github.com/dmunozv04/isponsorblocktv)

iSponsorBlockTV is a self-hosted application that connects to your YouTube TV
app (see compatibility below) and automatically skips segments (like Sponsors
or intros) in YouTube videos using the [SponsorBlock](https://sponsor.ajay.app/)
API. It can also auto mute and press the "Skip Ad" button the moment it becomes
available on YouTube ads.

> [!WARNING]
> YouTube appers to have changed the screen ID code format and is in the process
> of revoking all existing codes. This means that you'll have to pair your
> device again. You can find information on how to do that in the wiki.

## Installation

Check the [wiki](https://github.com/dmunozv04/iSponsorBlockTV/wiki/Installation)

## Compatibility

Legend: ✅ = Working, ❌ = Not working, ❔ = Not tested

Open an issue/pull request if you have tested a device that isn't listed here.

| Device             | Status |
| :----------------- | :----: |
| Apple TV           |  ✅*   |
| Samsung TV (Tizen) |   ✅   |
| LG TV (WebOS)      |   ✅   |
| Android TV         |   ✅   |
| Chromecast         |   ✅   |
| Google TV          |   ✅   |
| Roku               |   ✅   |
| Fire TV            |   ✅   |
| CCwGTV             |   ✅   |
| Nintendo Switch    |   ✅   |
| Xbox One/Series    |   ✅   |
| Playstation 4/5    |   ✅   |

*Ad muting won't work when using AirPlay to send the audio to another speaker.

** Shorts aren't fully supported due to limitations on YouTube's side.
A single short can be seen by either selecting the "Disconnect" option in the
warning shown
or by long pressing the thumbnail to open the menu and clicking play from there

## Usage

Run iSponsorBlockTV on a computer that has network access. It doesn't need to
be on the same network as the device, only access to youtube.com is required.

Auto discovery will require the computer to be on the same network as the device
during setup.
The device can also be manually added to iSponsorBlockTV with a YouTube TV code.
This code can be found in the settings page of your YouTube TV application.

## MQTT / Home Assistant

iSponsorBlockTV can publish what it does over MQTT so other systems can react to
it. This is **opt-in and off by default** - existing setups are unaffected.

Enable it in the config wizard (`setup` / `setup-cli`) or add an `mqtt` block to
`config.json`:

```json
"mqtt": {
    "enabled": true,
    "broker": "mqtt.example.lan",
    "port": 1883,
    "username": "",
    "password": "",
    "tls": false,
    "base_topic": "isponsorblocktv",
    "home_assistant": {
        "enabled": true,
        "discovery_prefix": "homeassistant"
    }
}
```

- `mqtt.enabled` publishes provider-neutral topics under `base_topic` (usable by
  any MQTT consumer). Events are published as JSON to
  `<base_topic>/<device>/event`, retained state to `.../now_playing`,
  `.../segments_skipped` and `.../connected`, and process availability to
  `<base_topic>/availability`.
- `mqtt.home_assistant.enabled` additionally publishes
  [MQTT Discovery](https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery)
  configs so Home Assistant auto-creates, per YouTube TV device, an **event**
  entity (fires `segment_skipped`, `ad_started`, `ad_ended`, `ad_skipped`),
  **now playing** and **segments skipped** sensors, and a **connected** binary
  sensor - no YAML required. It needs an MQTT broker that both this app and Home
  Assistant can reach (for example the Mosquitto add-on).

The MQTT client (`aiomqtt`) is only imported when MQTT is enabled.

## Libraries used

- [pyytlounge](https://github.com/FabioGNR/pyytlounge) Used to interact with the
  device
- asyncio and [aiohttp](https://github.com/aio-libs/aiohttp)
- [async-cache](https://github.com/iamsinghrajat/async-cache)
- [Textual](https://github.com/textualize/textual/) Used for the amazing new
  graphical configurator
- [ssdp](https://github.com/codingjoe/ssdp) Used for auto discovery
- [aiomqtt](https://github.com/empicano/aiomqtt) Used for the optional MQTT /
  Home Assistant integration

## Projects using this project

- [Home Assistant Addon](https://github.com/bertybuttface/addons/tree/main/isponsorblocktv)

## Contributing

1. Fork it (<https://github.com/dmunozv04/iSponsorBlockTV/fork>)
2. Create your feature branch (`git checkout -b my-new-feature`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin my-new-feature`)
5. Create a new Pull Request

## Contributors

[![Contributors](https://contrib.rocks/image?repo=dmunozv04/iSponsorBlockTV)](https://github.com/dmunozv04/iSponsorBlockTV/graphs/contributors)

Made with [contrib.rocks](https://contrib.rocks).

## License

[![GNU GPLv3](https://www.gnu.org/graphics/gplv3-127x51.png)](https://www.gnu.org/licenses/gpl-3.0.en.html)
