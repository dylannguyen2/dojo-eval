#!/bin/bash

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    print_error "jq is not installed. Please install it to parse JSON config."
    print_info "Install with: brew install jq (macOS) or apt-get install jq (Linux)"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CONFIG_FILE="${SCRIPT_DIR}/copy-config.json"

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    print_error "Config file not found: $CONFIG_FILE"
    exit 1
fi

print_info "Reading configuration from: $CONFIG_FILE"

# Parse config
SOURCE_REPO=$(jq -r '.source_repo' "$CONFIG_FILE")
TARGET_REPO=$(jq -r '.target_repo' "$CONFIG_FILE")

SOURCE_PATH="${SCRIPT_DIR}/${SOURCE_REPO}"
TARGET_PATH="${SCRIPT_DIR}/${TARGET_REPO}"

# Validate source and target paths
if [ ! -d "$SOURCE_PATH" ]; then
    print_error "Source repository not found: $SOURCE_PATH"
    exit 1
fi

if [ ! -d "$TARGET_PATH" ]; then
    print_error "Target repository not found: $TARGET_PATH"
    exit 1
fi

print_info "Source: $SOURCE_PATH"
print_info "Target: $TARGET_PATH"
echo ""

# Function to copy directory with rsync
copy_directory() {
    local src="$1"
    local dest="$2"
    local name="$3"

    if [ ! -d "$src" ]; then
        print_warning "Source directory not found: $src"
        return 1
    fi

    print_info "Copying $name..."

    # Create parent directory if it doesn't exist
    mkdir -p "$(dirname "$dest")"

    # Use rsync for efficient copying
    # -a: archive mode (preserves permissions, timestamps, etc.)
    # -v: verbose
    # --delete: delete files in dest that don't exist in src
    if rsync -av --delete "$src/" "$dest/"; then
        print_success "Copied $name to $dest"
        return 0
    else
        print_error "Failed to copy $name"
        return 1
    fi
}

# Function to copy file
copy_file() {
    local src="$1"
    local dest="$2"
    local name="$3"

    if [ ! -f "$src" ]; then
        print_warning "Source file not found: $src"
        return 1
    fi

    print_info "Copying $name..."

    # Create parent directory if it doesn't exist
    mkdir -p "$(dirname "$dest")"

    if cp "$src" "$dest"; then
        print_success "Copied $name to $dest"
        return 0
    else
        print_error "Failed to copy $name"
        return 1
    fi
}

# Copy directories (dojo-hooks, hooks-example)
print_info "=== Copying directories ==="
echo ""

DIR_COUNT=$(jq '.directories_to_copy | length' "$CONFIG_FILE")
for ((i=0; i<$DIR_COUNT; i++)); do
    DIR_NAME=$(jq -r ".directories_to_copy[$i].name" "$CONFIG_FILE")
    DIR_DESC=$(jq -r ".directories_to_copy[$i].description" "$CONFIG_FILE")

    SRC="${SOURCE_PATH}/${DIR_NAME}"
    DEST="${TARGET_PATH}/${DIR_NAME}"

    copy_directory "$SRC" "$DEST" "$DIR_NAME ($DIR_DESC)"
    echo ""
done

# Copy apps (jd, weibo, xiaohongshu)
print_info "=== Copying apps ==="
echo ""

APP_COUNT=$(jq '.apps_to_copy | length' "$CONFIG_FILE")
for ((i=0; i<$APP_COUNT; i++)); do
    APP_NAME=$(jq -r ".apps_to_copy[$i].name" "$CONFIG_FILE")
    APP_DESC=$(jq -r ".apps_to_copy[$i].description" "$CONFIG_FILE")

    SRC="${SOURCE_PATH}/${APP_NAME}"
    DEST="${TARGET_PATH}/${APP_NAME}"

    copy_directory "$SRC" "$DEST" "$APP_NAME ($APP_DESC)"
    echo ""
done

# Copy scripts
print_info "=== Copying scripts ==="
echo ""

# Ensure scripts directory exists in target
mkdir -p "${TARGET_PATH}/scripts"

SCRIPT_COUNT=$(jq '.scripts_to_copy | length' "$CONFIG_FILE")
for ((i=0; i<$SCRIPT_COUNT; i++)); do
    SCRIPT_NAME=$(jq -r ".scripts_to_copy[$i].name" "$CONFIG_FILE")
    SCRIPT_DESC=$(jq -r ".scripts_to_copy[$i].description" "$CONFIG_FILE")

    SRC="${SOURCE_PATH}/scripts/${SCRIPT_NAME}"
    DEST="${TARGET_PATH}/scripts/${SCRIPT_NAME}"

    copy_file "$SRC" "$DEST" "$SCRIPT_NAME ($SCRIPT_DESC)"
    echo ""
done

print_success "=== Copy operation completed ==="
print_info "Summary:"
print_info "  - Copied $DIR_COUNT directories"
print_info "  - Copied $APP_COUNT apps"
print_info "  - Copied $SCRIPT_COUNT scripts"
