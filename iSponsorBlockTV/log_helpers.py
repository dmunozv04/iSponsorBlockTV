from datetime import datetime

def info(message, device_name = None):
    device_message = ""
    if device_name:
        device_message = f"[{device_name}]"
    print(f"{device_message} {message}")
