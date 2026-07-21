"""Home Assistant MQTT Discovery config builder (opt-in layer 2).

Kept separate from the provider-neutral MQTT publisher (``notifications.py``) so
the core stays Home Assistant-agnostic. Given a device, this produces the
retained discovery config messages that make Home Assistant auto-create native
entities pointing at the topics the publisher already uses.
"""

import json

MANUFACTURER = "iSponsorBlockTV"
MODEL = "YouTube TV"

# Event types the `event` entity can fire (must match what the app emits).
EVENT_TYPES = ["segment_skipped", "ad_started", "ad_ended", "ad_skipped"]


def discovery_messages(discovery_prefix, base_topic, availability_topic, device_slug, device_name):
    """Return a list of ``(config_topic, json_payload)`` messages for one device.

    Each message is published retained to its discovery topic so Home Assistant
    creates the entity and groups it under a single device.
    """
    node = f"isponsorblocktv_{device_slug}"
    dev_base = f"{base_topic}/{device_slug}"
    device = {
        "identifiers": [node],
        "name": device_name or device_slug,
        "manufacturer": MANUFACTURER,
        "model": MODEL,
    }
    availability = [
        {
            "topic": availability_topic,
            "payload_available": "online",
            "payload_not_available": "offline",
        }
    ]

    def cfg(component, object_id, extra):
        topic = f"{discovery_prefix}/{component}/{node}/{object_id}/config"
        payload = {
            "unique_id": f"{node}_{object_id}",
            "device": device,
            "availability": availability,
        }
        payload.update(extra)
        return topic, json.dumps(payload)

    return [
        cfg(
            "event",
            "skips",
            {
                "name": "Skips",
                "state_topic": f"{dev_base}/event",
                "event_types": EVENT_TYPES,
                "icon": "mdi:skip-next",
            },
        ),
        cfg(
            "sensor",
            "title",
            {
                "name": "Title",
                "state_topic": f"{dev_base}/title",
                "icon": "mdi:youtube",
            },
        ),
        cfg(
            "sensor",
            "channel",
            {
                "name": "Channel",
                "state_topic": f"{dev_base}/channel",
                "icon": "mdi:account-box",
            },
        ),
        cfg(
            "sensor",
            "playback_state",
            {
                "name": "State",
                "state_topic": f"{dev_base}/playback_state",
                "icon": "mdi:play-pause",
            },
        ),
        cfg(
            "sensor",
            "segments_skipped",
            {
                "name": "Segments skipped",
                "state_topic": f"{dev_base}/segments_skipped",
                "state_class": "total_increasing",
                "icon": "mdi:counter",
            },
        ),
        cfg(
            "binary_sensor",
            "connected",
            {
                "name": "Connected",
                "state_topic": f"{dev_base}/connected",
                "payload_on": "ON",
                "payload_off": "OFF",
                "device_class": "connectivity",
            },
        ),
    ]
