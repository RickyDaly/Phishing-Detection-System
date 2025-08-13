


with open("PhishingArmy.txt", 'r') as pa:
    PhishArmy = set(line.strip() for line in pa if line.strip())

with open("blocklist.txt", 'r') as bl:
    blocklist = set(line.strip() for line in bl if line.strip())

List = open("blocklist.txt", "a")

try:
    with open("newconfirmed.txt", "r", encoding="utf-8") as file:
        for line in file:
            # print(url)
            parts = line.strip().strip("{}").split(",")
            if len(parts) >= 2:
                url = parts[1].strip().strip("'").strip()
                # print(url)

                if url.strip() in PhishArmy:
                    print(f"{url} Found")
                    if url.strip() not in blocklist:
                        print(f"{url} not in blocklist")
                        List.write(f"{url}\n")
                        
                    
                
except FileNotFoundError:
    print(f"Error: File 'url' not found.")