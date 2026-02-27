import sys
from entity_Cache import EntityCache
from filter_extraction import detect_filters


def print_filters(filters):
    print("\n" + "=" * 60)
    print("Detected Filters:\n")

    if not filters:
        print("No filters detected.")
    else:
        for key, value in filters.items():
            print(f"{key}: {value}")

    print("=" * 60 + "\n")


def main():
    print("\nFilter Detection Testing Console")
    print("Type your question.")
    print("Press Ctrl+C to exit.\n")

    # Initialize and load cache once
    entity_cache = EntityCache()
    entity_cache.load_from_db()

    try:
        while True:
            user_input = input("Enter Question: ").strip()

            if not user_input:
                continue

            filters = detect_filters(user_input, entity_cache)

            print_filters(filters)

    except KeyboardInterrupt:
        print("\n\nExiting Filter Test Console. Goodbye.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
