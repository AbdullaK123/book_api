# tests/test_storage.py
import pytest
from fastapi import HTTPException
from book_api.settings import config

class TestFileValidation:
    """Test file validation functionality"""

    @pytest.mark.asyncio
    async def test_valid_image_upload(self, file_service, test_image):
        """Should successfully validate a proper image"""
        validated = await file_service._validate_file(test_image, 'profile')
        assert validated is not None
        assert len(validated) > 0

    @pytest.mark.asyncio
    async def test_large_image_rejection(self, file_service, large_image):
        """Should reject images that exceed size limit"""
        with pytest.raises(HTTPException) as exc:
            await file_service._validate_file(large_image, 'profile')
        assert exc.value.status_code == 400
        assert 'File size' in exc.value.detail

    @pytest.mark.asyncio
    async def test_fake_image_rejection(self, file_service, fake_image):
        """Should reject non-image files with image extension"""
        with pytest.raises(HTTPException) as exc:
            await file_service._validate_file(fake_image, 'profile')
        assert exc.value.status_code == 400
        assert 'Invalid file type' in exc.value.detail

    @pytest.mark.asyncio
    async def test_corrupt_image_rejection(self, file_service, corrupt_image):
        """Should reject corrupted image files"""
        with pytest.raises(HTTPException) as exc:
            await file_service._validate_file(corrupt_image, 'profile')
        assert exc.value.status_code == 400
        assert 'Invalid image file' in exc.value.detail

class TestImageProcessing:
    """Test image processing functionality"""

    @pytest.mark.asyncio
    async def test_oversized_dimensions_resizing(self, file_service, oversized_image_dimensions):
        """Should resize images that exceed dimension limits"""
        validated = await file_service._validate_file(oversized_image_dimensions, 'profile')
        processed = await file_service._process_image(validated, 'profile')
        
        # Verify dimensions
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(processed))
        assert img.size[0] <= file_service.image_limits['profile'][0]
        assert img.size[1] <= file_service.image_limits['profile'][1]

    @pytest.mark.asyncio
    async def test_wrong_format_conversion(self, file_service, wrong_format):
        """Should convert PNG to JPEG"""
        validated = await file_service._validate_file(wrong_format, 'profile')
        processed = await file_service._process_image(validated, 'profile')
        
        # Verify JPEG format
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(processed))
        assert img.format == 'JPEG'

class TestS3Operations:
    """Test S3 storage operations"""
    @pytest.mark.asyncio
    async def test_get_file(self, file_service, test_user, test_image):
        """Should successfully retrieve file from S3"""
        
        # First upload
        result = await file_service.upload_profile_picture(test_user.id, test_image)
        url = result['profile_picture']
        
        # Then retrieve
        file = await file_service.get_file(url)
        assert file is not None

    @pytest.mark.asyncio
    async def test_successful_upload(self, file_service, test_image, test_user):
        """Should successfully upload file to S3"""
        result = await file_service.upload_profile_picture(test_user.id, test_image)
        assert result['profile_picture'].startswith(f'https://{config.AWS_BUCKET_NAME}')

    @pytest.mark.asyncio
    async def test_file_deletion(self, file_service, test_image, test_user):
        """Should successfully delete file from S3"""
        # First upload
        result = await file_service.upload_profile_picture(test_user.id, test_image)
        url = result['profile_picture']
        
        # Then delete
        success = await file_service.delete_file(url)
        assert success is True

    @pytest.mark.asyncio
    async def test_file_replacement(self, file_service, test_image, test_user):
        """Should successfully replace existing file"""
        # Upload initial file
        result = await file_service.upload_profile_picture(test_user.id, test_image)
        old_url = result['profile_picture']
        
        # Replace file
        new_result = await file_service.replace_file(old_url, test_image, 'profile')
        assert new_result['url'] != old_url
        assert new_result['url'].startswith(f'https://{config.AWS_BUCKET_NAME}')

class TestErrorCases:
    """Test various error scenarios"""

    @pytest.mark.asyncio
    async def test_nonexistent_user(self, file_service, test_image):
        """Should handle non-existent user gracefully"""
        with pytest.raises(HTTPException) as exc:
            await file_service.upload_profile_picture(99999, test_image)
        assert exc.value.status_code == 404
        assert 'User not found' in exc.value.detail

    @pytest.mark.asyncio
    async def test_invalid_file_url(self, file_service):
        """Should handle invalid file URLs gracefully"""
        invalid_url = 'https://invalid-bucket.s3.amazonaws.com/invalid/path.jpg'
        with pytest.raises(HTTPException) as exc:
            await file_service.delete_file(invalid_url)
        assert exc.value.status_code == 400
        assert 'Invalid file URL format' in exc.value.detail

    @pytest.mark.asyncio
    async def test_duplicate_upload(self, file_service, test_image, test_user):
        """Should handle duplicate uploads correctly"""
        # First upload
        result1 = await file_service.upload_profile_picture(test_user.id, test_image)
        # Second upload should succeed but return different URL
        result2 = await file_service.upload_profile_picture(test_user.id, test_image)
        assert result1['profile_picture'] != result2['profile_picture']