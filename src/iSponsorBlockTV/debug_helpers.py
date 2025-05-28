class AiohttpTracer:
    def __init__(self, logger):
        self.logger = logger

    async def on_request_start(self, session, context, params):
        self.logger.debug(f"Request started ({id(context):#x}): {params.method} {params.url}")

    async def on_request_end(self, session, context, params):
        self.logger.debug(f"Request ended ({id(context):#x}): {params.response.status}")

    async def on_request_exception(self, session, context, params):
        self.logger.debug(f"Request exception ({id(context):#x}): {params.exception}")

    async def on_response_chunk_received(self, session, context, params):
        chunk_size = len(params.chunk)
        try:
            # Try to decode as text
            text = params.chunk.decode("utf-8")
            self.logger.debug(f"Response chunk ({id(context):#x}) {chunk_size} bytes: {text}")
        except UnicodeDecodeError:
            # If not valid UTF-8, show as hex
            hex_data = params.chunk.hex()
            self.logger.debug(
                f"Response chunk ({id(context):#x}) ({chunk_size} bytes) [HEX]: {hex_data}"
            )
