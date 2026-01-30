#!/usr/bin/env python3
"""Browse Massive S3 flat files for options data"""

import boto3
import gzip
import io
from botocore.config import Config

# Massive S3 credentials
ACCESS_KEY = "6a891d8e-f7dd-4c83-a2ca-979df54b9c8b"
SECRET_KEY = "Td9cMGlx_c1vqpBuvxT_qVUu3P3730cc"
ENDPOINT = "https://files.massive.com"
BUCKET = "flatfiles"

s3 = boto3.client(
    's3',
    endpoint_url=ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    config=Config(signature_version='s3v4')
)

# Check recent data (2025)
print("=== Recent Options Day Aggs (2025) ===")
response = s3.list_objects_v2(Bucket=BUCKET, Prefix='us_options_opra/day_aggs_v1/2025/', MaxKeys=10)
for obj in response.get('Contents', []):
    print(f"  {obj['Key']} ({obj['Size']:,} bytes)")

# Check 2026 data
print("\n=== 2026 Options Data ===")
response = s3.list_objects_v2(Bucket=BUCKET, Prefix='us_options_opra/day_aggs_v1/2026/', MaxKeys=10)
for obj in response.get('Contents', []):
    print(f"  {obj['Key']} ({obj['Size']:,} bytes)")

# Download a sample file and show structure
print("\n=== Sample Data Structure (2025-01-02) ===")
response = s3.get_object(Bucket=BUCKET, Key='us_options_opra/day_aggs_v1/2025/01/2025-01-02.csv.gz')
with gzip.GzipFile(fileobj=io.BytesIO(response['Body'].read())) as f:
    lines = f.read().decode('utf-8').split('\n')[:20]
    for line in lines:
        print(line)

# Check for SPX specifically
print("\n=== SPX Options Sample ===")
response = s3.get_object(Bucket=BUCKET, Key='us_options_opra/day_aggs_v1/2025/01/2025-01-02.csv.gz')
with gzip.GzipFile(fileobj=io.BytesIO(response['Body'].read())) as f:
    content = f.read().decode('utf-8')
    lines = [l for l in content.split('\n') if 'SPX' in l or 'SPXW' in l][:10]
    print(f"Found {len([l for l in content.split(chr(10)) if 'SPX' in l])} SPX/SPXW lines")
    for line in lines:
        print(line)
