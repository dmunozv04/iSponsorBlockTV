import asyncio
import time

from aiohttp import ClientSession

# Class that handles webhooks
class WebhookHelper:
    def __init__(self, config, webhook_session: ClientSession) -> None:
        self.webhook_map = {}
        if hasattr(config, 'webhooks'):
            # Group webhooks by event for efficient lookup
            for webhook in config.webhooks:
                event = webhook['event']
                if event not in self.webhook_map:
                    self.webhook_map[event] = []
                self.webhook_map[event].append(webhook)
            print("Webhook map: ", self.webhook_map)
        self.webhook_session = webhook_session

    async def notify_webhook(self, logger, event, **data):
        """Send event and data to all configured webhooks"""
        logger.info("ENTERED notify_webhook")  # Add this line
        if event not in self.webhook_map:
            logger.debug(f"No webhooks set for event {event}")
            return

        webhook_data = {
            "event": event,
            "timestamp": time.time(),
            **data
        }

        logger.debug(f"Building webhook requests for {event} with data: {webhook_data}")
        # Create requests for all webhooks
        requests = [
            self._send_webhook(logger, webhook_config, webhook_data)
            for webhook_config in self.webhook_map[event]
            if webhook_config.get('url')
        ]
        logger.debug(f"Sending {len(requests)} webhooks for event {event}")
        
        if requests:
            # Let aiohttp handle connection pooling while we execute concurrently
            await asyncio.gather(*requests, return_exceptions=True)

    async def _send_webhook(self, logger, webhook_config, webhook_data):
        """Helper method to send individual webhook request"""
        event = webhook_data['event']
        url = webhook_config['url']
        logger.debug(f"Sending webhook {event} to {url}")
        try:
            async with self.webhook_session.request(
                webhook_config.get('method', 'POST'),
                url,
                json=webhook_data,
                headers=webhook_config.get('headers', {}),
                timeout=5
            ) as response:
                if response.status not in (200, 201, 204):
                    logger.warning(f"Webhook {event} to {url} failed (status: {response.status})")
                else:
                    logger.debug(f"Webhook {event} to {url} successfully sent")
        except Exception as e:
            logger.warning(f"Failed to send webhook {event} to {url}: {str(e)}")
            raise
