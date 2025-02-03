from fastapi import APIRouter, Depends, Request, HTTPException, Query, Body
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
from book_api import models, schemas
from book_api.core.rate_limiter import limiter
from book_api.core.event_bus import event_bus, Event
from book_api.database import get_db
from book_api.auth import (
    get_current_active_user
)

router = APIRouter(
    prefix='/shelves',
    tags=['shelves'],
    responses={
        404: {"description": "Not found"}
    }
)

def get_shelf_or_404(db: Session, shelf_id: int, user_id: int) -> models.Shelf:
    """Helper function to get shelf with proper error handling"""
    if shelf_id <= 0:
        raise HTTPException(status_code=404, detail="Shelf not found")
        
    shelf = (
        db.query(models.Shelf)
        .filter(models.Shelf.id == shelf_id)
        .filter(models.Shelf.user_id == user_id)
        .first()
    )
    
    if not shelf:
        raise HTTPException(status_code=404, detail="Shelf not found")
    
    return shelf

# create a shelf
@router.post('/', response_model=schemas.ShelfResponse)
@limiter.limit('100/minute')
async def create_shelf(
    request: Request,
    shelf: schemas.ShelfCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> models.Shelf:
    # Check if shelf name already exists for this user
    existing_shelf = (
        db.query(models.Shelf)
        .filter(models.Shelf.user_id == current_user.id)
        .filter(models.Shelf.name == shelf.name)
        .first()
    )
    
    if existing_shelf:
        raise HTTPException(
            status_code=400,
            detail="A shelf with this name already exists"
        )

    new_shelf = models.Shelf(
        **shelf.dict(),
        user_id=current_user.id,
        is_default=False  # Explicitly set is_default
    )
    db.add(new_shelf)
    db.commit()
    db.refresh(new_shelf)
    return new_shelf

# get a user's shelves
@router.get('/', response_model=schemas.PaginatedShelfResponse)
@limiter.limit('100/minute')
async def get_shelves(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    name: Optional[str] = None,
    is_public: Optional[bool] = None,
    page: int = Query(1, gt=0)  # Ensure page is greater than 0
) -> schemas.PaginatedShelfResponse:
    # Build query
    query = db.query(models.Shelf).filter(models.Shelf.user_id == current_user.id)
    
    # Apply filters
    if name:
        query = query.filter(models.Shelf.name.ilike(f"%{name}%"))
    if is_public is not None:  # Changed to allow False values
        query = query.filter(models.Shelf.is_public == is_public)
    
    # Get total count before pagination
    total = query.count()
    
    # Apply pagination
    shelves = query.offset((page - 1)*10).limit(10).all()
    
    # Add book count to each shelf
    for shelf in shelves:
        shelf.book_count = len(shelf.books)
    
    return schemas.PaginatedShelfResponse(
        total=total,
        page=page,
        items=shelves
    )

# get a shelf by its id
@router.get('/{shelf_id}', response_model=schemas.ShelfResponse)
@limiter.limit('100/minute')
async def get_shelf(
    request: Request,
    shelf_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> models.Shelf:
    return get_shelf_or_404(db, shelf_id, current_user.id)

# update a shelf
@router.put('/{shelf_id}', response_model=schemas.ShelfResponse)
@limiter.limit('100/minute')
async def update_shelf(
    request: Request,
    shelf_id: int,
    shelf_update: schemas.ShelfUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> models.Shelf:
    # Get the shelf
    shelf = get_shelf_or_404(db, shelf_id, current_user.id)
    
    # Prevent modification of default shelves
    if shelf.is_default:
        raise HTTPException(
            status_code=400,
            detail="Cannot modify default shelves"
        )
    
    # If name is being updated, check for uniqueness
    if shelf_update.name:
        existing_shelf = (
            db.query(models.Shelf)
            .filter(models.Shelf.user_id == current_user.id)
            .filter(models.Shelf.name == shelf_update.name)
            .filter(models.Shelf.id != shelf_id)
            .first()
        )
        if existing_shelf:
            raise HTTPException(
                status_code=400,
                detail="A shelf with this name already exists"
            )
    
    # Update the shelf with provided values
    for key, value in shelf_update.dict(exclude_unset=True).items():
        setattr(shelf, key, value)
    
    db.commit()
    db.refresh(shelf)
    
    return shelf

# delete a shelf
@router.delete('/{shelf_id}')
@limiter.limit('100/minute')
async def delete_shelf(
    request: Request,
    shelf_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> dict:
    # Get the shelf
    shelf = get_shelf_or_404(db, shelf_id, current_user.id)
    
    # Prevent deletion of default shelves
    if shelf.is_default:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete default shelves"
        )
    
    # Remove all book associations
    shelf.books.clear()
    
    # Delete the shelf
    db.delete(shelf)
    db.commit()
    
    return {"message": "Shelf deleted successfully"}


# add a book to a shelf
@router.post('/{shelf_id}/books', response_model=schemas.ShelfBookResponse)
@limiter.limit('100/minute')
async def add_book_to_shelf(
    shelf_id: int,
    book_data: schemas.AddBookToShelf,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> schemas.ShelfBookResponse:
    
    # Get the shelf
    shelf = get_shelf_or_404(db, shelf_id, current_user.id)
    
    # Get the book
    book = db.query(models.Book).filter(models.Book.id == book_data.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Check if the book is already in the shelf
    existing = db.query(models.book_shelf).filter_by(
        book_id=book.id,
        shelf_id=shelf.id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Book already exists in this shelf"
        )

    # Create the association with all required fields
    db.execute(
        models.book_shelf.insert().values(
            book_id=book.id,
            shelf_id=shelf.id,
            user_id=current_user.id,
            reading_status=book_data.reading_status,
            current_page=book_data.current_page if book_data.current_page else 0,
            started_at=datetime.utcnow() if book_data.reading_status == "CURRENTLY_READING" else None
        )
    )
    
    db.commit()

    return {
        "book": book,
        "status": {
            "reading_status": book_data.reading_status,
            "current_page": book_data.current_page if book_data.current_page else 0,
            "started_at": datetime.utcnow() if book_data.reading_status == "CURRENTLY_READING" else None,
            "finished_at": None
        }
    }


# bulk move books from one shelf to another
@router.put('/{shelf_id}/books/batch/move')
@limiter.limit('30/minute')
async def batch_move_books(
    request: Request,
    shelf_id: int,
    target_shelf_id: int = Query(..., description="ID of the shelf to move the books to"),
    book_data: schemas.BatchMoveBooks= Body(...),  
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> dict:
    """
    Move multiple books from one shelf to another in a single operation.
    """
    try:
        # Start a nested transaction
        with db.begin_nested():
            # Validate source and target shelves exist and belong to user
            source_shelf = get_shelf_or_404(db, shelf_id, current_user.id)
            target_shelf = get_shelf_or_404(db, target_shelf_id, current_user.id)
            
            if source_shelf.id == target_shelf.id:
                raise HTTPException(
                    status_code=400,
                    detail="Source and target shelves cannot be the same"
                )

            # Get all book associations for these books in source shelf
            book_assocs = db.query(models.book_shelf).filter(
                models.book_shelf.c.book_id.in_(book_data.book_ids),
                models.book_shelf.c.shelf_id == source_shelf.id,
                models.book_shelf.c.user_id == current_user.id
            ).all()

            # Verify all books exist in source shelf
            found_book_ids = {assoc.book_id for assoc in book_assocs}
            missing_book_ids = set(book_data.book_ids) - found_book_ids
            
            if missing_book_ids:
                raise HTTPException(
                    status_code=404,
                    detail=f"Books with IDs {missing_book_ids} not found in source shelf"
                )

            # Check for existing books in target shelf
            existing_books = db.query(models.book_shelf).filter(
                models.book_shelf.c.book_id.in_(book_data.book_ids),
                models.book_shelf.c.shelf_id == target_shelf.id,
                models.book_shelf.c.user_id == current_user.id
            ).all()

            if existing_books:
                existing_ids = {book.book_id for book in existing_books}
                raise HTTPException(
                    status_code=400,
                    detail=f"Books with IDs {existing_ids} already exist in target shelf"
                )

            # Move all books in one operation
            move_count = db.execute(
                models.book_shelf.update()
                .where(models.book_shelf.c.book_id.in_(book_data.book_ids))
                .where(models.book_shelf.c.shelf_id == source_shelf.id)
                .where(models.book_shelf.c.user_id == current_user.id)
                .values(shelf_id=target_shelf.id)
            ).rowcount

            # Update book counts
            source_shelf.book_count = len(source_shelf.books) - move_count
            target_shelf.book_count = len(target_shelf.books) + move_count
            
            db.commit()

            return {
                "message": f"Successfully moved {move_count} books to target shelf",
                "moved_book_ids": book_data.book_ids
            }

    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to move books: {str(e)}"
        )
        
# move a book between shelves
@router.put('/{shelf_id}/books/{book_id}/move')
@limiter.limit('100/minute')
async def move_book(
    request: Request,
    shelf_id: int,
    book_id: int,
    target_shelf_id: int = Query(..., description="ID of the shelf to move the book to"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> dict:
    try:
        with db.begin_nested() as transaction:
            # Validate shelves exist
            source_shelf = get_shelf_or_404(db, shelf_id, current_user.id)
            target_shelf = get_shelf_or_404(db, target_shelf_id, current_user.id)
            
            # Check book exists in source shelf
            book_assoc = db.query(models.book_shelf).filter(
                models.book_shelf.c.book_id == book_id,
                models.book_shelf.c.shelf_id == shelf_id
            ).first()
            
            if not book_assoc:
                raise HTTPException(status_code=404, detail="Book not found in source shelf")
                
            # Check book doesn't exist in target shelf
            existing = db.query(models.book_shelf).filter(
                models.book_shelf.c.book_id == book_id,
                models.book_shelf.c.shelf_id == target_shelf_id
            ).first()
            
            if existing:
                raise HTTPException(status_code=400, detail="Book already exists in target shelf")
                
            # Move the book
            db.execute(
                models.book_shelf.update()
                .where(models.book_shelf.c.book_id == book_id)
                .where(models.book_shelf.c.shelf_id == shelf_id)
                .values(shelf_id=target_shelf_id)
            )
            
        return {"message": "Book moved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# get all books on a certain shelf
@router.get('/{shelf_id}/books', response_model=List[schemas.ShelfBookResponse])
async def get_shelf_books(
    request: Request,
    shelf_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    reading_status: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    page: int = Query(1, gt=0)
) -> List[models.Book]:
    
    shelf = get_shelf_or_404(db, shelf_id, current_user.id)
    
    query = (
        db.query(
            models.Book,
            models.book_shelf.c.reading_status,
            models.book_shelf.c.current_page,
            models.book_shelf.c.started_at,
            models.book_shelf.c.finished_at
        )
        .join(models.book_shelf, models.Book.id == models.book_shelf.c.book_id)
        .filter(models.book_shelf.c.shelf_id == shelf_id)
    )
    
    # Apply filters
    if reading_status:
        query = query.filter(models.book_shelf.c.reading_status == reading_status)
        
    # Apply sorting
    if sort_by == "title":
        query = query.order_by(models.Book.title)
    elif sort_by == "date_added":
        query = query.order_by(models.book_shelf.c.created_at.desc())
    elif sort_by == "progress":
        query = query.order_by(models.book_shelf.c.current_page.desc())
        
    # Paginate results
    results = query.offset((page - 1) * 10).limit(10).all()
    
    return [
        {
            "book": result[0],
            "status": {
                "reading_status": result[1],
                "current_page": result[2],
                "started_at": result[3],
                "finished_at": result[4]
            }
        }
        for result in results
    ]