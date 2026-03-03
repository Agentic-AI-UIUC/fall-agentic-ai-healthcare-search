import csv
import os

#works now, made the parameter the filename instead of the whole path

def read_medical_data(csv_filename):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, csv_filename)

    data = []
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)  # reads rows as dictionaries
        for row in reader:
            data.append({
                "title": row["title"],
                "source": row["source"],
                "url": row["url"],
                "content": row["content"]
            })
    return data

#testing with injuries.csv, it worked
data = read_medical_data('injuries.csv')
print(data[0])

