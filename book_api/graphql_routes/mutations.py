import strawberry
from strawberry.types import Info
from typing import Optional
from sqlalchemy import desc
from book_api.graphql_routes.types import Comment, CommentInput, CommentUpdate
from book_api.models import (
    Comment as CommentModel,
    Review as ReviewModel
)
from fastapi import HTTPException


# mutation class
@strawberry.type
class Mutation:

    # mutation to create a new comment
    @strawberry.mutation
    async def create_comment(
        self,
        info: Info,
        input: CommentInput
    ) -> Comment:
        
        # Get context attributes
        context = info.context
        db = context["db"]  # Access db from context dict
        user = context["user"]  # Access user from context dict
        
        # check if the review exists
        review = db.query(ReviewModel).filter(
            ReviewModel.id == input.review_id
        ).first()
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        # calculate the path and depth
        if input.parent_id:
            parent = db.query(CommentModel).filter(
                CommentModel.id == input.parent_id
            ).first()
            if not parent:
                raise HTTPException(status_code=404, detail="Parent comment not found")
            if parent.depth >= 5:
                raise HTTPException(status_code=400, detail="Maximum depth reached")
            path = f"{parent.path}.{parent.id}"
            depth = parent.depth + 1
        else:
            path = "root"
            depth = 0

        # create the comment
        new_comment = CommentModel(
            content=input.content,
            review_id=input.review_id,
            user_id=user.id,
            parent_id=input.parent_id,
            path=path,
            depth=depth
        )

        db.add(new_comment)
        db.commit()
        db.refresh(new_comment)

        return new_comment

    # mutation to update a comment
    @strawberry.mutation
    async def update_comment(
        self,
        info: Info,
        comment_id: int,
        input: CommentUpdate
    ) -> Comment:
        
        # Get context attributes
        context = info.context
        db = context["db"]  # Access db from context dict
        user = context["user"]  # Access user from context dict
        
        # check if the comment exists
        comment = db.query(CommentModel).filter(
            CommentModel.id == comment_id,
            CommentModel.is_deleted == False
        ).first()

        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")
        
        # check if the user is the owner of the comment
        if comment.user_id != user.id:
            raise HTTPException(status_code=403, detail="You do not have permission to update this comment")
        
        # update the comment
        comment.content = input.content

        db.commit()
        db.refresh(comment)

        return comment

    # mutation to delete a comment
    @strawberry.mutation
    async def delete_comment(
        self,
        info: Info,
        comment_id: int
    ) -> Comment:
        
         # Get context attributes
        context = info.context
        db = context["db"]  # Access db from context dict
        user = context["user"]  # Access user from context dict
        
        # check if the comment exists
        comment = db.query(CommentModel).filter(
            CommentModel.id == comment_id,
            CommentModel.is_deleted == False
        ).first()

        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")
        
        # check if the user is the owner of the comment
        if comment.user_id != user.id and user.role != "admin":
            raise HTTPException(status_code=403, detail="You do not have permission to delete this comment")
        
        # delete the comment
        comment.is_deleted = True

        db.commit()
        db.refresh(comment)

        return comment

    # mutation to like a comment
    @strawberry.mutation
    async def like_comment(
        self,
        info: Info,
        comment_id: int
    ) -> Comment:
        
         # Get context attributes
        context = info.context
        db = context["db"]  # Access db from context dict
        user = context["user"]  # Access user from context dict

        # check if the comment exists
        comment = db.query(CommentModel).filter(
            CommentModel.id == comment_id,
            CommentModel.is_deleted == False
        ).first()

        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")
        
        # check if the user has already liked the comment
        if user in comment.liked_by:
            raise HTTPException(status_code=400, detail="You have already liked this comment")
        
        # like the comment
        comment.liked_by.append(user)
        comment.likes_count += 1

        db.commit()
        db.refresh(comment)

        return comment

    # mutation to unlike a comment
    @strawberry.mutation
    async def unlike_comment(
        self,
        info: Info,
        comment_id: int
    ) -> Comment:
        
         # Get context attributes
        context = info.context
        db = context["db"]  # Access db from context dict
        user = context["user"]  # Access user from context dict

        # check if the comment exists
        comment = db.query(CommentModel).filter(
            CommentModel.id == comment_id,
            CommentModel.is_deleted == False
        ).first()

        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")
        
        # check if the user has already liked the comment
        if user not in comment.liked_by:
            raise HTTPException(status_code=400, detail="You have not liked this comment")
        
        # unlike the comment
        comment.liked_by.remove(user)
        comment.likes_count -= 1

        db.commit()
        db.refresh(comment)

        return comment