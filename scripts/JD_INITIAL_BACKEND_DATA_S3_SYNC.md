# JD Initial Backend Data S3 Sync

A Python script that validates, uploads, and migrates image URLs in JD JSON files to S3 storage.

## Overview

This script performs three main functions:
1. **Link Validation**: Checks if URLs in JSON files are working or broken
2. **S3 Upload**: Downloads working images and uploads them to S3 with deterministic keys
3. **JSON Migration**: Updates JSON files to replace external URLs with S3 URLs and removes broken links

## Features

- ✅ **Link checking** with retry logic and timeout handling
- ✅ **Broken link severity analysis** (Red/Yellow/Green based on impact)
- ✅ **Deterministic S3 key generation** based on JSON structure and IDs
- ✅ **Idempotent execution** - safe to run multiple times (skips already-uploaded files)
- ✅ **Format preservation** - maintains original JSON encoding (Unicode escapes vs UTF-8)
- ✅ **Fault tolerance** - handles upload failures gracefully
- ✅ **Flexible targeting** - works with directories, single files, or custom paths

## Installation

```bash
pip install boto3 requests
```

Ensure AWS credentials are configured:
```bash
# Option 1: AWS credentials file
~/.aws/credentials

# Option 2: Environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
```

## Usage

### Basic Usage

```bash
# Process backend data (default)
python scripts/jd-initial-backend-data-s3-sync.py

# Process app initial data
python scripts/jd-initial-backend-data-s3-sync.py --target app

# Process a specific file
python scripts/jd-initial-backend-data-s3-sync.py --path jd/app/initial_data.json
```

### Advanced Options

```bash
# Overwrite existing S3 files
python scripts/jd-initial-backend-data-s3-sync.py --overwrite

# Use custom S3 bucket
python scripts/jd-initial-backend-data-s3-sync.py --bucket my-bucket

# Adjust timeout for slow connections
python scripts/jd-initial-backend-data-s3-sync.py --timeout 30

# Combine options
python scripts/jd-initial-backend-data-s3-sync.py --target app --overwrite --timeout 20
```

## Command-Line Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--target` | choice | `backend` | Target location: `backend` or `app` |
| `--path` | string | - | Custom path to JSON file(s) (overrides `--target`) |
| `--overwrite` | flag | `False` | Overwrite existing files in S3 |
| `--bucket` | string | `dojo-spas-artifacts` | S3 bucket name |
| `--timeout` | integer | `10` | HTTP request timeout in seconds |

### Target Locations

- **`backend`**: `dojo-bench-customer-colossus/initial-backend-data/jd/`
- **`app`**: `jd/app/`
- **Custom path**: Any file or directory specified with `--path`

## How It Works

### 1. URL Extraction
- Recursively scans JSON files for all HTTP/HTTPS URLs
- Tracks the JSON path for each URL (e.g., `products[2].images[1]`)
- **Skips S3 URLs** from the configured bucket (already migrated)

### 2. Link Validation
- Tests each unique URL with HEAD request (falls back to GET if needed)
- Implements retry logic for transient failures
- Caches results to avoid duplicate checks
- Categorizes links as working or broken

### 3. Severity Analysis

Broken links are categorized by impact:

| Severity | Condition | Impact |
|----------|-----------|--------|
| 🔴 **Red (Critical)** | Not in an array OR all items in array are broken | High - No alternatives available |
| 🟡 **Yellow (Warning)** | Multiple items in array are broken (but not all) | Medium - Some alternatives remain |
| 🟢 **Green (Low)** | Only 1 item in array is broken | Low - Other working items available |

**Validation Rule**: Script fails with exit code 1 if **any Red (critical) items** are found.

### 4. S3 Key Generation

Keys are generated deterministically based on JSON structure:

**Format**: `jd/{parent_id}/{path}/{extension}`

**Examples**:

| JSON Path | Parent `_id` | Original URL | S3 Key |
|-----------|-------------|--------------|--------|
| `products[2].images[1]` | `prod-abc123` | `https://example.com/img.jpg` | `jd/prod-abc123/products/2/images/1.jpg` |
| `stores[0].logo` | `store-xyz789` | `https://example.com/logo.png` | `jd/store-xyz789/stores/0/logo.png` |

**Key Generation Rules**:
1. Find nearest parent object with `_id` (priority) or `id`
2. Build path from JSON structure (keys and array indices)
3. Preserve file extension from original URL
4. Fallback to `jd/no-id/{filename}` if no parent ID found

### 5. S3 Upload

For each working URL:
1. Check if S3 object already exists (skip if `--overwrite` not set)
2. Download image content from original URL
3. Determine content type from file extension
4. Upload to S3 with appropriate metadata

### 6. JSON File Update

After successful uploads:
1. **Replace working URLs** with S3 HTTPS URLs:
   - Format: `https://dojo-spas-artifacts.s3.amazonaws.com/jd/...`
2. **Remove broken URLs** from arrays (drop the array element entirely)
3. **Preserve original format**:
   - Unicode escapes (`\u5b8c`) → remains Unicode escaped
   - UTF-8 characters (`完全`) → remains UTF-8
4. Write back to original file

## Output Examples

### Successful Run

```
JD Initial Backend Data - Link Checker & S3 Uploader
================================================================================
Target: backend
Checking links in: /path/to/dojo-bench-customer-colossus/initial-backend-data/jd
S3 Bucket: dojo-spas-artifacts
Overwrite mode: OFF

Found 36 JSON files
================================================================================

[1/2] Extracting URLs from JSON files...
Found 150 unique URLs (excluding S3 URLs from dojo-spas-artifacts)

[2/2] Checking URLs...
  [1/150] HTTP 200             https://img11.360buyimg.com/n1/s720x720_jfs/...
  [2/150] HTTP 200             https://images.unsplash.com/photo-...
  ...

================================================================================
SUMMARY
================================================================================
JSON files processed: 36
Total unique URLs: 150
Working URLs: 145 (96.7%)
Broken URLs: 5 (3.3%)

--------------------------------------------------------------------------------
BROKEN URLS BY SEVERITY
--------------------------------------------------------------------------------
🔴 Red (0): Not in array OR all items in array broken
🟡 Yellow (2): Multiple items in array broken
🟢 Green (3): Single item in array broken

🟡 YELLOW - WARNING
  HTTP 404             https://example.com/image1.jpg
    └─ 2/6 broken in array - products[5].images

🟢 GREEN - LOW IMPACT
  HTTP 404             https://example.com/review.jpg
    └─ Only 1/5 broken in array - reviews[2].images

================================================================================
S3 UPLOAD
================================================================================
Bucket: s3://dojo-spas-artifacts/
Overwrite mode: OFF

Uploading 145 files...
[1/145] jd/prod-a1b2c3/images/0.jpg
  ✅ Uploaded successfully
[2/145] jd/prod-a1b2c3/images/1.jpg
  ⏭️  Already exists (skipped)
...

--------------------------------------------------------------------------------
UPLOAD SUMMARY
--------------------------------------------------------------------------------
✅ Uploaded: 120
⏭️  Skipped (already exists): 25
❌ Failed: 0

================================================================================
UPDATING JSON FILES
================================================================================
  ✅ Updated add_a_product_from_search_result_to_cart_backend.json
  ✅ Updated search_for_apple_iphone_backend.json
  ...

--------------------------------------------------------------------------------
UPDATE SUMMARY
--------------------------------------------------------------------------------
Files updated: 36
URLs replaced with S3 links: 145
Broken URLs removed from arrays: 5

================================================================================
✅ VALIDATION PASSED - No critical issues found
================================================================================
```

### Already Migrated Data

```
Found 36 JSON files
================================================================================

[1/2] Extracting URLs from JSON files...
Found 0 unique URLs (excluding S3 URLs from dojo-spas-artifacts)

[2/2] Checking URLs...

================================================================================
SUMMARY
================================================================================
JSON files processed: 36
Total unique URLs: 0
Working URLs: 0
Broken URLs: 0

ℹ️  No external URLs found - all URLs are already S3 links from the configured bucket

================================================================================
✅ VALIDATION PASSED - No critical issues found
================================================================================
```

### Critical Issues Found

```
🔴 RED - CRITICAL
  HTTP 404             https://example.com/logo.png
    └─ Not in array - stores[0].logo

  Connection Error     https://example.com/banner.jpg
    └─ All 3 items in array broken - products[5].images

================================================================================
❌ VALIDATION FAILED - Critical (red) URLs found
================================================================================

Script will exit with code 1 to prevent next steps.
Please fix critical URLs before proceeding.
```

## Workflow

### Initial Migration

1. Run script on original data with external URLs
2. Script validates all links
3. If critical issues found, fix them first
4. Working URLs are uploaded to S3
5. JSON files are updated with S3 URLs
6. Commit the updated JSON files

### Subsequent Runs

1. Script detects existing S3 URLs and skips them
2. Only new external URLs (if any) are processed
3. Safe to run multiple times - idempotent

### Re-running After Partial Failure

If uploads fail partway through:
1. Re-run the script (without `--overwrite`)
2. Already-uploaded files are skipped
3. Failed uploads are retried
4. JSON files are only updated after all uploads succeed

## Error Handling

### Exit Codes

- **0**: Success - no critical issues
- **1**: Failure - critical URLs found OR upload/update errors

### Common Issues

**Issue**: `ZeroDivisionError` in summary
- **Cause**: All URLs already migrated (total_urls = 0)
- **Fix**: Already fixed in script - shows info message

**Issue**: `Not a directory` error when writing files
- **Cause**: File path construction bug with single files
- **Fix**: Already fixed - uses stored file paths

**Issue**: Unicode characters changed in git
- **Cause**: Inconsistent `ensure_ascii` setting
- **Fix**: Already fixed - detects and preserves original format

**Issue**: `Broken non-array URL found` error
- **Shouldn't happen**: Script fails before upload if red items exist
- **Fix**: Check validation logic - red items should block upload

## Best Practices

1. **Run on clean branch**: Commit or stash changes before running
2. **Review git diff**: Check the URL replacements before committing
3. **Test with `--target app` first**: Smaller dataset for testing
4. **Use default settings first**: Only use `--overwrite` if needed
5. **Monitor output**: Watch for failed uploads or update errors
6. **Commit incrementally**: If processing large datasets, commit after each target

## Troubleshooting

### Slow Performance

- Increase timeout: `--timeout 30`
- Run on faster network connection
- Process subsets using `--path`

### AWS Credentials Issues

```bash
# Verify credentials
aws s3 ls s3://dojo-spas-artifacts/

# Check boto3 can access
python -c "import boto3; print(boto3.client('s3').list_buckets())"
```

### JSON Format Issues

- Script auto-detects format (Unicode vs UTF-8)
- If issues persist, check for mixed formats in single file
- Manually standardize format before running

## Technical Details

### Dependencies

- **boto3**: AWS SDK for S3 operations
- **requests**: HTTP client for downloading images
- **urllib3**: Retry logic for failed requests

### S3 Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:HeadObject"
      ],
      "Resource": "arn:aws:s3:::dojo-spas-artifacts/jd/*"
    }
  ]
}
```

### File Format Detection

The script detects original JSON encoding:
- Checks for `\u` escape sequences
- Checks for raw UTF-8 characters (ord > 127)
- Preserves original format when writing back

### Idempotency

The script is safe to run multiple times:
1. S3 URL detection skips already-migrated URLs
2. S3 existence check skips uploaded files (unless `--overwrite`)
3. No side effects if no external URLs found

## Maintenance

### Adding New Targets

Edit the `main()` function to add new target locations:

```python
elif args.target == 'new_target':
    jd_data_dir = project_root / "path" / "to" / "new" / "location"
```

### Modifying S3 Key Format

Edit the `generate_s3_key()` method to change key structure.

### Changing Content Type Mapping

Edit `content_type_map` in `download_and_upload_to_s3()` method.

## License

Internal tool for Dojo project.
