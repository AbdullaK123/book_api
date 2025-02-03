# books.py
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from book_api.core.rate_limiter import limiter
from book_api.core.event_bus import event_bus, Event
from book_api import models, schemas
from book_api.database import get_db
from book_api.auth import (
    get_current_active_user
)

router = APIRouter(
    prefix="/books",
    tags=["books"],
    responses={404: {"description": "Not found"}}
)

@router.get("/", response_model=schemas.PaginatedBookResponse)
@limiter.limit("30/minute")
async def get_books(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    from_year: Optional[int] = Query(None, description="Filter books published from this year"),
    to_year: Optional[int] = Query(None, description="Filter books published up to this year"),
    min_avg_rating: Optional[float] = Query(None, description="Filter books with average rating greater than or equal to this value"),
    max_avg_rating: Optional[float] = Query(None, description="Filter books with average rating less than or equal to this value"),
    author_query: Optional[str] = Query(None, description="Filter books by author name"),
    title_query: Optional[str] = Query(None, description="Filter books by title"),
    genre: Optional[str] = Query(None, description="Filter books by genre"),
    order_by: Optional[str] = Query(None, description="Order books by a specific column"),
    page: int = Query(1, description="Page number")
) -> schemas.PaginatedBookResponse:
    """Get all books for the current user"""
    books = db.query(models.Book).filter(models.Book.user_id == current_user.id)

    if from_year:
        books = books.filter(models.Book.year >= from_year)
    if to_year:
        books = books.filter(models.Book.year <= to_year)
    if min_avg_rating:
        books = books.filter(models.Book.avg_rating >= min_avg_rating)
    if max_avg_rating:
        books = books.filter(models.Book.avg_rating <= max_avg_rating)
    if author_query:
        books = books.filter(models.Book.author.ilike(f"%{author_query}%"))
    if title_query:
        books = books.filter(models.Book.title.ilike(f"%{title_query}%"))
    if genre:
        books = books.filter(models.Book.genre == genre)

    if order_by == "avg_rating":
        books = books.order_by(models.Book.avg_rating.desc())
    elif order_by == "year":
        books = books.order_by(models.Book.year.desc())
    else:
        books = books.order_by(models.Book.id.desc())

    total = books.count()
    books = books.offset((page - 1) * 10).limit(10).all()

    return schemas.PaginatedBookResponse(
        total=total,
        page=page,
        items=books
    )

@router.get("/{book_id}", response_model=schemas.BookResponse)
@limiter.limit("30/minute")
async def get_book(
    request: Request,
    book_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> models.Book:
    """Get a specific book by ID"""
    book = db.query(models.Book).filter(
        models.Book.id == book_id,
        models.Book.user_id == current_user.id
    ).first()
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

@router.post("/", response_model=schemas.BookResponse)
@limiter.limit("100/minute")
async def create_book(
    request: Request,
    book: schemas.BookCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> models.Book:
    """Create a new book"""
    new_book = models.Book(
        **book.dict(),
        user_id=current_user.id
    )
    db.add(new_book)
    db.commit()
    db.refresh(new_book)

    return new_book

# route to bulk create books
@router.post("/bulk", response_model=List[schemas.BookResponse])
@limiter.limit("30/minute")
async def bulk_create_books(
    request: Request,
    books: List[schemas.BookCreate],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> List[models.Book]:
    """Bulk create books"""
    try: 
        new_books = []
        for book in books:
            new_book = models.Book(
                **book.dict(),
                user_id=current_user.id
            )
            db.add(new_book)
            new_books.append(new_book)

        db.commit()

        return new_books
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# route to update a book
@router.put("/{book_id}", response_model=schemas.BookResponse)
@limiter.limit("30/minute")
async def update_book(
    request: Request,
    book_id: int,
    book_update: schemas.BookUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> models.Book:
    """Update a book"""
    db_book = db.query(models.Book).filter(
        models.Book.id == book_id,
        models.Book.user_id == current_user.id
    ).first()
    
    if not db_book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    for key, value in book_update.dict(exclude_unset=True).items():
        setattr(db_book, key, value)
    
    db.commit()
    db.refresh(db_book)

    # Clear the cache for the current user
    event = Event(name="data_updated", data={"user_id": current_user.id})
    await event_bus.publish(event)

    return db_book

# route to delete a book
@router.delete("/{book_id}")
@limiter.limit("30/minute")
async def delete_book(
    request: Request,
    book_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> dict:
    """Delete a book"""
    db_book = db.query(models.Book).filter(
        models.Book.id == book_id,
        models.Book.user_id == current_user.id
    ).first()
    
    if not db_book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    db.delete(db_book)
    db.commit()

    return {"message": "Book deleted successfully"}