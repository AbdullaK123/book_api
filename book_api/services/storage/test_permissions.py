import boto3
import logging
from botocore.exceptions import ClientError
from book_api.settings import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_s3_permissions():
    try:
        s3 = boto3.client('s3',
            aws_access_key_id=config.AWS_ACCESS_KEY,
            aws_secret_access_key=config.AWS_SECRET_KEY,
            region_name=config.AWS_REGION
        )
        
        # Test 1: Can we list buckets?
        logger.info("Testing ListBuckets permission...")
        buckets = s3.list_buckets()
        logger.info(f"Success! Found {len(buckets['Buckets'])} buckets")
        
        bucket_name = config.AWS_BUCKET_NAME
        
        # Test 2: Can we access the specific bucket?
        logger.info(f"Testing HeadBucket for {bucket_name}...")
        try:
            s3.head_bucket(Bucket=bucket_name)
            logger.info("Success! Can access bucket")
        except ClientError as e:
            logger.error(f"Failed to access bucket: {str(e)}")
            
        # Test 3: Can we list objects?
        logger.info("Testing ListObjects permission...")
        try:
            objects = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
            logger.info("Success! Can list objects")
        except ClientError as e:
            logger.error(f"Failed to list objects: {str(e)}")
            
        # Test 4: Try to put a test object
        logger.info("Testing PutObject permission...")
        try:
            s3.put_object(
                Bucket=bucket_name,
                Key='test/permissions_check.txt',
                Body='Testing permissions'
            )
            logger.info("Success! Can put objects")
        except ClientError as e:
            logger.error(f"Failed to put object: {str(e)}")
            
    except Exception as e:
        logger.error(f"General error: {str(e)}")

test_s3_permissions()