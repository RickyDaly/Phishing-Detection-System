import csv

input = "newconfirmed.txt"
output = "capture.csv"

with open(input, "r", encoding="utf-8") as infile, \
     open(output, "w", newline="", encoding="utf-8") as outfile:

    w = csv.writer(outfile)
    w.writerow(["url", "website", "html", "label"])

    for line in infile:
        if not line.strip():
            continue
        clean = line.strip().rstrip(", \t")  
        clean = clean.strip("{}")   
        parts = [p.strip().strip("'") for p in clean.split(",")]
        if len(parts) >= 3:
            w.writerow([parts[0], parts[1], parts[2], 0])

print("CSV written to", output)
