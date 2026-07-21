"""MQTT notifications for iSponsorBlockTV (opt-in, off by default).

This module is the provider-neutral layer: it connects to an existing MQTT
broker and publishes events/state. Home Assistant discovery is layered on top
separately. It is imported lazily (only when ``mqtt.enabled``), so disabled
installs never load ``aiomqtt``.

``emit()`` is fire-and-forget - it only enqueues, so it never blocks or raises
in the playback hot path. A single background task owns the connection and
publishes from the queue, reconnecting as needed. Availability uses an MQTT
Last Will so consumers see the client go offline on an unclean exit.
"""

import asyncio
import json
import logging
import re
from typing import Optional

import aiomqtt

_INVALID = re.compile(r"[^a-zA-Z0-9_-]+")


def slugify(value: str) -> str:
    """Stable, topic-safe id from a screen id / name."""
    slug = _INVALID.sub("_", str(value)).strip("_").lower()
    return slug or "device"


def _device_list(config):
    """Extract (screen_id, name) pairs from config.devices (dicts or objects)."""
    result = []
    for d in getattr(config, "devices", None) or []:
        if isinstance(d, dict):
            screen_id, name = d.get("screen_id"), d.get("name")
        else:
            screen_id, name = getattr(d, "screen_id", None), getattr(d, "name", None)
        if screen_id:
            result.append((screen_id, name))
    return result


class Notifier:
    QUEUE_MAXSIZE = 200
    RECONNECT_DELAY = 10  # seconds between reconnect attempts

    def __init__(self, config, logger: Optional[logging.Logger] = None):
        mqtt = getattr(config, "mqtt", {}) or {}
        self.enabled: bool = bool(mqtt.get("enabled"))
        self._broker: str = mqtt.get("broker") or ""
        self._port: int = int(mqtt.get("port", 1883))
        self._username: Optional[str] = mqtt.get("username") or None
        self._password: Optional[str] = mqtt.get("password") or None
        self._tls: bool = bool(mqtt.get("tls"))
        self._base_topic: str = (mqtt.get("base_topic") or "isponsorblocktv").strip("/")
        self._client_id: str = f"isponsorblocktv-{slugify(self._base_topic)}"
        self.logger = logger or logging.getLogger("iSponsorBlockTV-mqtt")

        ha = mqtt.get("home_assistant") or {}
        self._ha_enabled: bool = self.enabled and bool(ha.get("enabled"))
        self._discovery_prefix: str = (ha.get("discovery_prefix") or "homeassistant").strip("/")
        self._devices = _device_list(config)

        self._queue: asyncio.Queue = asyncio.Queue(maxsize=self.QUEUE_MAXSIZE)
        self._task: Optional[asyncio.Task] = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._skip_counts: dict = {}
        self._state: dict = {}

    @property
    def availability_topic(self) -> str:
        return f"{self._base_topic}/availability"

    def event_topic(self, device_id: str) -> str:
        return f"{self._base_topic}/{device_id}/event"

    async def start(self) -> None:
        if not self.enabled:
            return
        if not self._broker:
            self.logger.warning("MQTT enabled but no broker configured; not connecting")
            self.enabled = False
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())
        self.logger.debug("MQTT notifier started (broker %s:%s)", self._broker, self._port)

    async def stop(self) -> None:
        if not self._task:
            return
        self._stop_event.set()
        try:
            # Give the loop a moment to publish "offline" and disconnect cleanly.
            await asyncio.wait_for(asyncio.shield(self._task), timeout=6)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        except Exception:
            pass

    def emit(
        self,
        event_type: str,
        device_id: str,
        device_name: Optional[str] = None,
        **fields,
    ) -> None:
        """Enqueue an event for publication. Fire-and-forget: never blocks/raises."""
        if not self.enabled:
            return
        did = slugify(device_id)
        payload = {"event_type": event_type, "device": device_name or did}
        payload.update({k: v for k, v in fields.items() if v is not None})
        self._enqueue(self.event_topic(did), json.dumps(payload), retain=False)
        self._update_state(did, event_type)

    def _enqueue(self, topic: str, payload: str, retain: bool = False) -> None:
        try:
            self._queue.put_nowait((topic, payload, retain))
        except asyncio.QueueFull:
            self.logger.debug("MQTT queue full; dropping message to %s", topic)

    def _publish_state(self, topic: str, payload: str) -> None:
        # Retained state, remembered so it can be re-published after a reconnect
        # (in case the broker lost its retained messages).
        self._state[topic] = payload
        self._enqueue(topic, payload, retain=True)

    def _update_state(self, device_id: str, event_type: str) -> None:
        base = f"{self._base_topic}/{device_id}"
        if event_type == "segment_skipped":
            self._skip_counts[device_id] = self._skip_counts.get(device_id, 0) + 1
            self._publish_state(f"{base}/segments_skipped", str(self._skip_counts[device_id]))
        elif event_type == "device_connected":
            self._publish_state(f"{base}/connected", "ON")
        elif event_type == "device_disconnected":
            self._publish_state(f"{base}/connected", "OFF")

    def set_title(self, device_id: str, value: str) -> None:
        """Set the title sensor state - the resolved video title (or the raw video id
        until it resolves), or an empty string when playback stops. Fire-and-forget;
        no-op when disabled."""
        if not self.enabled:
            return
        self._publish_state(f"{self._base_topic}/{slugify(device_id)}/title", str(value))

    def set_playback_state(self, device_id: str, value: str) -> None:
        """Set the playback_state sensor (playing / paused / stopped / ...).
        Fire-and-forget; no-op when disabled."""
        if not self.enabled:
            return
        self._publish_state(f"{self._base_topic}/{slugify(device_id)}/playback_state", str(value))

    def set_channel(self, device_id: str, value: str) -> None:
        """Set the channel sensor - the resolved channel name, or an empty string
        when idle. Fire-and-forget; no-op when disabled."""
        if not self.enabled:
            return
        self._publish_state(f"{self._base_topic}/{slugify(device_id)}/channel", str(value))

    async def _run(self) -> None:
        will = aiomqtt.Will(topic=self.availability_topic, payload="offline", qos=1, retain=True)
        tls_params = aiomqtt.TLSParameters() if self._tls else None
        while not self._stop_event.is_set():
            try:
                async with aiomqtt.Client(
                    hostname=self._broker,
                    port=self._port,
                    username=self._username,
                    password=self._password,
                    identifier=self._client_id,
                    will=will,
                    tls_params=tls_params,
                ) as client:
                    self.logger.info("Connected to MQTT broker %s:%s", self._broker, self._port)
                    await client.publish(self.availability_topic, "online", qos=1, retain=True)
                    await self._publish_discovery(client)
                    await self._republish_state(client)
                    await self._drain(client)
                    if self._stop_event.is_set():
                        # Graceful shutdown: mark offline before the clean disconnect
                        # (the Last Will only fires on an unclean disconnect).
                        await client.publish(self.availability_topic, "offline", qos=1, retain=True)
                        return
            # No explicit CancelledError handler: it subclasses BaseException, so it is
            # not caught below and propagates naturally to end the task on cancellation.
            except aiomqtt.MqttError as e:
                self.logger.warning(
                    "MQTT connection error (%s); reconnecting in %ss",
                    e,
                    self.RECONNECT_DELAY,
                )
            except Exception as e:  # noqa: BLE001 - never let the loop die
                self.logger.warning(
                    "MQTT unexpected error (%s); reconnecting in %ss",
                    e,
                    self.RECONNECT_DELAY,
                )
            if not self._stop_event.is_set():
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.RECONNECT_DELAY)
                except asyncio.TimeoutError:
                    pass

    async def _drain(self, client) -> None:
        """Publish queued messages until stop is requested or the connection drops."""
        stop_wait = asyncio.ensure_future(self._stop_event.wait())
        try:
            while not self._stop_event.is_set():
                get_fut = asyncio.ensure_future(self._queue.get())
                done, _ = await asyncio.wait(
                    {get_fut, stop_wait}, return_when=asyncio.FIRST_COMPLETED
                )
                if get_fut in done:
                    topic, payload, retain = get_fut.result()
                    # A failed publish raises MqttError, which unwinds to _run and
                    # triggers a reconnect; the in-flight message is dropped.
                    await client.publish(topic, payload, qos=0, retain=retain)
                else:
                    get_fut.cancel()
                    return
        finally:
            stop_wait.cancel()

    async def _publish_discovery(self, client) -> None:
        if not self._ha_enabled or not self._devices:
            return
        from . import homeassistant  # isolate the HA-specific config building

        count = 0
        for screen_id, name in self._devices:
            for topic, payload in homeassistant.discovery_messages(
                self._discovery_prefix,
                self._base_topic,
                self.availability_topic,
                slugify(screen_id),
                name,
            ):
                await client.publish(topic, payload, qos=1, retain=True)
                count += 1
        self.logger.info(
            "Published Home Assistant discovery: %d entities across %d device(s)",
            count,
            len(self._devices),
        )

    async def _republish_state(self, client) -> None:
        for topic, payload in list(self._state.items()):
            await client.publish(topic, payload, qos=0, retain=True)
