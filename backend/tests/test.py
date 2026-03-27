import json

# load your file
with open("backend/data/data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# write pretty format
with open("backend/data/data_pretty.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)