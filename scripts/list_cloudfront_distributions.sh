#!/bin/bash
aws cloudfront list-distributions --query "DistributionList.Items[*].{Id:Id,Domain:DomainName,OriginId:Origins.Items[0].Id,OriginPath:Origins.Items[0].OriginPath,S3Bucket:Origins.Items[0].DomainName}" --output table
