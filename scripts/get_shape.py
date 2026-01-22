import json
import sys

def get_shape(obj, max_array_samples=1):
    if obj is None:
        return "null"
    if isinstance(obj, bool):
        return "boolean"
    if isinstance(obj, int):
        return "integer"
    if isinstance(obj, float):
        return "number"
    if isinstance(obj, str):
        return f"string (len={len(obj)})" if len(obj) > 100 else "string"
    if isinstance(obj, list):
        if not obj:
            return "[]"
        samples = obj[:max_array_samples]
        item_shapes = [get_shape(item) for item in samples]
        unique = list(dict.fromkeys(json.dumps(s, sort_keys=True) if isinstance(s, dict) else str(s) for s in item_shapes))
        if len(unique) == 1:
            return [item_shapes[0], f"... ({len(obj)} items)"]
        return [item_shapes[0], f"... ({len(obj)} items, mixed types)"]
    if isinstance(obj, dict):
        return {k: get_shape(v) for k, v in obj.items()}
    return str(type(obj).__name__)

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data.json"
    with open(path) as f:
        data = json.load(f)
    print(json.dumps(get_shape(data), indent=2))