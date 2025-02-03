from fastapi import UploadFile, HTTPException
import boto3
from book_api.settings import config
from book_api.models import User, Book
import magic
import io
from PIL import Image
from datetime import datetime
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileService:
    """Handles all file operations for the Book API."""
    
    def __init__(self, db_session):
        logger.info("Initializing FileService")
        # Core attributes
        self.s3_client = boto3.client('s3', **config.s3_credentials)
        self.db = db_session
        
        # Configuration
        self.allowed_types = ['image/jpeg', 'image/png', 'image/webp']
        self.max_sizes = {
            'profile': 5 * 1024 * 1024,  # 5MB
            'cover': 10 * 1024 * 1024    # 10MB
        }
        self.image_limits = {
            'profile': (800, 800),    # max dimensions
            'cover': (1500, 2000)     # max dimensions
        }
        self._create_image_bucket()

    def _create_image_bucket(self, bucket_name: str = config.AWS_BUCKET_NAME) -> None:
        """Creates the S3 bucket for storing images"""

        # if the bucket already exists, return
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket {bucket_name} already exists")
            return
        except self.s3_client.exceptions.ClientError as e:
            if e.response['Error']['Code'] != '404':
                logger.error(f"Error checking bucket {bucket_name}: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f'Error checking bucket: {str(e)}'
                )
            else:
                # Create the bucket
                try:
                    self.s3_client.create_bucket(Bucket=bucket_name)
                    logger.info(f"Successfully created bucket {bucket_name}")
                except Exception as e:
                    logger.error(f"Error creating bucket {bucket_name}: {str(e)}")
                    raise HTTPException(
                        status_code=500,
                        detail=f'Error creating bucket: {str(e)}'
                    )
                

    async def upload_profile_picture(self, user_id: int, file: UploadFile) -> dict:
        logger.info(f"Processing profile picture upload for user {user_id}")
        # check if the user exists
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User {user_id} not found")
            raise HTTPException(status_code=404, detail='User not found.')
        
        try:
            validated_file = await self._validate_file(file, 'profile')
            processed_image = await self._process_image(validated_file, 'profile')
            
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            unique_id = str(uuid.uuid4())[:8]
            key = f"profiles/{user_id}/{timestamp}_{unique_id}.jpg"

            if user.profile_picture:
                logger.info(f"Deleting old profile picture: {user.profile_picture}")
                await self.delete_file(user.profile_picture)

            user.profile_picture = await self._save_to_s3(processed_image, key)
            self.db.commit()
            self.db.refresh(user)
            
            logger.info(f"Successfully uploaded profile picture for user {user_id}")
            return {
                "profile_picture": user.profile_picture
            }
        except Exception as e:
            logger.error(f"Error in upload_profile_picture: {str(e)}")
            raise

    async def upload_book_cover(self, book_id: int, file: UploadFile) -> dict:
        logger.info(f"Processing book cover upload for book {book_id}")
        # check if the book exists
        book = self.db.query(Book).filter(Book.id == book_id).first()
        if not book:
            logger.error(f"Book {book_id} not found")
            raise HTTPException(status_code=404, detail='Book not found.')
        
        try:
            validated_file = await self._validate_file(file, 'cover')
            processed_image = await self._process_image(validated_file, 'cover')

            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            unique_id = str(uuid.uuid4())[:8]
            key = f"covers/{book_id}/{timestamp}_{unique_id}.jpg"

            if book.cover_url:
                logger.info(f"Deleting old book cover: {book.cover}")
                await self.delete_file(book.cover)

            book.cover_url = await self._save_to_s3(processed_image, key)
            self.db.commit()
            self.db.refresh(book)
            
            logger.info(f"Successfully uploaded cover for book {book_id}")
            return {
                "cover_url": book.cover_url
            }
        except Exception as e:
            logger.error(f"Error in upload_book_cover: {str(e)}")
            raise

    async def get_file(self, file_url: str) -> dict:
        """Get file from S3 using the full URL"""
        logger.info(f"Getting file from URL: {file_url}")
        
        # Extract key from URL
        try:
            key = file_url.split(f"{config.AWS_BUCKET_NAME}.s3.amazonaws.com/")[1]
        except IndexError:
            logger.error(f"Invalid file URL format: {file_url}")
            raise HTTPException(status_code=400, detail='Invalid file URL format')
        
        # Validate the file key
        if not key.startswith(('profiles/', 'covers/')):
            logger.error(f"Invalid file path: {key}")
            raise HTTPException(status_code=400, detail='Invalid file path')
        
        try:
            # Get file from S3
            response = self.s3_client.get_object(
                Bucket=config.AWS_BUCKET_NAME,
                Key=key
            )
            logger.info(f"Successfully retrieved file: {key}")
            return response
        except Exception as e:
            logger.error(f"Error getting file {key}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f'Error getting file: {str(e)}'
            )
        
    async def delete_file(self, file_url: str) -> bool:
        """Delete file from S3 using the full URL"""
        logger.info(f"Attempting to delete file from URL: {file_url}")
        
        # Extract key from URL
        try:
            key = file_url.split(f"{config.AWS_BUCKET_NAME}.s3.amazonaws.com/")[1]
        except IndexError:
            logger.error(f"Invalid file URL format: {file_url}")
            raise HTTPException(status_code=400, detail='Invalid file URL format')
            
        # Validate the file key
        if not key.startswith(('profiles/', 'covers/')):
            logger.error(f"Invalid file path: {key}")
            raise HTTPException(status_code=400, detail='Invalid file path')
                
        try:
            # Delete from S3
            try:
                self.s3_client.head_object(
                    Bucket=config.AWS_BUCKET_NAME,
                    Key=key
                )
                self.s3_client.delete_object(
                    Bucket=config.AWS_BUCKET_NAME,
                    Key=key
                )
                logger.info(f"Successfully deleted file: {key}")
                return True
            except self.s3_client.exceptions.ClientError as e:
                if e.response['Error']['Code'] == '404':
                    logger.info(f"File {key} does not exist")
                    return True
                raise
                
        except Exception as e:
            logger.error(f"Error deleting file {key}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f'Error deleting file: {str(e)}'
            )

    async def replace_file(self, old_url: str, new_file: UploadFile, type: str) -> dict:
        """Replace existing file with new one using the full URL"""
        logger.info(f"Replacing file {old_url} with new file")
        
        # Extract key from URL
        try:
            old_key = old_url.split(f"{config.AWS_BUCKET_NAME}.s3.amazonaws.com/")[1]
        except IndexError:
            logger.error(f"Invalid file URL format: {old_url}")
            raise HTTPException(status_code=400, detail='Invalid file URL format')

        # Validate the file path
        if not old_key.startswith(('profiles/', 'covers/')):
            logger.error(f"Invalid file path: {old_key}")
            raise HTTPException(status_code=400, detail='Invalid file path')
                
        try:
            # Process new file first
            validated_file = await self._validate_file(new_file, type)
            processed_image = await self._process_image(validated_file, type)
            
            # Generate new key maintaining the same path structure
            path_parts = old_key.split('/')
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            unique_id = str(uuid.uuid4())[:8]
            new_key = f"{path_parts[0]}/{path_parts[1]}/{timestamp}_{unique_id}.jpg"
            
            # Upload new file
            new_url = await self._save_to_s3(processed_image, new_key)
            
            # If successful, delete old file
            await self.delete_file(old_url)
            
            logger.info(f"Successfully replaced file {old_key} with {new_key}")
            return {
                "url": new_url,
                "key": new_key
            }
                
        except Exception as e:
            logger.error(f"Error replacing file {old_key}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f'Error replacing file: {str(e)}'
            )

    async def _validate_file(self, file: UploadFile, type: str) -> bytes:
        logger.info(f"Validating file of type {type}")
        # check if file exists
        if not file:
            logger.error("No file provided")
            raise HTTPException(status_code=400, detail='No file provided.')

        # read file once
        await file.seek(0)
        content = await file.read()
        file_size = len(content)
        logger.info(f"File size: {file_size} bytes")

        # check if file size is within limits
        if file_size > self.max_sizes[type]:
            logger.error(f"File size {file_size} exceeds limit of {self.max_sizes[type]}")
            raise HTTPException(status_code=400, detail='File size too large.')

        # check mime type
        mime_type = magic.from_buffer(content, mime=True)
        logger.info(f"Detected MIME type: {mime_type}")
        if mime_type not in self.allowed_types:
            logger.error(f"Invalid file type: {mime_type}")
            raise HTTPException(status_code=400, detail='Invalid file type.')

        # try to open and validate image
        try:
            image = Image.open(io.BytesIO(content))
            image.verify()  # Verify it's a valid image
        except Exception as e:
            logger.error(f"Invalid image file: {str(e)}")
            raise HTTPException(status_code=400, detail='Invalid image file.')

        # strip metadata and convert to standard format
        try:
            image = Image.open(io.BytesIO(content))  # Need to reopen after verify
            # Strip metadata by creating new image
            image_data = list(image.getdata())
            clean_image = Image.new(image.mode, image.size)
            clean_image.putdata(image_data)
            
            # Convert to JPEG format
            buffer = io.BytesIO()
            clean_image.save(buffer, format='JPEG', quality=85)

            # Store content in memory for reuse
            file._content = content # Cache content
            await file.seek(0) # Reset for future reads

            return buffer.getvalue()
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            raise HTTPException(status_code=400, detail=f'Error processing image: {str(e)}')
            

    async def _process_image(self, content: bytes, type: str) -> bytes:
        logger.info(f"Processing image of type {type}")
        # open the image and resize it to fit the limits depending on the type
        image = Image.open(io.BytesIO(content))
        original_size = image.size
        image.thumbnail(self.image_limits[type],  Image.Resampling.LANCZOS)
        logger.info(f"Resized image from {original_size} to {image.size}")

        # convert the image to bytes
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG')
        return buffer.getvalue()

    async def _save_to_s3(self, content: bytes, key: str) -> str:
        logger.info(f"Uploading file to S3: {key}")
        try:
            self.s3_client.put_object(
                Bucket=config.AWS_BUCKET_NAME,
                Key=key,
                Body=content,
                ContentType='image/jpeg'
            )
            logger.info(f"Successfully uploaded file to S3: {key}")
            return f'https://{config.AWS_BUCKET_NAME}.s3.amazonaws.com/{key}'
        except Exception as e:
            logger.error(f"Error uploading to S3 {key}: {str(e)}")
            raise HTTPException(status_code=500, detail=f'Error uploading file: {str(e)}')
