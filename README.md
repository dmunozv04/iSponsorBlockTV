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

> [!NOTE]
> This is an unofficial WebGUI fork of [dmunozv04/iSponsorBlockTV](https://github.com/dmunozv04/iSponsorBlockTV).
> The badges, compatibility information, and contributor credits refer to the upstream project.
> For this fork's image and browser setup, see [WebGUI edition](#webgui-edition).

> [!WARNING]
> YouTube appers to have changed the screen ID code format and is in the process
> of revoking all existing codes. This means that you'll have to pair your
> device again. You can find information on how to do that in the wiki.

## Installation

Check the [wiki](https://github.com/dmunozv04/iSponsorBlockTV/wiki/Installation)
for the original application's installation instructions.

### WebGUI edition

This fork adds a password-protected dashboard, night mode, device enable/pause
controls, playback settings, searchable logs, and automatic configuration backups.
The panel and playback service run together; no Docker socket mount is needed.
It retains upstream ad muting and available ad skips, not full removal of every ad.

**Unraid:** use the [template](templates/isponsorblocktv-web.xml), which includes
the icon and a masked password field, or enter these settings manually:

| Setting | Value |
| --- | --- |
| Repository | `ghcr.io/ss1gohan13/isponsorblocktv:web-gui` |
| Network | `Host` |
| Data mapping | `/mnt/user/appdata/isponsorblocktv/data` → `/app/data` (read/write) |
| `WEB_PASSWORD` | Choose your own password of at least 12 characters |
| `WEB_PORT` | `1166` |
| `ALLOWED_NETWORKS` | Your receiver subnets, e.g. `192.168.0.0/16` |
| WebUI | `http://[IP]:[PORT:1166]/` |

Open `http://YOUR-SERVER-IP:1166`. No `--setup-cli` argument is needed.
To reuse an existing configuration, stop the previous container before starting
this one with the same data directory. Keep the panel on a trusted LAN or use
HTTPS through a reverse proxy.

For Chromecast pairing, actively cast a YouTube video, then use **Search local
network** or enter the receiver's IP and select **Check device**. Across VLANs,
direct-IP pairing needs TCP 8009 access; host mode does not relay discovery.
`ALLOWED_NETWORKS` limits receiver checks, not browser access or firewall rules.
The panel currently pairs Google Cast receivers; other compatible clients can be
imported through an existing upstream configuration. Playback settings apply to
all enabled devices. Backups are stored in `/app/data/web-backups/`.

## Compatibility

Legend: ✅ = Working, ❌ = Not working, ❔ = Not tested

Open an issue/pull request if you have tested a device that isn't listed here.

| Device             | Status |
|:-------------------|:------:|
| Apple TV           |   ✅*   |
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
| Playstation 4/5    |   ✅    |

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

The instructions above describe upstream setup. For this fork's browser-based
Cast pairing, use the [WebGUI edition](#webgui-edition) instructions.

## Libraries used

- [pyytlounge](https://github.com/FabioGNR/pyytlounge) Used to interact with the
  device
- asyncio and [aiohttp](https://github.com/aio-libs/aiohttp)
- [async-cache](https://github.com/iamsinghrajat/async-cache)
- [Textual](https://github.com/textualize/textual/) Used for the amazing new
  graphical configurator
- [ssdp](https://github.com/codingjoe/ssdp) Used for auto discovery
- WebGUI additions: [PyChromecast](https://github.com/home-assistant-libs/pychromecast)
  and [Zeroconf](https://github.com/python-zeroconf/python-zeroconf) for Cast pairing and discovery

## Projects using this project

- [Home Assistant Addon](https://github.com/bertybuttface/addons/tree/main/isponsorblocktv)

## Contributing

For contributions to the original project:

1. Fork it (<https://github.com/dmunozv04/iSponsorBlockTV/fork>)
2. Create your feature branch (`git checkout -b my-new-feature`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin my-new-feature`)
5. Create a new Pull Request

For WebGUI changes, target the `web-gui` branch of
[ss1gohan13/iSponsorBlockTV](https://github.com/ss1gohan13/iSponsorBlockTV).

## Contributors

[![Contributors](https://contrib.rocks/image?repo=dmunozv04/iSponsorBlockTV)](https://github.com/dmunozv04/iSponsorBlockTV/graphs/contributors)

Made with [contrib.rocks](https://contrib.rocks).

## License

[![GNU GPLv3](https://www.gnu.org/graphics/gplv3-127x51.png)](https://www.gnu.org/licenses/gpl-3.0.en.html)
