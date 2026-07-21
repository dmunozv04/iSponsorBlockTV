# MQTT notifications + Home Assistant integration - design & build plan

Status: draft. Target: a new opt-in feature that publishes iSponsorBlockTV
events over MQTT, with an optional Home Assistant MQTT Discovery layer so the
events become native HA entities with zero YAML.

## Goal

Emit events (segment skipped, ad muted/skipped, now playing, device
connect/disconnect) so external automation can react - primarily Home Assistant,
but any MQTT consumer benefits. The headline use case: HA fires a notification to
a TV when a sponsor segment is skipped.

## Principles (what keeps this upstream-mergeable)

- **Off by default, zero impact.** Existing users see no change; nothing connects
  unless explicitly enabled.
- **No broker bundled.** iSponsorBlockTV is only a _publisher_; it connects
  outbound to an existing broker (the user's Mosquitto). Flow: iSB-TV -> broker <- HA.
- **Provider-neutral core.** Layer 1 is plain MQTT topics usable by anyone
  (Node-RED, manual HA config, etc.). Home Assistant Discovery is an opt-in
  _layer 2_ on top - so the core is not HA-specific.
- **Lazy import.** The MQTT client is imported only when enabled, so disabled
  installs pay nothing at runtime.
- **Async-native.** Use `aiomqtt` (asyncio, thin wrapper over paho) to match the
  existing aiohttp/asyncio model - no threads.

## Two-layer config (config.json)

```json
"mqtt": {
    "enabled": false,
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

- `mqtt.enabled` (layer 1) - connect to the broker and publish raw event/state topics.
- `mqtt.home_assistant.enabled` (layer 2, requires layer 1) - additionally publish
  retained HA Discovery config topics. If set while `mqtt.enabled` is false, warn
  and treat MQTT as disabled.

`Config.__load()` already maps any config.json key onto an attribute and `save()`
round-trips it, so the block drops in with only default values + validation added
in `helpers.Config`.

## Event catalog (grounded in the current code)

| Event                                      | Fields                                     | Source hook                                                              |
| ------------------------------------------ | ------------------------------------------ | ------------------------------------------------------------------------ |
| `segment_skipped`                          | device, video_id, category, from, to, uuid | `main.py` `DeviceListener.skip()`                                        |
| `ad_started` / `ad_ended`                  | device, video_id                           | `ytlounge._process_event` mute branches (`onAdStateChange`, `adPlaying`) |
| `ad_skipped`                               | device, video_id                           | `ytlounge._process_event` skip-ad branch                                 |
| `now_playing`                              | device, video_id, duration, state          | `_handle_now_playing_event` -> `process_playstatus()`                    |
| `device_connected` / `device_disconnected` | device, screen_name                        | `loop()` connect + `loungeScreenDisconnected`                            |

`device` = a stable id derived from the configured device (slug of `screen_id`,
with the human `name` carried as an attribute).

Open item: pyytlounge exposes `video_id` but not the title/channel. v1 publishes
`video_id`; optional title resolution via the YouTube Data API (only when
`apikey` is set) is a later enhancement.

## MQTT topic layout (layer 1, provider-neutral)

- Base: `base_topic` (default `isponsorblocktv`).
- Availability (LWT): `isponsorblocktv/<device_id>/availability` -> `online`/`offline`.
- Events: `isponsorblocktv/<device_id>/event` -> `{"event_type": "...", ...fields}`.
- State (retained): `isponsorblocktv/<device_id>/now_playing`,
  `.../connected`, `.../segments_skipped`.

## Home Assistant Discovery (layer 2)

- Prefix: `discovery_prefix` (default `homeassistant`).
- One HA _device_ per configured YouTube TV device (identifiers from `screen_id`,
  name from the device `name`), so all entities group under it.
- Entities (retained config topics, published once on connect):
  - **event** - `event_types: [segment_skipped, ad_started, ad_skipped, ad_ended]`;
    state topic = the event topic above. This is the entity automations trigger on.
  - **sensor** `now_playing` - state = video_id, attrs: duration, state.
  - **sensor** `segments_skipped` - running counter (only when `skip_count_tracking`).
  - **binary_sensor** `connected` - device link state, uses the availability topic.
- Availability wired via the LWT topic so entities show unavailable when iSB-TV is down.

## Code structure

- New module `src/iSponsorBlockTV/notifications.py`:
  - `Notifier` with `async start()`, `async stop()`, and
    `emit(event_type: str, device, **fields)`.
  - Owns the `aiomqtt` client + a background publish/connection task, LWT,
    discovery publishing. No-op cheaply when disabled.
- `helpers.Config`: add `mqtt` defaults + `validate()` checks (types, layer-2
  requires layer-1).
- `main.main_async`: if `config.mqtt.enabled`, lazily import + construct the
  `Notifier`, `await notifier.start()`, pass it into each `DeviceListener`;
  ensure `stop()` in the finish/teardown path.
- `main.DeviceListener`: accept `notifier`; emit `device_connected` (after the
  "Connected to device" log), `now_playing` (in `process_playstatus`),
  `segment_skipped` (in `skip()`), `device_disconnected` on teardown.
- `ytlounge.YtLoungeApi`: accept `notifier`; emit `ad_started`/`ad_ended`/
  `ad_skipped` from the corresponding `_process_event` branches.
- Setup wizard (`setup_wizard.py`): optional MQTT config screen (can land after a
  manual-config-first v1).
- Deps: add `aiomqtt` (v1: regular dependency, lazily imported; optional
  `[mqtt]` extra is a possible follow-up if upstream wants zero footprint).

## Build plan (phased, each independently testable)

1. Config plumbing - `mqtt` block, defaults, validation. No behavior change.
2. `Notifier` (layer 1) - connect, LWT, publish event + state topics.
3. Wire `emit()` into `DeviceListener` + `YtLoungeApi` hooks.
4. HA Discovery (layer 2) - retained config topics + entities + availability.
5. Setup wizard screen (optional).
6. Docs - README section, wiki, update `config.json.template`.

## Testing (live)

- Point the service config at an MQTT broker with `mqtt.enabled=true` and
  `home_assistant.enabled=true`.
- Watch the HA MQTT device appear; play a video on the TV; confirm the `event`
  entity fires `segment_skipped`; build an automation to notify a TV (e.g. LG webOS).

## Open decisions

1. **now_playing detail** - v1 `video_id` only, or add optional YouTube-API title
   resolution when `apikey` is set?
2. **aiomqtt packaging** - regular dependency (simplest, chosen for v1) vs an
   optional `[mqtt]` extra (zero footprint for non-users, more build work across
   PyPI / Docker / pyapp / HA add-on).
