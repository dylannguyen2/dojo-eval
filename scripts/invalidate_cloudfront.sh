#!/bin/bash

# Usage: ./invalidate.sh <app-name> [demo] <staging|prod>
# Examples:
#   ./invalidate.sh gmail prod
#   ./invalidate.sh gmail demo prod
#   ./invalidate.sh taobao staging

APP_NAME="$1"
if [[ "$2" == "demo" ]]; then
  IS_DEMO=true
  ENV="$3"
else
  IS_DEMO=false
  ENV="$2"
fi

if [[ -z "$APP_NAME" || -z "$ENV" ]]; then
  echo "Usage: $0 <app-name> [demo] <staging|prod>"
  echo "Examples:"
  echo "  $0 gmail prod"
  echo "  $0 gmail demo staging"
  exit 1
fi

# Set bucket based on environment
if [[ "$ENV" == "prod" ]]; then
  BUCKET="dojo-spas-production"
elif [[ "$ENV" == "staging" ]]; then
  BUCKET="dojo-spas-staging"
else
  echo "Error: environment must be 'staging' or 'prod'"
  exit 1
fi

# Build origin path
if [[ "$IS_DEMO" == true ]]; then
  ORIGIN_PATH="/demo/$APP_NAME"
else
  ORIGIN_PATH="/$APP_NAME"
fi

# Find the distribution ID
DIST_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Origins.Items[0].DomainName=='${BUCKET}.s3.us-east-1.amazonaws.com' && Origins.Items[0].OriginPath=='${ORIGIN_PATH}'].Id | [0]" \
  --output text)

if [[ -z "$DIST_ID" || "$DIST_ID" == "None" ]]; then
  echo "Error: No distribution found for $APP_NAME (demo=$IS_DEMO) in $ENV"
  exit 1
fi

echo "Invalidating distribution $DIST_ID for $APP_NAME (demo=$IS_DEMO, env=$ENV)..."
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*"
