from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Float, UniqueConstraint, Index, Boolean, Table
from sqlalchemy.orm import declarative_base, relationship
from enum import Enum
from datetime import datetime

Base = declarative_base()

# association tables for many-to-many relationships
book_shelf = Table(
    'book_shelf',
    Base.metadata,
    Column('book_id', Integer, ForeignKey('books.id', ondelete='CASCADE')),
    Column('shelf_id', Integer, ForeignKey('shelves.id', ondelete='CASCADE')),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE')),
    Column('reading_status', String(20), nullable=False),
    Column('current_page', Integer, nullable=True),
    Column('started_at', DateTime, nullable=True),
    Column('finished_at', DateTime, nullable=True),
    UniqueConstraint('book_id', 'shelf_id', 'user_id', name='unique_book_shelf_user')
)

# table for followers
followers_assoc = Table(
    'followers',
    Base.metadata,
    Column('follower_id', Integer, ForeignKey('users.id', ondelete='CASCADE')),
    Column('followed_id', Integer, ForeignKey('users.id', ondelete='CASCADE')),
    Column('created_at', DateTime, nullable=False, default=datetime.utcnow()),
    UniqueConstraint('follower_id', 'followed_id', name='unique_follower_followed')
)

# table for review likes
review_likes = Table(
    'review_likes',
    Base.metadata,
    Column('review_id', Integer, ForeignKey('reviews.id', ondelete='CASCADE')),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE')),
    Column('created_at', DateTime, nullable=False, default=datetime.utcnow()),
    UniqueConstraint('review_id', 'user_id', name='unique_review_like')
)

# table for comment likes
comment_likes = Table(
    'comment_likes',
    Base.metadata,
    Column('comment_id', Integer, ForeignKey('comments.id', ondelete='CASCADE')),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE')),
    Column('created_at', DateTime, nullable=False, default=datetime.utcnow),
    UniqueConstraint('comment_id', 'user_id', name='unique_comment_like')
)


class User(Base):

    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)  # Added unique constraint and length
    email = Column(String(100), unique=True, nullable=False)    # Added unique constraint and length
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default='user')
    bio = Column(Text, nullable=True)                          # Changed to Text type
    profile_picture = Column(String(255), nullable=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow())
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow(), onupdate=datetime.utcnow())
    followers_count = Column(Integer, nullable=False, default=0)
    following_count = Column(Integer, nullable=False, default=0)

    # helper methods
    def is_following(self, user):
        return self.followers.filter(followers_assoc.c.followed_id == user.id).count() > 0
    
    def follow(self, user):
        if not self.is_following(user):
            self.followers.append(user)
            user.followers_count += 1
            self.following_count += 1
            return True
        return False

    def unfollow(self, user):
        if self.is_following(user):
            self.followers.remove(user)
            user.followers_count -= 1
            self.following_count -= 1
            return True
        return False
    
    def get_followers(self, skip:int=0, limit:int=10):
        return self.followers.offset(skip).limit(limit).all()
    
    def get_following(self, skip:int=0, limit:int=10):
        return self.followed_by.offset(skip).limit(limit).all()

    # Relationships
    reviews = relationship('Review', back_populates='user', cascade='all, delete-orphan')
    books = relationship('Book', back_populates='user', cascade='all, delete-orphan')
    shelves = relationship('Shelf', back_populates='user', cascade='all, delete-orphan')
    comments = relationship('Comment', back_populates='user', cascade='all, delete-orphan')
    comment_likes = relationship(
        'Comment',
        secondary=comment_likes,
        back_populates='liked_by',
        lazy='dynamic',
        overlaps="liked_by,likes"
    )
    review_likes = relationship(
        'Review',
        secondary=review_likes,
        back_populates='liked_by',
        lazy='dynamic',
        overlaps="liked_by,likes"
    )
    followers = relationship(
        'User',
        secondary=followers_assoc,
        primaryjoin=(followers_assoc.c.follower_id == id),
        secondaryjoin=(followers_assoc.c.followed_id == id),
        backref='followed_by',
        lazy='dynamic'
    )

    def __repr__(self):
        return f'<User(username={self.username}, email={self.email})>'

class Book(Base):

    __tablename__ = 'books'

    __table_args__ = (
        Index('idx_book_author', 'author'),
        Index('idx_book_title', 'title'),
        Index('idx_book_year', 'year')
    )

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    author = Column(String(100), nullable=False)
    publisher = Column(String(100), nullable=True)
    year = Column(Integer, nullable=True)
    genre = Column(String(50), nullable=False)
    page_count = Column(Integer, nullable=False)
    average_rating = Column(Float, nullable=True, default=0.0)  # Added to track average rating
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow())
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow(), onupdate=datetime.utcnow())
    cover_url = Column(String(255), nullable=True)

    # Foreign Keys
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Relationships
    reviews = relationship('Review', back_populates='book', cascade='all, delete-orphan')
    user = relationship('User', back_populates='books')
    shelves = relationship(
        'Shelf',
        secondary=book_shelf,
        back_populates='books'
    )

    def __repr__(self):
        return f'<Book(title={self.title}, author={self.author})>'

class Review(Base):

    __tablename__ = 'reviews'

    id = Column(Integer, primary_key=True)
    rating = Column(Integer, nullable=False)
    content = Column(Text, nullable=True)
    likes_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow())
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow(), onupdate=datetime.utcnow())

    # Foreign Keys
    book_id = Column(Integer, ForeignKey('books.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Relationships
    book = relationship('Book', back_populates='reviews')
    user = relationship('User', back_populates='reviews')
    comments = relationship('Comment', back_populates='review', cascade='all, delete-orphan')
    liked_by = relationship(
        'User',
        secondary=review_likes,
        back_populates='review_likes',
        lazy='dynamic',
        overlaps="review_likes,likes"
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'book_id', name='unique_user_book_review'),
    )

    def __repr__(self):
        return f'<Review(rating={self.rating}, user_id={self.user_id}, book_id={self.book_id})>'
    

class Shelf(Base):

    __tablename__ = 'shelves'
    __table_args__ = (
        Index('idx_shelf_user', 'user_id'),
        Index('idx_shelf_name', 'name'),
    )

    # columns
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, nullable=False)
    is_default = Column(Boolean, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow())
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow(), onupdate=datetime.utcnow())
    book_count = Column(Integer, nullable=False, default=0)
    
    def update_book_count(self):
        """Update the book count"""
        self.book_count = len(self.books)

    # relationships
    user = relationship('User', back_populates='shelves')
    books = relationship(
        'Book',
        secondary=book_shelf,
        back_populates='shelves'
    )

# table for comments
class Comment(Base):

    __tablename__ = 'comments'
    __table_args__ = (
        Index('idx_comment_user', 'user_id'),
        Index('idx_comment_review', 'review_id'),
        Index('idx_comment_parent', 'parent_id'),
        Index('idx_comment_path', 'path')
    )

    # main columns
    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    path = Column(String(255), nullable=False)
    depth = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow())
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow(), onupdate=datetime.utcnow())
    likes_count = Column(Integer, nullable=False, default=0)
    is_deleted = Column(Boolean, nullable=False, default=False)

    # Foreign Keys
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    review_id = Column(Integer, ForeignKey('reviews.id'), nullable=True)
    parent_id = Column(Integer, ForeignKey('comments.id', ondelete='CASCADE'), nullable=True)

    # Relationships
    user = relationship('User', back_populates='comments')
    review = relationship('Review', back_populates='comments')
    parent = relationship('Comment', remote_side=[id], backref='children')
    liked_by = relationship(
        'User',
        secondary=comment_likes,
        back_populates='comment_likes',
        lazy='dynamic',
        overlaps="comment_likes,likes"
    )