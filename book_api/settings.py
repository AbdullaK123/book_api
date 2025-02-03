from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv
from fastapi_mail import ConnectionConfig
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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 5  # Default to 30 minutes
    
    # Database Settings (if you have any)
    DATABASE_URL: str

    # Email Settings
    MAIL_FROM: str
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_STARTTLS: bool
    MAIL_SSL_TLS: bool
    USE_CREDENTIALS: bool
    VALIDATE_CERTS: bool
    FRONTEND_URL: Optional[str] = None 


    class Config:
        env_file = ".env"
        case_sensitive = True  # AWS keys are case sensitive

    @property
    def email_config(self):
        """Helper to get email configuration"""
        return ConnectionConfig(
            MAIL_USERNAME=self.MAIL_USERNAME,
            MAIL_PASSWORD=self.MAIL_PASSWORD,
            MAIL_FROM=self.MAIL_FROM,
            MAIL_PORT=self.MAIL_PORT,
            MAIL_SERVER=self.MAIL_SERVER,
            MAIL_STARTTLS=self.MAIL_STARTTLS,
            MAIL_SSL_TLS=self.MAIL_SSL_TLS,
            USE_CREDENTIALS=self.USE_CREDENTIALS,
            VALIDATE_CERTS=self.VALIDATE_CERTS
        )

    @property
    def s3_credentials(self):
        """Helper to get AWS credentials as dict"""
        return {
            "aws_access_key_id": self.AWS_ACCESS_KEY,
            "aws_secret_access_key": self.AWS_SECRET_KEY,
            "region_name": self.AWS_REGION
        }

config = Settings()