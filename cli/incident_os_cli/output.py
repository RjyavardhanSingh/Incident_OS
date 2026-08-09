import json


def short_id(value):
    return value.split("-")[0] if value else "-"


def print_table(headers, rows):
    widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    fmt = "  ".join(f"{{{i}:<{w}}}" for i, w in enumerate(widths))
    print(fmt.format(*headers))
    print("-" * (sum(widths) + 2 * (len(headers) - 1)))
    for row in rows:
        print(fmt.format(*[str(c) for c in row]))


def kv(title, pairs):
    print(title)
    for key, value in pairs:
        print(f"  {key:<20} {value}")
    print()


def dump_json(data):
    print(json.dumps(data, indent=2, default=str))
