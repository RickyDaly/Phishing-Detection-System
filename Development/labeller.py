import csv

# File paths
input_csv = 'capture.csv'             # Your CSV file from earlier
blocklist_file = 'blocklist.txt'     # TXT file with one website per line
output_csv = 'results_labelled.csv'    # Final updated CSV

# Load blocklist into a set for fast lookup
with open(blocklist_file, 'r') as bl:
    blocklist = set(line.strip() for line in bl if line.strip())

# Read the CSV, update labels
with open(input_csv, 'r', newline='', encoding='utf-8') as infile, \
     open(output_csv, 'w', newline='', encoding='utf-8') as outfile:
    
    reader = csv.DictReader(infile)
    fieldnames = reader.fieldnames
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    
    writer.writeheader()
    
    for row in reader:
        website = row['website'].strip()
        # Label = 1 if on blocklist
        row['label'] = '1' if website in blocklist else row['label']
        writer.writerow(row)
