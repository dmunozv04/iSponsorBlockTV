"""Entry point for the web interface."""

import os
import uvicorn


def main():
    """Start the web server."""
    port = int(os.getenv("ISPONSORBLOCKTV_PORT", "42069"))
    host = os.getenv("ISPONSORBLOCKTV_HOST", "0.0.0.0")
    
    uvicorn.run(
        "iSponsorBlockTV.web.api:app",
        host=host,
        port=port,
        reload=os.getenv("ISPONSORBLOCKTV_DEV", "").lower() == "true",
    )


if __name__ == "__main__":
    main()
