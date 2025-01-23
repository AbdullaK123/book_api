from fastapi import APIRouter, File, UploadFile, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from book_api.services.storage.file_service import FileService
from book_api.settings import config
from book_api.auth import get_current_active_user
from book_api.database import get_db
from book_api.core.rate_limiter import limiter
from book_api.models import User, Book
from book_api import schemas
import logging

logger = logging.getLogger(__name__)

def get_file_service(db: Session = Depends(get_db)) -> FileService:
    return FileService(db)

router = APIRouter(
    prefix="/files",
    tags=["files"],
    responses={404: {"description": "Not found"}},
)

# route to get profile picture
@router.get("/profile-picture/{user_id}")
async def get_profile_picture(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    file_service: FileService = Depends(get_file_service)
) -> StreamingResponse:
    """Get profile picture"""
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.profile_picture:
        raise HTTPException(status_code=404, detail="Profile picture not found")
    
    response = await file_service.get_file(user.profile_picture)

    return StreamingResponse(
        response["Body"],
        media_type=response["ContentType"]
    )

# route to get book cover
@router.get("/book-cover/{book_id}")
async def get_book_cover(
    request: Request,
    book_id: int,
    db: Session = Depends(get_db),
    file_service: FileService = Depends(get_file_service)
) -> StreamingResponse:
    """Get book cover"""
    book = db.query(Book).get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if not book.cover_url:
        raise HTTPException(status_code=404, detail="Cover not found")
    
    response = await file_service.get_file(book.cover_url)

    return StreamingResponse(
        response["Body"],
        media_type=response["ContentType"]
    )

@router.post("/profile-picture")
@limiter.limit("100/minute")
async def upload_profile_picture(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    file_service: FileService = Depends(get_file_service)
) -> dict:
    """Upload a profile picture"""
    try:
        logger.info(f"Uploading profile picture for user {current_user.id}")
        result = await file_service.upload_profile_picture(current_user.id, file)
        db.refresh(current_user)
        return result
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to upload profile picture: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload profile picture")

@router.post("/book-cover/{book_id}")
@limiter.limit("100/minute")
async def upload_book_cover(
    request: Request,
    book_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    file_service: FileService = Depends(get_file_service)
) -> dict:
    """Upload a book cover"""
    # Verify book ownership
    book = db.query(Book).filter(
        Book.id == book_id,
        Book.user_id == current_user.id
    ).first()
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    try:
        logger.info(f"Uploading book cover for book {book_id}")
        result = await file_service.upload_book_cover(book_id, file)
        db.refresh(book)
        return result
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to upload book cover: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload book cover")

@router.delete("/profile-picture", response_model=schemas.MessageResponse)
@limiter.limit("100/minute")
async def delete_profile_picture(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    file_service: FileService = Depends(get_file_service)
) -> dict:
    """Delete profile picture"""
    if not current_user.profile_picture:
        raise HTTPException(status_code=400, detail="No profile picture to delete")
    
    try:
        await file_service.delete_file(current_user.profile_picture)
        current_user.profile_picture = None
        db.commit()
        return {"message": "Profile picture deleted successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete profile picture: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete profile picture")

@router.delete("/book-cover/{book_id}", response_model=schemas.MessageResponse)
@limiter.limit("5/minute")
async def delete_book_cover(
    request: Request,
    book_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    file_service: FileService = Depends(get_file_service)
) -> dict:
    """Delete book cover"""
    book = db.query(Book).filter(
        Book.id == book_id,
        Book.user_id == current_user.id
    ).first()
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
        
    if not book.cover_url:
        raise HTTPException(status_code=400, detail="No cover to delete")
    
    try:
        await file_service.delete_file(book.cover_url)
        book.cover_url = None
        db.commit()
        return {"message": "Book cover deleted successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete book cover: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete book cover")

@router.put("/profile-picture")
@limiter.limit("5/minute")
async def update_profile_picture(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    file_service: FileService = Depends(get_file_service)
) -> dict:
    """Update profile picture"""
    if not current_user.profile_picture:
        raise HTTPException(status_code=400, detail="No profile picture to update")
    
    try:
        result = await file_service.replace_file(
            current_user.profile_picture,
            file,
            'profile'
        )
        current_user.profile_picture = result["url"]
        db.commit()
        db.refresh(current_user)
        return result
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update profile picture: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update profile picture")

@router.put("/book-cover/{book_id}")
@limiter.limit("5/minute")
async def update_book_cover(
    request: Request,
    book_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    file_service: FileService = Depends(get_file_service)
) -> dict:
    """Update book cover"""
    book = db.query(Book).filter(
        Book.id == book_id,
        Book.user_id == current_user.id
    ).first()
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if not book.cover_url:
        raise HTTPException(status_code=400, detail="No cover to update")
    
    try:
        result = await file_service.replace_file(
            book.cover_url,
            file,
            'cover'
        )
        book.cover_url = result["url"]
        db.commit()
        db.refresh(book)
        return result
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update book cover: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update book cover")