from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    # AWS Settings
    AWS_ACCESS_KEY: str
    AWS_SECRET_KEY: str
    AWS_REGION: str = "us-east-1"  # Default region if none specified
    AWS_BUCKET_NAME: str = "bookapi-images"  # Default bucket name
    
    # Upload Limits
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB default
    ALLOWED_EXTENSIONS: set = {"jpg", "jpeg", "png", "webp"}
    
    # Security Settings
    SECRET_KEY: str
    ALGORITHM: str = "HS256"  # Default to HS256
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # Default to 30 minutes
    
    # Database Settings (if you have any)
    DATABASE_URL: str
    
    class Config:
        env_file = ".env"
        case_sensitive = True  # AWS keys are case sensitive

    @property
    def s3_credentials(self):
        """Helper to get AWS credentials as dict"""
        return {
            "aws_access_key_id": self.AWS_ACCESS_KEY,
            "aws_secret_access_key": self.AWS_SECRET_KEY,
            "region_name": self.AWS_REGION
        }

config = Settings()