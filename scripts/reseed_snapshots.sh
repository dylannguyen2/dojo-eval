#!/bin/bash

set -e

# Parse arguments
ENV=""
TARGETS=()

while [[ $# -gt 0 ]]; do
  case $1 in
    --env)
      ENV="$2"
      shift 2
      ;;
    --targets)
      IFS=',' read -ra TARGETS <<< "$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 --env <staging|production> --targets <jd,weibo,xhs,notion>"
      exit 1
      ;;
  esac
done

# Validate env
if [[ "$ENV" != "staging" && "$ENV" != "production" ]]; then
  echo "Error: --env must be 'staging' or 'production'"
  exit 1
fi

# Validate targets
if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "Error: --targets is required (comma-separated: jd,weibo,xhs,notion)"
  exit 1
fi

# Switch kubectl context
echo "Switching to dojo-$ENV..."
kubectx "dojo-$ENV"

# Get the directory containing this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Process each target
for target in "${TARGETS[@]}"; do
  case $target in
    jd)
      echo "Reseeding jd..."
      kubectl delete volumesnapshot jd-default-seed-data --ignore-not-found
      kubectl delete volumesnapshot meilisearch-jd-default-seed-data --ignore-not-found
      uv run "$SCRIPT_DIR/seed.py" remote --path ../jd/app/initial_data.json --name "jd-default-seed-data" --env $ENV
      ;;
    weibo)
      echo "Reseeding weibo..."
      kubectl delete volumesnapshot weibo-default-seed-data --ignore-not-found
      kubectl delete volumesnapshot meilisearch-weibo-default-seed-data --ignore-not-found
      uv run "$SCRIPT_DIR/seed.py" remote --path ../weibo/app/initial_data.json --name "weibo-default-seed-data" --env $ENV
      ;;
    xhs)
      echo "Reseeding xhs..."
      kubectl delete volumesnapshot xhs-default-seed-data --ignore-not-found
      kubectl delete volumesnapshot meilisearch-xhs-default-seed-data --ignore-not-found
      uv run "$SCRIPT_DIR/seed.py" remote --path ../xiaohongshu/app/initial_data.json --name "xhs-default-seed-data" --env $ENV
      ;;
    notion)
      echo "Reseeding notion..."
      kubectl delete volumesnapshot notion-default-seed-data --ignore-not-found
      kubectl delete volumesnapshot meilisearch-notion-default-seed-data --ignore-not-found
      uv run "$SCRIPT_DIR/seed.py" remote --path ../notion/app/initial_data.json --name "notion-default-seed-data" --env $ENV
      ;;
    *)
      echo "Unknown target: $target (valid: jd, weibo, xhs, notion)"
      exit 1
      ;;
  esac
done

echo "Done!"