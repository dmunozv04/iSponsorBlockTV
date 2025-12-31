from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import json
import os

app = FastAPI()

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/app/data/config.json")


@app.get("/api/config")
def get_config():
    if not os.path.exists(CONFIG_PATH):
        if os.path.exists("/app/config.json.template"):
            with open("/app/config.json.template", "r") as f:
                return json.load(f)
        return {}

    try:
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config")
def update_config(config: dict):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=4)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Serve React App
app.mount("/assets", StaticFiles(directory="/app/static/assets"), name="assets")

# Import correct ytlounge from src
import sys

sys.path.append("/app/src")
from iSponsorBlockTV.ytlounge import YtLoungeApi
import asyncio
import aiohttp


@app.post("/api/pair")
async def pair_device(data: dict):
    code = data.get("code")
    name = data.get("name")
    offset = data.get("offset", 0)

    if not code:
        raise HTTPException(status_code=400, detail="Pairing code required")

    try:
        # Sanitize code
        pairing_code = int(str(code).replace("-", "").replace(" ", ""))
        try:
            offset = int(offset)
        except:
            offset = 0

        async with aiohttp.ClientSession() as session:
            api = YtLoungeApi(screen_id=None, config=None, api_helper=None)
            await api.change_web_session(session)

            paired = await api.pair(pairing_code)
            if not paired:
                raise HTTPException(
                    status_code=400, detail="Pairing failed. Check code and try again."
                )

            return {
                "name": name if name else api.screen_name,
                "screen_id": api.auth.screen_id,
                "offset": offset,
            }
    except Exception as e:
        print(f"Pairing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    if full_path.startswith("api"):
        raise HTTPException(status_code=404)
    if os.path.exists(f"/app/static/{full_path}") and full_path != "":
        return FileResponse(f"/app/static/{full_path}")
    return FileResponse("/app/static/index.html")
