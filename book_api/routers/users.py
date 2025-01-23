from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
import datetime
from book_api.core.rate_limiter import limiter
from book_api.core.event_bus import event_bus, Event
from book_api import models, schemas
from book_api.database import get_db
from book_api.auth import (
    get_password_hash,
    get_user,
    get_current_active_user,
    authenticate_user,
    get_access_token,
    check_role
)

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}}
)

# Create a user
@router.post("/", response_model=schemas.UserResponse)
@limiter.limit("100/minute")
async def create_user(
    request: Request,
    user: schemas.UserCreate,
    db: Session = Depends(get_db)
) -> models.User:
    db_user = get_user(db, user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    hashed_password = get_password_hash(user.password)
    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        role=user.role if user.role else 'user'
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Publish user created event
    event = Event(name='user_created', data={'user_id': new_user.id})
    await event_bus.publish(event)

    return new_user

# Get all users (admin only)
@router.get("/", response_model=List[schemas.UserResponse], dependencies=[Depends(check_role(['admin']))])
@limiter.limit("100/minute")
async def get_users(request: Request, db: Session = Depends(get_db)) -> List[models.User]:
    users = db.query(models.User).all()
    return users

# Login endpoints can be here too since they're user-related
@router.post("/login", response_model=schemas.Token)
@limiter.limit("100/minute")
async def login_user(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> dict:
    db_user = authenticate_user(db, form_data.username, form_data.password)
    if not db_user:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    db_user.last_login = datetime.datetime.utcnow()
    db.commit()
    db.refresh(db_user)
    
    access_token = get_access_token(data={'sub': db_user.username, 'role': db_user.role}, request=request)
    return {"access_token": access_token, "token_type": "bearer"}


# Get current user profile
@router.get("/me", response_model=schemas.UserResponse)
@limiter.limit("100/minute")
async def get_current_user_profile(
    request: Request,
    current_user: models.User = Depends(get_current_active_user)
) -> models.User:
    return current_user

# Update user profile (example of a new endpoint we could add)
@router.put("/me", response_model=schemas.UserResponse)
@limiter.limit("100/minute")
async def update_user_profile(
    request: Request,
    user_update: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> models.User:
    for key, value in user_update.dict(exclude_unset=True).items():
        setattr(current_user, key, value)
    db.commit()
    db.refresh(current_user)
    return current_user


# Follow a user
@router.post('/{user_id}/follow')
@limiter.limit("100/minute")
async def follow_user(
    request: Request,
    user_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> dict:
    try:
        with db.begin_nested():
            # check if the user exists
            user_to_follow = db.query(models.User).filter(models.User.id == user_id).first()
            if not user_to_follow:
                raise HTTPException(status_code=404, detail="User not found")
            
            # do not allow the user to follow themselves
            if current_user.id == user_id:
                raise HTTPException(
                    status_code=400,
                    detail="You cannot follow yourself"
                )

            # check if the current user is not already following that user
            if user_to_follow in current_user.followers:
                raise HTTPException(status_code=400, detail="Already following this user")

            # add a new row to the followers association table
            current_user.followers.append(user_to_follow)
            
            # update the current user's follows count and the user's followed_by count
            current_user.following_count += 1
            user_to_follow.followers_count += 1
            
            # commit the changes to the database
            db.commit()
            return {"message": f"Successfully followed user {user_id}"}
    except Exception as e:
        if e.status_code in [400, 404]:
            raise e
        raise HTTPException(
            status_code=500,
            detail=f"Could not follow user: {e}"
        )


# Unfollow a user
@router.delete('/{user_id}/unfollow')
@limiter.limit("100/minute")
async def unfollow_user(
    request: Request,
    user_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> dict:
    try:
        with db.begin_nested():
             # check if the user exists
            user_to_unfollow = db.query(models.User).filter(models.User.id == user_id).first()
            if not user_to_unfollow:
                raise HTTPException(status_code=404, detail="User not found")

            # if the current user is not following the user to unfollow throw an exception
            if user_to_unfollow not in current_user.followers:
                raise HTTPException(status_code=400, detail="You are not following this user")

            # add a new row to the followers association table
            current_user.followers.remove(user_to_unfollow)
            
            # update the current user's follows count and the user's followed_by count
            current_user.following_count -= 1
            user_to_unfollow.followers_count -= 1
            
            # commit the changes to the database
            db.commit()
            return {"message": f"Successfully unfollowed user {user_id}"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to unfollow user: {e}"
        )

# get a users followers
@router.get('/following', response_model=schemas.PaginatedUserResponse)
@limiter.limit('100/minute')
async def get_following(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    page: int = Query(1, gt=0, description="Page number"),
    per_page: int = Query(10, gt=0, le=100, description="Items per page")
) -> schemas.PaginatedUserResponse:
    user_following = current_user.followers[(page-1) * per_page: page * per_page]
    count = len(user_following)
    
    return schemas.PaginatedUserResponse(
        total=count,
        page=page,
        items=user_following
    )

# get who a user is following
@router.get('/followers', response_model=schemas.PaginatedUserResponse)
@limiter.limit('100/minute')
async def get_followers(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    page: int = Query(1, gt=0, description="Page number"),
    per_page: int = Query(10, gt=0, le=100, description="Items per page")
) -> schemas.PaginatedUserResponse:
    user_followers = current_user.followed_by[(page-1) * per_page: page * per_page]
    count = len(user_followers)
    
    return schemas.PaginatedUserResponse(
        total=count,
        page=page,
        items=user_followers
    )


# route for a user to like a review
@router.post('/{review_id}/like')
@limiter.limit('100/minute')
async def like_review(
    request: Request,
    review_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> dict:
    try:
        with db.begin_nested():
            # check if the review exists
            review = db.query(models.Review).filter(models.Review.id == review_id).first()
            if not review:
                raise HTTPException(status_code=404, detail="Review not found")
            
            # check if the user has already liked the review
            if current_user in review.liked_by:
                raise HTTPException(status_code=400, detail="You have already liked this review")
            
            # add the user to the review's liked_by list
            review.liked_by.append(current_user)

            # update the review's like count
            review.likes_count += 1
            
            # commit the changes to the database
            db.commit()
            return {"message": "Review liked successfully"}
    except Exception as e:
        if e.status_code in [400, 404]:
            raise e
        raise HTTPException(
            status_code=500,
            detail=f"Could not like review: {e}"
        )
    
# route for a user to unlike a review
@router.delete('/{review_id}/unlike')
@limiter.limit('100/minute')
async def unlike_review(
    request: Request,
    review_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> dict:
    try:
        with db.begin_nested():
            # check if the review exists
            review = db.query(models.Review).filter(models.Review.id == review_id).first()
            if not review:
                raise HTTPException(status_code=404, detail="Review not found")
            
            # check if the user has already liked the review
            if current_user not in review.liked_by:
                raise HTTPException(status_code=400, detail="You have not liked this review")
            
            # remove the user from the review's liked_by list
            review.liked_by.remove(current_user)

            # update the review's like count
            review.likes_count -= 1
            
            # commit the changes to the database
            db.commit()
            return {"message": "Review unliked successfully"}
    except Exception as e:
        if e.status_code in [400, 404]:
            raise e
        raise HTTPException(
            status_code=500,
            detail=f"Could not unlike review: {e}"
        )
    
# route for a user to get all of their liked reviews
@router.get('/liked_reviews', response_model=schemas.PaginatedReviewResponse)
@limiter.limit('100/minute')
async def get_liked_reviews(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    page: int = Query(1, gt=0, description="Page number"),
    per_page: int = Query(10, gt=0, le=100, description="Items per page")
) -> schemas.PaginatedReviewResponse:
    # select all reviews from the review_likes association table where the user_id is the current user's id
    liked_reviews = (
        db.query(models.Review)
        .join(models.review_likes)
        .filter(models.review_likes.c.user_id == current_user.id)
        .all()
    )

    # paginate the results
    count = len(liked_reviews)
    liked_reviews = liked_reviews[(page-1) * per_page: page * per_page]

    return schemas.PaginatedReviewResponse(
        total=count,
        page=page,
        items=liked_reviews
    )
