import websocket
import json
import time
import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
import queue
import threading

domain_queue = queue.Queue()

def capture_website(url):
    """Tries HTTPS first, then HTTP if HTTPS fails."""
    for scheme in ["https", "http"]:
        full_url = f"{scheme}://{url}"
        try:
            response = requests.get(full_url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
 
            parsed_url = urlparse(full_url)
            domain = parsed_url.netloc.replace(".", "_")  
            filename = f"{domain}.html"
            save_path = os.path.join(os.getcwd(), "files", filename)
 
            os.makedirs("files", exist_ok=True)
 
            with open(save_path, "w", encoding="utf-8") as file:
                file.write(soup.prettify())

            print(f"Captured: {full_url} -> {filename}")

            
            with open("newconfirmed.txt", "a", encoding="utf-8") as log_file:
                log_file.write(f"{{'{full_url}','{url}', '{filename.strip()}'}}, \n")

            return  

        except requests.exceptions.RequestException:
            print(f"Failed: {full_url}, trying next...")

def process_queue():
    """Worker function to process the queue continuously."""
    with ThreadPoolExecutor(max_workers=10) as executor:
        while True:
            url = domain_queue.get()
            if url is None:
                break  
            executor.submit(capture_website, url)
            domain_queue.task_done()

def on_message(ws, message):
    """Handles incoming WebSocket messages and adds domains to the queue."""
    try:
        data = json.loads(message)
        domain = data.get("domain", "").strip()[:-1]  
        if domain:
            domain_queue.put(domain)
            print(f"New domain added to queue: {domain}")
    except json.JSONDecodeError:
        print("Message is not JSON format.")

def on_error(ws, error):
    """Handles WebSocket errors."""
    print("Error:", error)

def on_close(ws, close_status_code, close_msg):
    """Handles WebSocket disconnections."""
    print("WebSocket closed:", close_status_code, close_msg)

def on_open(ws):
    """Handles WebSocket opening."""
    print("WebSocket connection opened.")

def start_websocket():
    """Starts the WebSocket connection."""
    ws = websocket.WebSocketApp(
        "wss://zonestream.openintel.nl/ws/confirmed_newly_registered_domain",
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.on_open = on_open
    ws.run_forever()

if __name__ == "__main__":
    threading.Thread(target=process_queue, daemon=True).start()
    start_websocket()
