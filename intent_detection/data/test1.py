import json

INPUT_FILE = "data.json"

def clean_json():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data:
        # Remove keys if they exist
        item.pop("operation", None)
        item.pop("output_type", None)

    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("✅ Successfully removed 'operation' and 'output_type' from all entries.")

if __name__ == "__main__":
    clean_json()
