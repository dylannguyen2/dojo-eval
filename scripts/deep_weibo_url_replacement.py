#!/usr/bin/env python3
"""
Deep replace image URLs in JSON files with S3-hosted versions.
Maintains a persistent mapping file for deterministic replacements.
"""

import json
import hashlib
import os
import sys
import random
import mimetypes
from pathlib import Path
from urllib.parse import urlparse
import boto3
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

BUCKET = "dojo-spas-artifacts"
PREFIX = "weibo/images"
MAPPING_FILE = "url_mapping.json"
S3_REGION = "us-east-1"

s3 = boto3.client("s3")

def load_mapping():
    if Path(MAPPING_FILE).exists():
        with open(MAPPING_FILE) as f:
            return json.load(f)
    return {}

def save_mapping(mapping):
    with open(MAPPING_FILE, "w") as f:
        json.dump(mapping, f, indent=2)

def get_extension(url, content_type=None):
    parsed = urlparse(url)
    path_ext = Path(parsed.path).suffix.lower()
    if path_ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"]:
        return path_ext
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0])
        if ext:
            return ext
    return ".jpg"

def url_to_s3_key(url, ext):
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    return f"{PREFIX}/{url_hash}{ext}"

def s3_key_to_url(key):
    return f"https://{BUCKET}.s3.{S3_REGION}.amazonaws.com/{key}"

def check_s3_exists(key):
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
        return True
    except:
        return False

def upload_to_s3(key, data, content_type):
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
    )

def download_image(url, timeout=10):
    try:
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
        resp.raise_for_status()
        return resp.content, resp.headers.get("Content-Type", "image/jpeg")
    except Exception as e:
        return None, None

def process_url(url, mapping, successful_urls):
    """Process a single URL, return (original, replacement) or None if already mapped."""
    if url in mapping:
        return None

    # Skip URLs already on our S3 bucket
    if f"{BUCKET}.s3" in url or f"s3.amazonaws.com/{BUCKET}" in url:
        successful_urls.append(url)
        return (url, url)  # map to itself
    
    data, content_type = download_image(url)
    
    if data:
        ext = get_extension(url, content_type)
        key = url_to_s3_key(url, ext)
        if not check_s3_exists(key):
            upload_to_s3(key, data, content_type or "image/jpeg")
        s3_url = s3_key_to_url(key)
        successful_urls.append(s3_url)
        return (url, s3_url)
    else:
        if successful_urls:
            fallback = random.choice(successful_urls)
        else:
            fallback = url  # keep original if nothing available
        return (url, fallback)

def is_image_url(value):
    if not isinstance(value, str):
        return False
    lower = value.lower()
    if any(ext in lower for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"]):
        return True
    if any(hint in lower for hint in ["avatar", "image", "img", "photo", "pic"]):
        return value.startswith("http")
    return False

def collect_urls(obj, urls, path=""):
    """Recursively collect all image URLs from the object."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and is_image_url(v):
                urls.append((path + "." + k if path else k, v))
            else:
                collect_urls(v, urls, path + "." + k if path else k)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            collect_urls(item, urls, f"{path}[{i}]")

def replace_urls(obj, mapping):
    """Recursively replace URLs using the mapping."""
    if isinstance(obj, dict):
        return {k: replace_urls(v, mapping) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [replace_urls(item, mapping) for item in obj]
    elif isinstance(obj, str) and obj in mapping:
        return mapping[obj]
    return obj

def process_file(filepath, mapping, successful_urls):
    print(f"Processing {filepath}...")
    
    with open(filepath) as f:
        data = json.load(f)
    
    urls = []
    collect_urls(data, urls)
    unique_urls = list(set(url for _, url in urls))
    
    new_urls = [u for u in unique_urls if u not in mapping]
    print(f"  Found {len(unique_urls)} URLs, {len(new_urls)} new")
    
    if new_urls:
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(process_url, url, mapping, successful_urls): url for url in new_urls}
            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                if result:
                    orig, repl = result
                    mapping[orig] = repl
                if (i + 1) % 50 == 0:
                    print(f"    Processed {i + 1}/{len(new_urls)}")
                    save_mapping(mapping)
        
        save_mapping(mapping)
    
    replaced_data = replace_urls(data, mapping)
    
    out_path = Path(filepath).stem + "_replaced.json"
    with open(out_path, "w") as f:
        json.dump(replaced_data, f, indent=2, ensure_ascii=False)
    
    print(f"  Wrote {out_path}")
    return out_path

def main():
    if len(sys.argv) < 2:
        print("Usage: python replace_urls.py <file1.json> [file2.json ...]")
        sys.exit(1)
    
    mapping = load_mapping()
    successful_urls = list(mapping.values())
    
    for filepath in sys.argv[1:]:
        if not Path(filepath).exists():
            print(f"File not found: {filepath}")
            continue
        process_file(filepath, mapping, successful_urls)
    
    print(f"\nDone. Mapping has {len(mapping)} entries saved to {MAPPING_FILE}")

if __name__ == "__main__":
    main()