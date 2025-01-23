import strawberry
from typing import List, Optional
from enum import Enum
from datetime import datetime


# User types
@strawberry.type
class User:
    id: int
    username: str 

# Comment types
@strawberry.type
class Comment:
    id: int
    content: str
    path: str
    depth: int
    created_at: datetime
    updated_at: datetime
    likes_count: int
    is_deleted: bool
    
    # Relationships
    user: User
    review_id: int
    parent_id: Optional[int]
    replies: List['Comment']
    
    # Computed fields
    @strawberry.field
    def is_edited(self) -> bool:
        return self.updated_at > self.created_at
    
@strawberry.input
class CommentInput:
    content: str
    review_id: int
    parent_id: Optional[int] = None

@strawberry.input
class CommentUpdate:
    content: str

@strawberry.enum
class CommentOrderBy(Enum):
    NEWEST = "newest"
    OLDEST = "oldest"
    MOST_LIKED = "most_liked"

# Review types
@strawberry.type
class Review:
    id: int
    rating: int
    content: str
    likes_count: int
    created_at: datetime
    updated_at: datetime
    
    # Relationships
    user: User
    book_id: int
    
    # Comment relationship with filtering/sorting
    @strawberry.field
    def comments(
        self,
        order_by: Optional[CommentOrderBy] = CommentOrderBy.NEWEST,
        depth: Optional[int] = None,
        page: int = 1,
        per_page: int = 20
    ) -> List[Comment]:
        # This will be implemented in the resolver
        pass

@strawberry.input
class ReviewInput:
    book_id: int
    rating: int
    content: str

@strawberry.input
class ReviewUpdate:
    rating: Optional[int] = None
    content: Optional[str] = None
