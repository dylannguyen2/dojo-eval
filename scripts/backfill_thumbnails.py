import json
import boto3
import cv2
import tempfile
import os
from urllib.parse import urlparse
from botocore.exceptions import ClientError

def process_posts(json_file_path: str, output_file_path: str = None):
    """
    Process posts JSON file, extract first frames from videos,
    upload as thumbnails to S3, and update the JSON.
    """
    s3 = boto3.client('s3')
    
    # Load the JSON file
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    posts = data.get('posts', [])
    processed_count = 0
    skipped_count = 0
    
    for post in posts:
        # Check if this is a video post with an mp4 file
        if post.get('type') != 'video':
            continue
        
        media_url = post.get('media', '')
        if not media_url.endswith('.mp4'):
            continue
        
        print(f"Processing post {post.get('_id')}: {post.get('title')}")
        
        try:
            # Parse the S3 URL
            parsed = urlparse(media_url)
            bucket_name = parsed.netloc.split('.')[0]
            video_key = parsed.path.lstrip('/')
            
            # Create thumbnail key (same path, different extension)
            thumbnail_key = video_key.rsplit('.', 1)[0] + '.jpg'
            thumbnail_url = f"https://{bucket_name}.s3.amazonaws.com/{thumbnail_key}"
            
            # Check if thumbnail already exists
            try:
                s3.head_object(Bucket=bucket_name, Key=thumbnail_key)
                print(f"  Thumbnail already exists, skipping: {thumbnail_url}")
                post['thumbnail'] = thumbnail_url
                skipped_count += 1
                continue
            except ClientError as e:
                if e.response['Error']['Code'] != '404':
                    raise
                # 404 means it doesn't exist, continue with processing
            
            # Download video to temp file
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_video:
                tmp_video_path = tmp_video.name
                print(f"  Downloading video from s3://{bucket_name}/{video_key}")
                s3.download_file(bucket_name, video_key, tmp_video_path)
            
            # Extract first frame using OpenCV
            cap = cv2.VideoCapture(tmp_video_path)
            success, frame = cap.read()
            cap.release()
            
            if not success:
                print(f"  Failed to read video frame for post {post.get('_id')}")
                os.unlink(tmp_video_path)
                continue
            
            # Save frame as JPEG
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_thumb:
                tmp_thumb_path = tmp_thumb.name
                cv2.imwrite(tmp_thumb_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            
            # Upload thumbnail to S3
            print(f"  Uploading thumbnail to s3://{bucket_name}/{thumbnail_key}")
            s3.upload_file(
                tmp_thumb_path, 
                bucket_name, 
                thumbnail_key,
                ExtraArgs={'ContentType': 'image/jpeg'}
            )
            
            # Update the post with thumbnail URL
            post['thumbnail'] = thumbnail_url
            processed_count += 1
            print(f"  Done: {thumbnail_url}")
            
            # Cleanup temp files
            os.unlink(tmp_video_path)
            os.unlink(tmp_thumb_path)
            
        except Exception as e:
            print(f"  Error processing post {post.get('_id')}: {e}")
            continue
    
    # Save updated JSON
    output_path = output_file_path or json_file_path
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\nProcessed {processed_count} new thumbnails")
    print(f"Skipped {skipped_count} existing thumbnails")
    print(f"Updated JSON saved to: {output_path}")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python generate_thumbnails.py <input.json> [output.json]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    process_posts(input_file, output_file)