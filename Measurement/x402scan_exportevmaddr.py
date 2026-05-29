import os
import re

ADDRESS_PATTERN = re.compile(r"0x[a-fA-F0-9]{40}")

def extract_addresses_from_file(path: str) -> list[str]:
    addresses = []
    seen = set()
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                for match in ADDRESS_PATTERN.findall(line):
                    if match not in seen:
                        seen.add(match)
                        addresses.append(match)
    except Exception as e:
        print(f"error reading {path}: {e}")
    return addresses

def main():
    result = {}
    for entry in os.listdir("."):
        if os.path.isfile(entry):
            addresses = extract_addresses_from_file(entry)
            if addresses:
                result[entry.split(".")[0]] = addresses
    print(result)

if __name__ == "__main__":
    main()