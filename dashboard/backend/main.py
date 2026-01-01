from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import json
import os
import sys
import aiohttp
import traceback

sys.path.append("/app/src")
try:
    from iSponsorBlockTV.ytlounge import YtLoungeApi
except ImportError:
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), "../../src"))
        from iSponsorBlockTV.ytlounge import YtLoungeApi
    except ImportError:
        print("Warning: Could not import YtLoungeApi. Pairing will fail.")
        YtLoungeApi = None

try:
    from iSponsorBlockTV.api_helpers import ApiHelper
    from iSponsorBlockTV.helpers import Config
except ImportError:
    print("Error importing ApiHelper or Config:")
    traceback.print_exc()
    ApiHelper = None
    Config = None

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


app.mount("/assets", StaticFiles(directory="/app/static/assets"), name="assets")

@app.post("/api/pair")
async def pair_device(data: dict):
    code = data.get("code")
    name = data.get("name")
    offset = data.get("offset", 0)

    if not code:
        raise HTTPException(status_code=400, detail="Pairing code required")

    try:
        try:
            pairing_code = int(str(code).replace("-", "").replace(" ", ""))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid pairing code format. Digits only.")

        try:
            offset = int(offset)
        except (ValueError, TypeError):
            offset = 0

        async with aiohttp.ClientSession() as session:
            api = YtLoungeApi(screen_id=None, config=None, api_helper=None)
            await api.change_web_session(session)

            try:
                paired = await api.pair(pairing_code)
            except Exception as e:
                err_msg = str(e)
                if "404" in err_msg:
                    raise HTTPException(
                        status_code=400, detail="Invalid pairing code or code expired."
                    )
                raise e

            if not paired:
                raise HTTPException(
                    status_code=400, detail="Pairing failed. Check code and try again."
                )

            return {
                "name": name if name else api.screen_name,
                "screen_id": api.auth.screen_id,
                "offset": offset,
            }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Pairing error: {e}")
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")


@app.get("/api/channels/search")
async def search_channels(query: str):
    if not query:
        return []

    current_apikey = None
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                config_data = json.load(f)
                current_apikey = config_data.get("apikey")
        except Exception:
            pass

    if not current_apikey:
        raise HTTPException(status_code=400, detail="API Key is missing from backend config")

    if not ApiHelper:
        raise HTTPException(
            status_code=500, detail="Backend not properly initialized (ApiHelper missing)"
        )

    class MockConfig:
        def __init__(self, key):
            self.apikey = key
            self.skip_categories = []
            self.channel_whitelist = []
            self.skip_count_tracking = False
            self.devices = []
            self.minimum_skip_length = 0

    mock_config = MockConfig(current_apikey)

    async with aiohttp.ClientSession() as session:
        api = ApiHelper(mock_config, session)
        try:
            results = await api.search_channels(query)
            formatted_results = [{"id": r[0], "name": r[1], "subscribers": r[2]} for r in results]
            return formatted_results
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            print(f"Search error: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    if full_path.startswith("api"):
        raise HTTPException(status_code=404)
    if os.path.exists(f"/app/static/{full_path}") and full_path != "":
        return FileResponse(f"/app/static/{full_path}")
    return FileResponse("/app/static/index.html")
