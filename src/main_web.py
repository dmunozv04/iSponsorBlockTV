import os
from textual_serve.server import Server

command    = "python3 main_tui.py"
host       = os.environ.get("WEB_HOST", "127.0.0.1")
port       = int(os.environ.get("WEB_PORT", 8000))
public_url = os.environ.get("WEB_URL")  # e.g. "https://myapp.example.com"

server_kwargs = {"host": host, "port": port}
if public_url:
    server_kwargs["public_url"] = public_url

server = Server(command, **server_kwargs)
server.serve(debug=False) # generates a textual.log debug file when True
