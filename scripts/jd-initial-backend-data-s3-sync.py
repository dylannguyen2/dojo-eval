#!/usr/bin/env python3
"""
Script to check links in JD initial backend data JSON files.
This script iterates through JSON files in dojo-bench-customer-colossus/initial-backend-data/jd
and checks if URLs are broken or not.
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple, Optional
from urllib.parse import urlparse, unquote

import boto3
from botocore.exceptions import ClientError
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class LinkChecker:
    """Check if links in JSON files are broken."""

    def __init__(self, base_dir: str, timeout: int = 10, s3_bucket: str = "dojo-spas-artifacts", overwrite: bool = False):
        """
        Initialize the link checker.

        Args:
            base_dir: Base directory containing JSON files
            timeout: Timeout for HTTP requests in seconds
            s3_bucket: S3 bucket name for uploads
            overwrite: Whether to overwrite existing S3 objects
        """
        self.base_dir = Path(base_dir)
        self.timeout = timeout
        self.s3_bucket = s3_bucket
        self.overwrite = overwrite
        self.session = self._create_session()
        self.s3_client = boto3.client('s3')

        # Track URLs and their status
        self.url_cache: Dict[str, Tuple[bool, str]] = {}  # url -> (is_working, status_info)
        self.all_urls: Set[str] = set()
        self.url_locations: Dict[str, List[str]] = defaultdict(list)  # url -> list of JSON paths
        self.json_data: Dict[str, Any] = {}  # file_name -> parsed JSON data
        self.json_file_paths: Dict[str, Path] = {}  # file_name -> full file path
        self.json_file_formats: Dict[str, bool] = {}  # file_name -> ensure_ascii flag
        self.url_to_s3_key: Dict[str, str] = {}  # url -> s3_key mapping

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic."""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def is_url(self, value: str) -> bool:
        """Check if a string is a valid HTTP/HTTPS URL."""
        if not isinstance(value, str):
            return False
        if not value or not value.strip():
            return False
        try:
            result = urlparse(value)
            return result.scheme in ('http', 'https') and bool(result.netloc)
        except Exception:
            return False

    def is_s3_url(self, url: str) -> bool:
        """
        Check if a URL is an S3 URL from our bucket.

        Args:
            url: URL to check

        Returns:
            True if it's an S3 URL from our bucket
        """
        if not isinstance(url, str):
            return False

        try:
            parsed = urlparse(url)
            # Check for S3 URL patterns:
            # - https://bucket.s3.amazonaws.com/key
            # - https://bucket.s3.region.amazonaws.com/key
            # - https://s3.amazonaws.com/bucket/key
            # - https://s3.region.amazonaws.com/bucket/key

            if 's3.amazonaws.com' in parsed.netloc:
                # Pattern 1: bucket.s3.amazonaws.com
                if parsed.netloc.startswith(f"{self.s3_bucket}.s3"):
                    return True
                # Pattern 2: s3.amazonaws.com/bucket
                if parsed.path.startswith(f"/{self.s3_bucket}/"):
                    return True

            return False
        except Exception:
            return False

    def extract_urls_from_json(self, data: Any, path: str = "", file_name: str = "") -> Set[str]:
        """
        Recursively extract all URLs from JSON data with their paths.

        Args:
            data: JSON data (dict, list, or primitive)
            path: Current JSON path
            file_name: Name of the JSON file being processed

        Returns:
            Set of URLs found
        """
        urls = set()

        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{path}.{key}" if path else key
                urls.update(self.extract_urls_from_json(value, new_path, file_name))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_path = f"{path}[{i}]"
                urls.update(self.extract_urls_from_json(item, new_path, file_name))
        elif isinstance(data, str) and self.is_url(data):
            # Skip S3 URLs from our bucket (already processed)
            if not self.is_s3_url(data):
                urls.add(data)
                # Store location information
                location = f"{file_name}::{path}" if file_name else path
                self.url_locations[data].append(location)

        return urls

    def check_url(self, url: str) -> Tuple[bool, str]:
        """
        Check if a URL is working.

        Args:
            url: URL to check

        Returns:
            Tuple of (is_working, status_info)
        """
        # Return cached result if available
        if url in self.url_cache:
            return self.url_cache[url]

        try:
            # Use HEAD request to check if URL is accessible
            response = self.session.head(
                url,
                timeout=self.timeout,
                allow_redirects=True,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; LinkChecker/1.0)'}
            )

            # Some servers don't support HEAD, try GET if HEAD fails
            if response.status_code >= 400:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    stream=True,  # Don't download content
                    headers={'User-Agent': 'Mozilla/5.0 (compatible; LinkChecker/1.0)'}
                )

            is_working = response.status_code < 400
            status = f"HTTP {response.status_code}"

        except requests.exceptions.Timeout:
            is_working = False
            status = "Timeout"
        except requests.exceptions.ConnectionError:
            is_working = False
            status = "Connection Error"
        except requests.exceptions.TooManyRedirects:
            is_working = False
            status = "Too Many Redirects"
        except requests.exceptions.RequestException as e:
            is_working = False
            status = f"Request Error: {str(e)[:50]}"
        except Exception as e:
            is_working = False
            status = f"Error: {str(e)[:50]}"

        # Cache the result
        self.url_cache[url] = (is_working, status)
        return is_working, status

    def detect_json_format(self, file_path: Path) -> bool:
        """
        Detect if the JSON file uses Unicode escapes or UTF-8 characters.

        Args:
            file_path: Path to JSON file

        Returns:
            True if file uses Unicode escapes (ensure_ascii=True), False if UTF-8
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check for Unicode escape sequences like \u5b8c
            has_unicode_escapes = '\\u' in content

            # Check for actual non-ASCII characters (like Chinese characters)
            has_utf8_chars = any(ord(c) > 127 for c in content)

            # If file has Unicode escapes and no raw UTF-8 chars, it's ASCII-escaped
            # If file has raw UTF-8 chars, it's UTF-8 format
            if has_unicode_escapes and not has_utf8_chars:
                return True  # ensure_ascii=True
            elif has_utf8_chars:
                return False  # ensure_ascii=False
            else:
                # Default to True (ASCII-escaped) if unsure
                return True
        except Exception:
            # Default to True if detection fails
            return True

    def process_json_file(self, json_path: Path) -> Set[str]:
        """
        Process a JSON file and extract all URLs.

        Args:
            json_path: Path to JSON file

        Returns:
            Set of URLs found in the file
        """
        try:
            # Detect original format
            ensure_ascii = self.detect_json_format(json_path)

            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Store the parsed JSON data, file path, and format
            self.json_data[json_path.name] = data
            self.json_file_paths[json_path.name] = json_path
            self.json_file_formats[json_path.name] = ensure_ascii

            return self.extract_urls_from_json(data, "", json_path.name)
        except json.JSONDecodeError as e:
            print(f"Error parsing {json_path.name}: {e}")
            return set()
        except Exception as e:
            print(f"Error reading {json_path.name}: {e}")
            return set()

    def process_directory(self) -> Dict[str, Any]:
        """
        Process all JSON files in the directory.

        Returns:
            Dictionary with results
        """
        if not self.base_dir.exists():
            print(f"Error: Path not found: {self.base_dir}")
            sys.exit(1)

        # Check if it's a single file or directory
        if self.base_dir.is_file():
            if self.base_dir.suffix == '.json':
                json_files = [self.base_dir]
            else:
                print(f"Error: Not a JSON file: {self.base_dir}")
                sys.exit(1)
        else:
            json_files = list(self.base_dir.glob("*.json"))
            if not json_files:
                print(f"No JSON files found in {self.base_dir}")
                sys.exit(1)

        print(f"Found {len(json_files)} JSON file{'s' if len(json_files) > 1 else ''}")
        print("=" * 80)

        # Extract all URLs from all JSON files
        print("\n[1/2] Extracting URLs from JSON files...")
        for json_file in json_files:
            urls = self.process_json_file(json_file)
            self.all_urls.update(urls)

        print(f"Found {len(self.all_urls)} unique URLs (excluding S3 URLs from {self.s3_bucket})")

        # Check each unique URL
        print("\n[2/2] Checking URLs...")
        working_urls = []
        broken_urls = []

        for i, url in enumerate(sorted(self.all_urls), 1):
            is_working, status = self.check_url(url)

            # Print progress with full URL
            print(f"  [{i}/{len(self.all_urls)}] {status:<20} {url}")

            if is_working:
                working_urls.append((url, status))
            else:
                broken_urls.append((url, status))

        return {
            'total_urls': len(self.all_urls),
            'working_urls': working_urls,
            'broken_urls': broken_urls,
            'json_files_processed': len(json_files)
        }

    def get_file_extension(self, url: str) -> str:
        """
        Extract file extension from URL.

        Args:
            url: The URL to extract extension from

        Returns:
            File extension with dot (e.g., '.jpg') or empty string
        """
        parsed = urlparse(url)
        path = unquote(parsed.path)
        # Remove query parameters if they're in the path
        path = path.split('?')[0]
        ext = os.path.splitext(path)[1]
        # Default to .jpg if no extension found
        return ext if ext else '.jpg'

    def get_value_from_path(self, data: Any, path: str) -> Optional[Any]:
        """
        Navigate through JSON data using a path string.

        Args:
            data: JSON data
            path: Path string like "products[2].images[1]"

        Returns:
            Value at the path or None
        """
        if not path:
            return data

        current = data
        # Split path by dots and brackets
        tokens = re.findall(r'[^.\[\]]+', path)

        i = 0
        while i < len(tokens):
            token = tokens[i]

            if token.isdigit():
                # Array index
                idx = int(token)
                if isinstance(current, list) and 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                # Object key
                if isinstance(current, dict) and token in current:
                    current = current[token]
                else:
                    return None

            i += 1

        return current

    def find_parent_id(self, data: Any, path: str) -> Optional[str]:
        """
        Find the nearest parent object with _id or id field.

        Args:
            data: JSON data
            path: Path string like "products[2].images[1]"

        Returns:
            The _id or id value, or None
        """
        # Split path into segments
        segments = re.findall(r'([^.\[\]]+)(\[\d+\])?', path)

        # Try progressively shorter paths to find parent with id
        for i in range(len(segments), 0, -1):
            # Build path up to this point
            partial_path = ""
            for j in range(i):
                key, index = segments[j]
                if partial_path:
                    partial_path += "."
                partial_path += key
                if index:
                    partial_path += index

            # Get object at this path
            obj = self.get_value_from_path(data, partial_path)

            if isinstance(obj, dict):
                # Check for _id first, then id
                if "_id" in obj:
                    return obj["_id"]
                elif "id" in obj:
                    return obj["id"]

        return None

    def s3_object_exists(self, key: str) -> bool:
        """
        Check if an S3 object exists.

        Args:
            key: S3 object key

        Returns:
            True if object exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.s3_bucket, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                # Some other error occurred
                raise

    def get_s3_https_url(self, s3_key: str) -> str:
        """
        Convert S3 key to HTTPS URL.

        Args:
            s3_key: S3 object key

        Returns:
            HTTPS URL to access the object
        """
        # Use S3 direct URL format
        return f"https://{self.s3_bucket}.s3.amazonaws.com/{s3_key}"

    def set_value_at_path(self, data: Any, path: str, value: Any) -> bool:
        """
        Set a value in JSON data at a specific path.

        Args:
            data: JSON data
            path: Path string like "products[2].images[1]"
            value: Value to set

        Returns:
            True if successful, False otherwise
        """
        if not path:
            return False

        # Split path into segments
        segments = re.findall(r'([^.\[\]]+)(\[\d+\])?', path)

        current = data
        # Navigate to parent
        for i in range(len(segments) - 1):
            key, index = segments[i]

            if index:
                # Array index
                idx = int(index.strip('[]'))
                if isinstance(current, dict) and key in current:
                    current = current[key]
                    if isinstance(current, list) and 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        return False
                else:
                    return False
            else:
                # Object key
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return False

        # Set the final value
        final_key, final_index = segments[-1]

        if final_index:
            # Array index
            idx = int(final_index.strip('[]'))
            if isinstance(current, dict) and final_key in current:
                if isinstance(current[final_key], list) and 0 <= idx < len(current[final_key]):
                    current[final_key][idx] = value
                    return True
        else:
            # Object key
            if isinstance(current, dict):
                current[final_key] = value
                return True

        return False

    def remove_value_at_path(self, data: Any, path: str) -> bool:
        """
        Remove a value from JSON data at a specific path (for array elements).

        Args:
            data: JSON data
            path: Path string like "products[2].images[1]"

        Returns:
            True if successful, False otherwise
        """
        if not path:
            return False

        # Split path into segments
        segments = re.findall(r'([^.\[\]]+)(\[\d+\])?', path)

        # Must end with array index to remove
        if not segments[-1][1]:
            return False

        current = data
        # Navigate to parent array
        for i in range(len(segments) - 1):
            key, index = segments[i]

            if index:
                # Array index
                idx = int(index.strip('[]'))
                if isinstance(current, dict) and key in current:
                    current = current[key]
                    if isinstance(current, list) and 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        return False
                else:
                    return False
            else:
                # Object key
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return False

        # Remove from the final array
        final_key, final_index = segments[-1]
        idx = int(final_index.strip('[]'))

        if isinstance(current, dict) and final_key in current:
            if isinstance(current[final_key], list) and 0 <= idx < len(current[final_key]):
                del current[final_key][idx]
                return True

        return False

    def update_json_files(self, working_urls: List[Tuple[str, str]], broken_urls: List[Tuple[str, str]]) -> Dict[str, Any]:
        """
        Update JSON files with S3 URLs and remove broken links from arrays.

        Args:
            working_urls: List of (url, status) tuples for working URLs
            broken_urls: List of (url, status) tuples for broken URLs

        Returns:
            Dictionary with update statistics
        """
        print("\n" + "=" * 80)
        print("UPDATING JSON FILES")
        print("=" * 80)

        stats = {
            'files_updated': 0,
            'urls_replaced': 0,
            'urls_removed': 0,
            'errors': []
        }

        # Build set of working URLs
        working_url_set = {url for url, _ in working_urls}
        broken_url_set = {url for url, _ in broken_urls}

        # Process each JSON file
        for file_name, data in self.json_data.items():
            modified = False

            # Track items to remove (must be done in reverse to maintain indices)
            removals = []  # (path, url) tuples

            # Find all URLs in this file and update/remove them
            for url in self.all_urls:
                locations = self.url_locations.get(url, [])

                for location in locations:
                    if not location.startswith(f"{file_name}::"):
                        continue

                    path = location.split("::", 1)[1]

                    if url in working_url_set and url in self.url_to_s3_key:
                        # Replace with S3 URL
                        s3_key = self.url_to_s3_key[url]
                        s3_url = self.get_s3_https_url(s3_key)

                        if self.set_value_at_path(data, path, s3_url):
                            stats['urls_replaced'] += 1
                            modified = True
                        else:
                            stats['errors'].append(f"Failed to update {file_name}::{path}")

                    elif url in broken_url_set:
                        # Check if it's in an array
                        context = self.get_array_context(url)
                        if context['is_in_array']:
                            # Mark for removal
                            removals.append((path, url))
                        else:
                            # This should not happen due to validation
                            stats['errors'].append(f"Broken non-array URL found: {file_name}::{path}")

            # Remove broken URLs from arrays (in reverse order to maintain indices)
            # We need to be careful about the order - sort by path depth and index
            removals_sorted = sorted(removals, key=lambda x: (x[0].count('['), x[0]), reverse=True)

            for path, url in removals_sorted:
                if self.remove_value_at_path(data, path):
                    stats['urls_removed'] += 1
                    modified = True
                else:
                    stats['errors'].append(f"Failed to remove {file_name}::{path}")

            # Write back to file if modified
            if modified:
                # Use the stored file path instead of constructing it
                file_path = self.json_file_paths.get(file_name)
                if not file_path:
                    error_msg = f"File path not found for {file_name}"
                    stats['errors'].append(error_msg)
                    print(f"  ❌ {error_msg}")
                    continue

                # Use the original format (ensure_ascii flag)
                ensure_ascii = self.json_file_formats.get(file_name, True)

                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=ensure_ascii, indent=2)
                    stats['files_updated'] += 1
                    print(f"  ✅ Updated {file_name}")
                except Exception as e:
                    error_msg = f"Failed to write {file_name}: {str(e)}"
                    stats['errors'].append(error_msg)
                    print(f"  ❌ {error_msg}")

        print("\n" + "-" * 80)
        print("UPDATE SUMMARY")
        print("-" * 80)
        print(f"Files updated: {stats['files_updated']}")
        print(f"URLs replaced with S3 links: {stats['urls_replaced']}")
        print(f"Broken URLs removed from arrays: {stats['urls_removed']}")

        if stats['errors']:
            print(f"\n⚠️  Errors: {len(stats['errors'])}")
            for error in stats['errors']:
                print(f"  - {error}")

        return stats

    def download_and_upload_to_s3(self, url: str, s3_key: str) -> Tuple[bool, str]:
        """
        Download URL content and upload to S3.

        Args:
            url: URL to download
            s3_key: S3 key to upload to

        Returns:
            Tuple of (success, message)
        """
        # Check if object already exists
        if not self.overwrite and self.s3_object_exists(s3_key):
            return True, "Already exists (skipped)"

        try:
            # Download the content
            response = self.session.get(
                url,
                timeout=self.timeout,
                stream=True,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; S3Uploader/1.0)'}
            )
            response.raise_for_status()

            # Determine content type from URL extension
            ext = self.get_file_extension(url).lower()
            content_type_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
                '.svg': 'image/svg+xml',
            }
            content_type = content_type_map.get(ext, 'application/octet-stream')

            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=response.content,
                ContentType=content_type
            )

            return True, "Uploaded successfully"

        except requests.exceptions.RequestException as e:
            return False, f"Download failed: {str(e)[:50]}"
        except ClientError as e:
            return False, f"S3 upload failed: {str(e)[:50]}"
        except Exception as e:
            return False, f"Error: {str(e)[:50]}"

    def generate_s3_key(self, url: str, location: str) -> str:
        """
        Generate deterministic S3 key for a URL.

        Args:
            url: The URL to upload
            location: Location string like "filename.json::products[2].images[1]"

        Returns:
            S3 key path
        """
        # Parse location
        parts = location.split("::")
        if len(parts) != 2:
            # Fallback: use URL filename
            filename = os.path.basename(urlparse(url).path)
            return f"jd/unknown/{filename}"

        file_name, path = parts

        # Get the JSON data for this file
        data = self.json_data.get(file_name)
        if not data:
            filename = os.path.basename(urlparse(url).path)
            return f"jd/unknown/{filename}"

        # Find parent object with _id or id
        parent_id = self.find_parent_id(data, path)

        if not parent_id:
            # No parent ID found, use filename from URL
            filename = os.path.basename(urlparse(url).path).split('?')[0]
            if not filename:
                filename = "unnamed"
            return f"jd/no-id/{filename}"

        # Build subdirectory path from JSON structure
        # Parse path like "productMeta[0].productReviews[3].images[1]"
        segments = re.findall(r'([^.\[\]]+)(\[\d+\])?', path)

        subdirs = []
        for key, index in segments:
            # Skip the key that contains the parent_id (top level)
            # We need to find where the parent_id is
            # For now, let's build path after we find the parent

            if index:
                # Extract index number
                idx = index.strip('[]')
                subdirs.append(f"{key}/{idx}")
            else:
                subdirs.append(key)

        # Build the full path
        subdir_path = "/".join(subdirs) if subdirs else ""

        # Get file extension
        ext = self.get_file_extension(url)

        # Build final S3 key
        if subdir_path:
            s3_key = f"jd/{parent_id}/{subdir_path}{ext}"
        else:
            filename = os.path.basename(urlparse(url).path).split('?')[0] or "unnamed"
            s3_key = f"jd/{parent_id}/{filename}"

        return s3_key

    def get_array_context(self, url: str) -> Dict[str, Any]:
        """
        Get array context for a URL - determine if it's in an array and how many siblings are broken.

        Args:
            url: The URL to analyze

        Returns:
            Dictionary with array context information
        """
        locations = self.url_locations.get(url, [])
        array_info = []

        for location in locations:
            # Extract the array path (everything before the last [index])
            if '[' in location:
                # Find the last array index
                parts = location.split('::')
                if len(parts) == 2:
                    file_name, path = parts
                else:
                    path = location

                # Get the array base path (remove the last [index])
                import re
                match = re.search(r'^(.+)\[\d+\]$', path)
                if match:
                    array_base_path = match.group(1)

                    # Find all URLs from the same array
                    sibling_urls = []
                    for other_url, other_locations in self.url_locations.items():
                        for other_location in other_locations:
                            if array_base_path in other_location and '[' in other_location:
                                sibling_urls.append(other_url)
                                break

                    # Count how many siblings are broken
                    broken_siblings = []
                    working_siblings = []
                    for sibling in sibling_urls:
                        if sibling in self.url_cache:
                            is_working, _ = self.url_cache[sibling]
                            if is_working:
                                working_siblings.append(sibling)
                            else:
                                broken_siblings.append(sibling)

                    array_info.append({
                        'location': location,
                        'array_path': array_base_path,
                        'total_items': len(sibling_urls),
                        'broken_items': len(broken_siblings),
                        'working_items': len(working_siblings)
                    })

        return {
            'is_in_array': len(array_info) > 0,
            'array_contexts': array_info
        }

    def get_severity(self, url: str) -> Tuple[str, str, str]:
        """
        Determine severity level for a broken URL.

        Returns:
            Tuple of (color_code, indicator, description)
            - Green: Single broken item in array with working siblings
            - Yellow: Multiple broken items in array (but not all)
            - Red: Not in array OR all items in array are broken
        """
        # ANSI color codes
        RED = '\033[91m'
        YELLOW = '\033[93m'
        GREEN = '\033[92m'
        RESET = '\033[0m'

        context = self.get_array_context(url)

        if not context['is_in_array']:
            # Not in array - RED
            locations = self.url_locations.get(url, [])
            location = locations[0] if locations else "unknown"
            return RED, "🔴", f"Not in array - {location}"

        # In an array - check how many items are broken
        array_ctx = context['array_contexts'][0]  # Use first context
        total = array_ctx['total_items']
        broken = array_ctx['broken_items']
        working = array_ctx['working_items']

        if broken == total:
            # All items broken - RED
            return RED, "🔴", f"All {total} items in array broken - {array_ctx['array_path']}"
        elif broken == 1:
            # Only this item broken - GREEN
            return GREEN, "🟢", f"Only 1/{total} broken in array - {array_ctx['array_path']}"
        else:
            # Multiple but not all broken - YELLOW
            return YELLOW, "🟡", f"{broken}/{total} broken in array - {array_ctx['array_path']}"

    def print_summary(self, results: Dict[str, Any]) -> int:
        """
        Print summary of link checking results.

        Returns:
            Exit code: 0 if no critical issues, 1 if critical (red) URLs found
        """
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"JSON files processed: {results['json_files_processed']}")
        print(f"Total unique URLs: {results['total_urls']}")

        # Guard against division by zero
        if results['total_urls'] > 0:
            working_pct = len(results['working_urls']) / results['total_urls'] * 100
            broken_pct = len(results['broken_urls']) / results['total_urls'] * 100
            print(f"Working URLs: {len(results['working_urls'])} ({working_pct:.1f}%)")
            print(f"Broken URLs: {len(results['broken_urls'])} ({broken_pct:.1f}%)")
        else:
            print(f"Working URLs: {len(results['working_urls'])}")
            print(f"Broken URLs: {len(results['broken_urls'])}")
            print("\nℹ️  No external URLs found - all URLs are already S3 links from the configured bucket")

        exit_code = 0

        if results['broken_urls']:
            # Categorize broken URLs by severity
            red_urls = []
            yellow_urls = []
            green_urls = []

            for url, status in results['broken_urls']:
                color, indicator, description = self.get_severity(url)
                if "🔴" in indicator:
                    red_urls.append((url, status, description))
                elif "🟡" in indicator:
                    yellow_urls.append((url, status, description))
                else:
                    green_urls.append((url, status, description))

            print("\n" + "-" * 80)
            print("BROKEN URLS BY SEVERITY")
            print("-" * 80)
            print(f"🔴 Red ({len(red_urls)}): Not in array OR all items in array broken")
            print(f"🟡 Yellow ({len(yellow_urls)}): Multiple items in array broken")
            print(f"🟢 Green ({len(green_urls)}): Single item in array broken")

            # Print Red URLs
            if red_urls:
                print("\n🔴 RED - CRITICAL")
                for url, status, desc in sorted(red_urls):
                    print(f"  {status:<20} {url}")
                    print(f"    └─ {desc}")
                exit_code = 1  # Set failure exit code

            # Print Yellow URLs
            if yellow_urls:
                print("\n🟡 YELLOW - WARNING")
                for url, status, desc in sorted(yellow_urls):
                    print(f"  {status:<20} {url}")
                    print(f"    └─ {desc}")

            # Print Green URLs
            if green_urls:
                print("\n🟢 GREEN - LOW IMPACT")
                for url, status, desc in sorted(green_urls):
                    print(f"  {status:<20} {url}")
                    print(f"    └─ {desc}")

        if results['working_urls']:
            print("\n" + "-" * 80)
            print(f"WORKING URLS ({len(results['working_urls'])} total)")
            print("-" * 80)
            # Show all working URLs
            for url, status in sorted(results['working_urls']):
                print(f"  {status:<20} {url}")

        # Generate S3 key mappings and upload
        if exit_code == 0 and results['working_urls']:
            print("\n" + "=" * 80)
            print("S3 UPLOAD")
            print("=" * 80)
            print(f"Bucket: s3://{self.s3_bucket}/")
            print(f"Overwrite mode: {'ON' if self.overwrite else 'OFF'}")
            print()

            mappings = []
            for url, status in sorted(results['working_urls']):
                locations = self.url_locations.get(url, [])
                if locations:
                    # Use first location for key generation
                    s3_key = self.generate_s3_key(url, locations[0])
                    mappings.append((url, s3_key, locations[0]))
                    # Store mapping for later use
                    self.url_to_s3_key[url] = s3_key

            # Upload each file
            upload_results = {
                'success': [],
                'skipped': [],
                'failed': []
            }

            print(f"Uploading {len(mappings)} files...")
            for i, (url, s3_key, location) in enumerate(mappings, 1):
                print(f"[{i}/{len(mappings)}] {s3_key}")
                success, message = self.download_and_upload_to_s3(url, s3_key)

                if success:
                    if "skipped" in message.lower():
                        upload_results['skipped'].append((url, s3_key, message))
                        print(f"  ⏭️  {message}")
                    else:
                        upload_results['success'].append((url, s3_key, message))
                        print(f"  ✅ {message}")
                else:
                    upload_results['failed'].append((url, s3_key, message))
                    print(f"  ❌ {message}")

            # Print upload summary
            print("\n" + "-" * 80)
            print("UPLOAD SUMMARY")
            print("-" * 80)
            print(f"✅ Uploaded: {len(upload_results['success'])}")
            print(f"⏭️  Skipped (already exists): {len(upload_results['skipped'])}")
            print(f"❌ Failed: {len(upload_results['failed'])}")

            if upload_results['failed']:
                print("\n" + "-" * 80)
                print("FAILED UPLOADS")
                print("-" * 80)
                for url, s3_key, message in upload_results['failed']:
                    print(f"  {s3_key}")
                    print(f"    URL: {url}")
                    print(f"    Error: {message}")

            # Set exit code if any uploads failed
            if upload_results['failed']:
                exit_code = 1
            else:
                # All uploads successful, now update JSON files
                update_stats = self.update_json_files(results['working_urls'], results['broken_urls'])

                # Check for errors in JSON updates
                if update_stats['errors']:
                    exit_code = 1

        # Print final status
        print("\n" + "=" * 80)
        if exit_code == 0:
            print("✅ VALIDATION PASSED - No critical issues found")
            print("=" * 80)
        else:
            print("❌ VALIDATION FAILED - Critical (red) URLs found")
            print("=" * 80)
            print("\nScript will exit with code 1 to prevent next steps.")
            print("Please fix critical URLs before proceeding.")

        return exit_code


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Check links in JD JSON files and upload to S3',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process backend data files (default)
  python jd-initial-backend-data-s3-sync.py

  # Process app initial data
  python jd-initial-backend-data-s3-sync.py --target app

  # Process with custom path
  python jd-initial-backend-data-s3-sync.py --path path/to/json/files

  # Upload to S3 (overwrite existing files)
  python jd-initial-backend-data-s3-sync.py --overwrite
        """
    )
    parser.add_argument(
        '--target',
        choices=['backend', 'app'],
        default='backend',
        help='Target location: "backend" for dojo-bench-customer-colossus/initial-backend-data/jd, "app" for jd/app (default: backend)'
    )
    parser.add_argument(
        '--path',
        type=str,
        help='Custom path to JSON files or directory (overrides --target)'
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing files in S3 (default: skip existing files)'
    )
    parser.add_argument(
        '--bucket',
        default='dojo-spas-artifacts',
        help='S3 bucket name (default: dojo-spas-artifacts)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=10,
        help='HTTP request timeout in seconds (default: 10)'
    )

    args = parser.parse_args()

    # Determine the base directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    if args.path:
        # Custom path provided
        jd_data_dir = Path(args.path)
        if not jd_data_dir.is_absolute():
            jd_data_dir = project_root / jd_data_dir
    elif args.target == 'app':
        # App initial data
        jd_data_dir = project_root / "jd" / "app"
    else:
        # Backend data (default)
        jd_data_dir = project_root / "dojo-bench-customer-colossus" / "initial-backend-data" / "jd"

    print("JD Initial Backend Data - Link Checker & S3 Uploader")
    print("=" * 80)
    print(f"Target: {args.target if not args.path else 'custom'}")
    print(f"Checking links in: {jd_data_dir}")
    print(f"S3 Bucket: {args.bucket}")
    print(f"Overwrite mode: {'ON' if args.overwrite else 'OFF'}")
    print()

    # Create link checker and process
    checker = LinkChecker(
        str(jd_data_dir),
        timeout=args.timeout,
        s3_bucket=args.bucket,
        overwrite=args.overwrite
    )
    results = checker.process_directory()
    exit_code = checker.print_summary(results)

    # Exit with appropriate code
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
