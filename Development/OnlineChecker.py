import requests
from urllib.parse import quote


resolver_ip = "165.87.13.129"
base_url = "https://digwebinterface.com"

output = open("blocklist.txt", "a", encoding="utf-8") 

# Function to query Spamhaus
def query_spamhaus(url_part):
    encoded_url_part = quote(url_part)
    query_url = (
        f"{base_url}/?hostnames={encoded_url_part}.dbl.spamhaus.org&type=A"
        f"&ns=resolver&useresolver={resolver_ip}&nameservers="
    )

    response = requests.get(query_url)

    if response.status_code == 200:
        content = response.text
        if "127.0.1.4" in content:
            return True
    return False



try:
    with open("newconfirmed.txt", "r", encoding="utf-8") as file:
        for line in file:
            parts = line.strip().strip("{}").split(",")
            if len(parts) >= 2:
                url = parts[1].strip().strip("'").strip()
                if query_spamhaus(url):
                    print(f"[BLOCKED] {url} is on the Spamhaus blocklist.")

                else:
                    print(f"[CLEAN] {url} is NOT on the Spamhaus blocklist.")
                    output.write(f"{url}\n")
except FileNotFoundError:
    print(f"Error: File 'url' not found.")