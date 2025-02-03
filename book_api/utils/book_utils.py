# book_utils.py
from sqlalchemy import func
from sqlalchemy.orm import Session
from book_api.models import Book, Review, Shelf
from book_api import models
import logging

logger = logging.getLogger(__name__)

async def update_book_rating(db: Session, book_id: int) -> float:
    """
    Update the average rating for a book based on its reviews.
    
    Args:
        db (Session): Database session
        book_id (int): ID of the book to update
        
    Returns:
        float: The new average rating
        
    Raises:
        Exception: If database operation fails
    """
    try:
        logger.info(f"Updating average rating for book_id: {book_id}")
        avg_rating = db.query(func.avg(Review.rating))\
            .filter(Review.book_id == book_id)\
            .scalar()
        
        avg_rating = float(avg_rating) if avg_rating is not None else 0.0
        avg_rating = round(avg_rating, 2)
        
        logger.debug(f"Calculated average rating: {avg_rating}")
        
        book = db.query(Book).filter(Book.id == book_id).first()
        if book:
            book.average_rating = avg_rating
            db.commit()
            db.refresh(book)
            logger.info(f"Successfully updated rating for book_id {book_id} to {avg_rating}")
            
        return avg_rating
            
    except Exception as e:
        logger.error(f"Failed to update rating for book_id {book_id}: {str(e)}")
        db.rollback()
        raise

def get_review_statistics(db: Session, book_id: int) -> dict:
    """
    Get detailed review statistics for a book.
    
    Args:
        db (Session): Database session
        book_id (int): ID of the book to get statistics for
        
    Returns:
        dict: Dictionary containing:
            - total_reviews: Total number of reviews
            - rating_distribution: Distribution of ratings from 1-5
    """
    logger.info(f"Fetching review statistics for book_id: {book_id}")
    
    total_reviews = db.query(models.Review)\
        .filter(models.Review.book_id == book_id)\
        .count()
    
    rating_distribution = db.query(
        models.Review.rating,
        func.count(models.Review.rating).label('count')
    ).filter(
        models.Review.book_id == book_id
    ).group_by(
        models.Review.rating
    ).all()
    
    distribution = {i: 0 for i in range(1, 6)}
    for rating, count in rating_distribution:
        distribution[rating] = count
    
    logger.debug(f"Found {total_reviews} reviews with distribution: {distribution}")
    return {
        "total_reviews": total_reviews,
        "rating_distribution": distribution
    }

async def create_default_shelves(db: Session, user_id: int) -> dict:
    """
    Create default bookshelves for a new user.
    
    Args:
        db (Session): Database session
        user_id (int): ID of the user to create shelves for
        
    Returns:
        dict: Success message
        
    Raises:
        Exception: If shelf creation fails
    """
    logger.info(f"Creating default shelves for user_id: {user_id}")
    try:
        shelves = [
            Shelf(
                name="Read",
                user_id=user_id,
                is_default=True,
                is_public=True,
                description="Books you have finished reading"
            ),
            Shelf(
                name="Currently Reading",
                user_id=user_id,
                is_default=True,
                is_public=True,
                description="Books you are currently reading"
            ),
            Shelf(
                name="Want to Read",
                user_id=user_id,
                is_default=True,
                is_public=True,
                description="Books you want to read in the future"
            )
        ]

        # Add all shelves in a single operation
        db.add_all(shelves)
        db.flush()  # Ensure IDs are generated
        db.commit()
        
        logger.info(f"Successfully created default shelves for user {user_id}")
        return {"message": "Default shelves created successfully."}
        
    except Exception as e:
        logger.error(f"Error creating default shelves for user {user_id}: {str(e)}")
        db.rollback()
        raise