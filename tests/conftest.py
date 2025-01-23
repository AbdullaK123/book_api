import pytest
import asyncio
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime
from book_api.main import app
from book_api.database import Base, get_db
import io 
from PIL import Image
from fastapi import UploadFile
import boto3
from moto import mock_aws
from book_api.settings import config
from book_api.services.storage.file_service import FileService
import os
import random
import numpy as np

# Test database configuration
SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables in test database
Base.metadata.create_all(bind=engine)

# -------- Basic Fixtures --------

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for each test session"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
def db() -> Generator:
    """Get a TestingSessionLocal instance with transaction rollback"""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    session.execute(text("PRAGMA foreign_keys=ON;"))
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def mock_request_headers() -> dict:
    """Mock headers for token binding"""
    return {
        'User-Agent': 'Mozilla/5.0 (Test Browser)',
        'X-Device-Id': 'test-device-123',
        'Host': '127.0.0.1'
    }

@pytest.fixture
def client(db: TestingSessionLocal, mock_request_headers: dict) -> TestClient:
    """Get test client with database session and mocked headers"""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, headers=mock_request_headers) as c:
        yield c

# -------- Test Data Fixtures --------

@pytest.fixture
def user_data() -> dict:
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123",
        "role": "user"
    }

@pytest.fixture
def admin_data() -> dict:
    return {
        "username": "admin",
        "email": "admin@example.com",
        "password": "admin123",
        "role": "admin"
    }

@pytest.fixture
def book_data() -> dict:
    return {
        "title": "Test Book",
        "author": "Test Author",
        "publisher": "Test Publisher",
        "year": datetime.now().year,
        "genre": "Fiction",
        "page_count": 200
    }

@pytest.fixture
def review_data() -> dict:
    return {
        "rating": 5,
        "content": "Great book!"
    }

# -------- Authentication Fixtures --------

@pytest.fixture
def user_token(client: TestClient, user_data: dict, mock_request_headers: dict) -> str:
    """Create a user and get their token"""
    # Create user
    response = client.post(
        "/users/", 
        json=user_data,
        headers=mock_request_headers
    )
    assert response.status_code == 200

    # Login and get token
    login_response = client.post(
        "/users/login",
        data={
            "username": user_data["username"],
            "password": user_data["password"]
        },
        headers=mock_request_headers
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]

@pytest.fixture
def admin_token(client: TestClient, admin_data: dict, mock_request_headers: dict) -> str:
    """Create an admin and get their token"""
    response = client.post(
        "/users/", 
        json=admin_data,
        headers=mock_request_headers
    )
    assert response.status_code == 200

    login_response = client.post(
        "/users/login",
        data={
            "username": admin_data["username"],
            "password": admin_data["password"]
        },
        headers=mock_request_headers
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]

@pytest.fixture
def auth_headers(user_token: str, mock_request_headers: dict) -> dict:
    """Get headers for authenticated user"""
    return {
        "Authorization": f"Bearer {user_token}",
        **mock_request_headers
    }

@pytest.fixture
def admin_headers(admin_token: str, mock_request_headers: dict) -> dict:
    """Get headers for authenticated admin"""
    return {
        "Authorization": f"Bearer {admin_token}",
        **mock_request_headers
    }

# -------- Other Fixtures --------
@pytest.fixture
def test_users():
    return [
        {
            "username": "testuser",
            "email": "test_email1@gmail.com",
            "password": "testpass123",
            "role": "user"
        },
        {
            "username": "testuser2",
            "email": "test_email2@gmail.com",
            "password": "testpass1234",
            "role": "user"
        },
        {
            "username": "testuser3",
            "email": "test_email3@gmail.com",
            "password": "testpass12345",
            "role": "user"
        }
    ]

@pytest.fixture
def test_author():
    return {
        "username": "testauthor",
        "email": "testauthor@gmail.com",
        "password": "testpass123342",
        "role": "user"
    }

@pytest.fixture
def test_reviews():
    return [
        {
            "rating": 4,
            "content": "Great book!"
        },
        {
            "rating": 5,
            "content": "Awesome book!"
        },
        {
            "rating": 3,
            "content": "Good book!"
        }
    ]

@pytest.fixture
def second_user_data():
    """Fixture for creating a second test user"""
    return {
        "username": "testuser2",
        "email": "test2@example.com",
        "password": "testpass123",
        "role": "user"
    }


@pytest.fixture
def test_follow_user():
    return {
        "username": "testusertofollow",
        "email": "example@email.com",
        "password": "testpass123",
        "role": "user"
    }

@pytest.fixture
def test_unfollow_user():
    return {
        "username": "testuserunfollow",
        "email": "example22@email.com",
        "password": "testpass123",
        "role": "user"
    }

@pytest.fixture
def second_user_headers(client: TestClient, second_user_data: dict, mock_request_headers: dict):
    """Get headers for a second authenticated user"""
    # Create user
    response = client.post("/users/", json=second_user_data, headers=mock_request_headers)
    assert response.status_code == 200
    
    # Login
    response = client.post(
        "/users/login",
        data={
            "username": second_user_data["username"],
            "password": second_user_data["password"]
        },
        headers=mock_request_headers
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    
    return {
        "Authorization": f"Bearer {token}",
        **mock_request_headers
    }


@pytest.fixture
def book_author_headers(client: TestClient, admin_data: dict, mock_request_headers: dict):
    """Get headers for book author"""
    # Create user
    response = client.post("/users/", json=admin_data, headers=mock_request_headers)
    assert response.status_code == 200
    
    # Login
    response = client.post(
        "/users/login",
        data={
            "username": admin_data["username"],
            "password": admin_data["password"]
        },
        headers=mock_request_headers
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    
    return {
        "Authorization": f"Bearer {token}",
        **mock_request_headers
    }

@pytest.fixture
def test_review(client: TestClient, auth_headers: dict, book_data: dict, book_author_headers: dict):
    """Create a test review for GraphQL tests"""
    # First create a book with a different user
    book_response = client.post("/books/", json=book_data, headers=book_author_headers)
    assert book_response.status_code == 200
    book_id = book_response.json()["id"]
    
    # Create review with the test user
    review_data = {
        "book_id": book_id,
        "rating": 4,
        "content": "Test review for GraphQL tests"
    }
    review_response = client.post("/reviews/", json=review_data, headers=auth_headers)
    assert review_response.status_code == 200
    return review_response.json()

@pytest.fixture
def test_comment(client: TestClient, auth_headers: dict, test_review: dict):
    """Create a test comment for GraphQL tests"""
    mutation = """
    mutation {
        createComment(
            input: {
                content: "Test comment",
                reviewId: %d
            }
        ) {
            id
            content
        }
    }
    """ % test_review["id"]
    
    response = client.post(
        "/graphql",
        headers=auth_headers,
        json={"query": mutation}
    )
    result = response.json()
    assert "data" in result
    assert "errors" not in result
    return result["data"]["createComment"]

@pytest.fixture
def test_comments(client: TestClient, auth_headers: dict, test_review: dict):
    """Create multiple test comments for a review"""
    comments = []
    
    # Create multiple top-level comments
    for i in range(3):
        mutation = """
        mutation {
            createComment(
                input: {
                    content: "Test comment %d",
                    reviewId: %d
                }
            ) {
                id
                content
            }
        }
        """ % (i + 1, test_review["id"])
        
        response = client.post(
            "/graphql",
            headers=auth_headers,
            json={"query": mutation}
        )
        result = response.json()
        assert "data" in result
        assert "errors" not in result
        comments.append(result["data"]["createComment"])
    
    return comments

@pytest.fixture
def test_comment_with_replies(client: TestClient, auth_headers: dict, test_review: dict):
    """Create a test comment with multiple replies"""
    # Create parent comment
    parent_mutation = """
    mutation {
        createComment(
            input: {
                content: "Parent comment",
                reviewId: %d
            }
        ) {
            id
            content
        }
    }
    """ % test_review["id"]
    
    parent_response = client.post(
        "/graphql",
        headers=auth_headers,
        json={"query": parent_mutation}
    )
    parent_result = parent_response.json()
    assert "data" in parent_result
    parent_comment = parent_result["data"]["createComment"]
    
    # Create replies
    replies = []
    for i in range(3):
        reply_mutation = """
        mutation {
            createComment(
                input: {
                    content: "Reply %d",
                    reviewId: %d,
                    parentId: %d
                }
            ) {
                id
                content
                path
                depth
            }
        }
        """ % (i + 1, test_review["id"], parent_comment["id"])
        
        reply_response = client.post(
            "/graphql",
            headers=auth_headers,
            json={"query": reply_mutation}
        )
        reply_result = reply_response.json()
        assert "data" in reply_result
        replies.append(reply_result["data"]["createComment"])
    
    return {
        "parent": parent_comment,
        "replies": replies
    }

# -------- S3 Fixtures --------

@pytest.fixture
def test_image():
    """Create a valid test image"""
    # Create a small 100x100 red image
    img = Image.new('RGB', (100, 100), color='red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_byte_arr.seek(0)
    
    return UploadFile(
        filename='test.jpg',
        file=img_byte_arr
    )

# In conftest.py
@pytest.fixture
def test_user(db):
    """Create a test user with unique email"""
    from book_api.models import User
    import uuid
    
    # Generate unique email
    unique_id = str(uuid.uuid4())[:8]
    user = User(
        username=f"testuser_{unique_id}",
        email=f"test_{unique_id}@example.com",
        hashed_password="testpass",
        role="user"
    )
    db.add(user)
    db.commit()
    return user


# Change in conftest.py
@pytest.fixture
def wrong_format():
    """Create a PNG file when only JPG is allowed"""
    img = Image.new('RGB', (100, 100), color='yellow')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    file = UploadFile(
        filename='wrong_format.png',
        file=img_byte_arr,
    )
    return file

@pytest.fixture
def large_image():
    """Create an image that exceeds size limits (5MB)"""
    # Calculate how many pixels we need to guarantee over 5MB
    # Using RGB (3 bytes per pixel) with minimal compression
    target_size = 6 * 1024 * 1024  # Aim for 6MB to ensure we exceed 5MB
    bytes_per_pixel = 3  # RGB format
    
    # Create a pattern that's hard to compress
    width = height = int(np.sqrt((target_size / bytes_per_pixel)))
    img = Image.new('RGB', (width, width))
    pixels = []
    
    # Generate random pixel data to prevent efficient compression
    for i in range(width * height):
        pixels.extend([
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255)
        ])
    
    img.putdata(list(zip(*[iter(pixels)]*3)))
    
    # Convert to bytes
    img_byte_arr = io.BytesIO()
    # Use PNG format instead of JPEG to avoid unwanted compression
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    # Log the actual size to verify
    size_mb = len(img_byte_arr.getvalue()) / (1024 * 1024)
    print(f"Generated image size: {size_mb:.2f} MB")
    
    return UploadFile(
        filename='large.png',
        file=img_byte_arr
    )

@pytest.fixture
def fake_image():
    """Create a text file pretending to be an image"""
    content = b"This is not an image but pretends to be one"
    
    return UploadFile(
        filename='fake.jpg',
        file=io.BytesIO(content)
    )

@pytest.fixture
def corrupt_image():
    """Create a corrupted JPEG file"""
    # JPEG header bytes
    jpeg_header = bytes([
        0xFF, 0xD8,                # SOI marker
        0xFF, 0xE0,                # APP0 marker
        0x00, 0x10,                # Length of APP0 segment
        0x4A, 0x46, 0x49, 0x46, 0x00  # "JFIF\0"
    ])
    
    # Add corrupted data
    corrupted_data = jpeg_header + b'This is not valid JPEG content'
    
    return UploadFile(
        filename='corrupt.jpg',
        file=io.BytesIO(corrupted_data)
    )

@pytest.fixture
def oversized_image_dimensions():
    """Create an image with dimensions too large"""
    # Create image with dimensions larger than allowed
    img = Image.new('RGB', (2000, 2000), color='green')  # Too big for profile pic
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_byte_arr.seek(0)
    
    return UploadFile(
        filename='too_big_dimensions.jpg',
        file=img_byte_arr
    )

@pytest.fixture
def wrong_format():
    """Create a PNG file when only JPG is allowed"""
    img = Image.new('RGB', (100, 100), color='yellow')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return UploadFile(
        filename='wrong_format.png',
        file=img_byte_arr
    )

@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto"""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@pytest.fixture(scope="function")
def mock_s3_bucket(aws_credentials):
    """Mock S3 client and create test bucket"""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=config.AWS_BUCKET_NAME)
        yield s3

@pytest.fixture
def file_service(db:TestingSessionLocal, mock_s3_bucket):
    """Create FileService instance with mocked S3"""
    return FileService(db)

@pytest.fixture
def mock_s3(monkeypatch):
    """Mock S3 operations for testing"""
    class MockS3Client:
        class Exceptions:
            class ClientError(Exception):
                pass
            
        exceptions = Exceptions()
        
        def head_bucket(self, Bucket):
            return True
            
        def put_object(self, Bucket, Key, Body, ContentType):
            return {"ETag": "mock-etag"}
            
        def get_object(self, Bucket, Key):
            return {
                "Body": io.BytesIO(b"mock-image-data"),
                "ContentType": "image/jpeg"
            }
            
        def delete_object(self, Bucket, Key):
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    monkeypatch.setattr("boto3.client", lambda service, **kwargs: MockS3Client())