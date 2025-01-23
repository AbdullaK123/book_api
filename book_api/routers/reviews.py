from fastapi import APIRouter, HTTPException, Depends, Request, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from book_api import models, schemas
from book_api.database import get_db
from book_api.auth import get_current_active_user
from book_api.core.rate_limiter import limiter
from book_api.utils.book_utils import get_review_statistics
from book_api.core.event_bus import event_bus, Event

router = APIRouter(
    prefix="/reviews",
    tags=["reviews"],
    responses={404: {"description": "Not found"}}
)

@router.get("/", response_model=List[schemas.ReviewResponse])
@limiter.limit("30/minute")
async def get_reviews(
    request: Request,
    book_id: Optional[int] = Query(None, description="Filter reviews by book ID"),
    user_id: Optional[int] = Query(None, description="Filter reviews by user ID"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> List[models.Review]:
    """
    Get reviews with optional filters.
    Any authenticated user can view any reviews.
    """
    query = db.query(models.Review)
    
    if book_id:
        query = query.filter(models.Review.book_id == book_id)
    if user_id:
        query = query.filter(models.Review.user_id == user_id)
    
    return query.all()

@router.get("/book/{book_id}/stats")
@limiter.limit("30/minute")
async def get_book_review_stats(
    request: Request,
    book_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> dict:
    """Get review statistics for a specific book"""
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    return get_review_statistics(db, book_id)

@router.get("/{review_id}", response_model=schemas.ReviewResponse)
@limiter.limit("30/minute")
async def get_review(
    request: Request,
    review_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> models.Review:
    """Get a specific review by ID"""
    review = db.query(models.Review).filter(models.Review.id == review_id).first()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@router.post("/", response_model=schemas.ReviewResponse)
@limiter.limit("30/minute")
async def create_review(
    request: Request,
    review: schemas.ReviewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> models.Review:
    """Create a new review"""
    # Check if book exists
    book = db.query(models.Book).filter(models.Book.id == review.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Check if user is trying to review their own book
    if book.user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot review your own book"
        )
    
    # Check if user already reviewed this book
    existing_review = db.query(models.Review).filter(
        models.Review.book_id == review.book_id,
        models.Review.user_id == current_user.id
    ).first()
    
    if existing_review:
        raise HTTPException(
            status_code=400,
            detail="You have already reviewed this book"
        )
    
    new_review = models.Review(
        **review.dict(),
        user_id=current_user.id
    )
    db.add(new_review)
    db.commit()
    db.refresh(new_review)

    # Update book's average rating
    event = Event(name="update_book_rating", data={"book_id": review.book_id})
    await event_bus.publish(event)


    return new_review

@router.put("/{review_id}", response_model=schemas.ReviewResponse)
@limiter.limit("30/minute")
async def update_review(
    request: Request,
    review_id: int,
    review_update: schemas.ReviewUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> models.Review:
    """Update a review - users can only update their own reviews"""
    db_review = db.query(models.Review).filter(models.Review.id == review_id).first()
    
    if not db_review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    # Check if user owns the review
    if db_review.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only update your own reviews"
        )
    
    # Store book_id before update for cache clearing
    book_id = db_review.book_id
    
    for key, value in review_update.dict(exclude_unset=True).items():
        setattr(db_review, key, value)
    
    db.commit()
    db.refresh(db_review)

    # Update book's average rating
    event = Event(name="update_book_rating", data={"book_id": book_id})
    await event_bus.publish(event)

    return db_review

@router.delete("/{review_id}")
@limiter.limit("30/minute")
async def delete_review(
    request: Request,
    review_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> dict:
    """Delete a review - users can only delete their own reviews"""
    db_review = db.query(models.Review).filter(models.Review.id == review_id).first()
    
    if not db_review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    # Check if user owns the review
    if db_review.user_id != current_user.id and current_user.role != 'admin':
        raise HTTPException(
            status_code=403,
            detail="You can only delete your own reviews"
        )
    
    # Store book_id before deletion for updating rating and cache
    book_id = db_review.book_id
    
    db.delete(db_review)
    db.commit()

    # Update book's average rating
    event = Event(name="update_book_rating", data={"book_id": book_id})
    await event_bus.publish(event)

    return {"message": "Review deleted successfully"}