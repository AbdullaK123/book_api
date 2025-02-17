from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal, Dict
from datetime import datetime

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

# User Schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    role: str = Field(default="user", pattern="^(user|admin)$")
    bio: Optional[str] = None
    profile_picture: Optional[str] = None

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserUpdate(BaseModel):
    bio: Optional[str] = None
    profile_picture: Optional[str] = None
    email: Optional[EmailStr] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(UserBase):
    id: int
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    followers_count: int
    following_count: int

    class Config:
        from_attributes = True

class PaginatedUserResponse(BaseModel):
    total: int
    page: int
    items: List[UserResponse]

# Book Schemas
class BookBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    author: str = Field(..., min_length=1, max_length=100)
    publisher: Optional[str] = Field(None, max_length=100)
    year: Optional[int] = Field(None, le=datetime.now().year)
    genre: str = Field(..., min_length=1, max_length=50)
    page_count: int = Field(..., gt=0)

class BookCreate(BookBase):
    pass

class BookUpdate(BookBase):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    author: Optional[str] = Field(None, min_length=1, max_length=100)
    genre: Optional[str] = Field(None, min_length=1, max_length=50)
    page_count: Optional[int] = Field(None, gt=0)

class BookResponse(BookBase):
    id: int
    average_rating: Optional[float] = 0.0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PaginatedBookResponse(BaseModel):
    total: int
    page: int
    items: List[BookResponse]


# Review Schemas
class ReviewBase(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    content: Optional[str] = None

class ReviewCreate(ReviewBase):
    book_id: int

class ReviewUpdate(ReviewBase):
    rating: Optional[int] = Field(None, ge=1, le=5)

class ReviewResponse(ReviewBase):
    id: int
    book_id: int
    user_id: int
    likes_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PaginatedReviewResponse(BaseModel):
    total: int
    page: int
    items: List[ReviewResponse]


# Shelf schemas 
class ShelfBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100) 
    description: Optional[str] = Field(None, max_length=500) 
    is_public: bool = Field(default=True)  

class ShelfCreate(ShelfBase):
    pass

class ShelfUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_public: Optional[bool] = None

class ShelfResponse(ShelfBase):
    id: int 
    name: str 
    description: Optional[str] = None
    is_public: bool 
    is_default: bool
    book_count: int 
    created_at: datetime 
    updated_at: datetime

    class Config:
        from_attributes = True

class UserBookStatus(BaseModel):
    reading_status: Literal["WANT_TO_READ", "CURRENTLY_READING", "READ"]
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    current_page: Optional[int] = Field(None, ge=0)  
    last_progress_update: Optional[datetime] = None


class ShelfBookResponse(BaseModel):
    book: BookResponse
    status: UserBookStatus

    class Config:
        from_attributes = True

class PaginatedShelfResponse(BaseModel):
    total: int
    page: int
    items: List[ShelfResponse]

class AddBookToShelf(BaseModel):
    book_id: int
    reading_status: Literal["WANT_TO_READ", "CURRENTLY_READING", "READ"]
    current_page: Optional[int] = Field(None, ge=0)

class BatchMoveBooks(BaseModel):
    book_ids: List[int] = Field(..., min_items=1)

class BatchUpdateBookStatus(BaseModel):
    book_ids: List[int] = Field(..., min_items=1)
    reading_status: Literal["WANT_TO_READ", "CURRENTLY_READING", "READ"]

class ShelfStats(BaseModel):
    total_books: int
    books_by_status: Dict[str, int]  
    pages_read: int
    completion_rate: float  

class UpdateBookStatus(BaseModel):
    reading_status: Literal["WANT_TO_READ", "CURRENTLY_READING", "READ"]
    current_page: Optional[int] = Field(None, ge=0)

# other schemas

class MessageResponse(BaseModel):
    """Schema for simple message responses"""
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Operation completed successfully"
            }
        }