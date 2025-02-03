import strawberry
from strawberry.types import Info
from typing import List, Optional
from sqlalchemy import desc
from book_api.graphql_routes.types import Comment, Review, CommentOrderBy
from book_api.models import (
    Comment as CommentModel,
    Review as ReviewModel
)


# query class
@strawberry.type
class Query:

    # field to get a single comment by id
    @strawberry.field
    async def get_comment_by_id(self, info: Info, comment_id: int) -> Comment:
        """Get a single comment by id"""
        
        # Get context attributes
        context = info.context
        db = context["db"]  # Access db from context dict
        user = context["user"]  # Access user from context dict

        return db.query(CommentModel).filter(
            CommentModel.id == comment_id,
            CommentModel.is_deleted == False
        ).first()

    # field to get all comments for a review
    @strawberry.field
    async def get_comments_for_review(
        self,
        info: Info,
        review_id: int,
        order_by: CommentOrderBy = CommentOrderBy.NEWEST,
        depth: Optional[int] = None,
        page: int = 1,
        per_page: int = 20
    ) -> List[Comment]:
        """Get all comments for a review"""
        
        # Get context attributes
        context = info.context
        db = context["db"]  # Access db from context dict
        user = context["user"]  # Access user from context dict

        # query the comments
        query = db.query(CommentModel).filter(
            CommentModel.review_id == review_id,
            CommentModel.is_deleted == False
        )

        # apply ordering
        if order_by == CommentOrderBy.NEWEST:
            query = query.order_by(desc(CommentModel.created_at))
        elif order_by == CommentOrderBy.OLDEST:
            query = query.order_by(CommentModel.created_at)
        elif order_by == CommentOrderBy.MOST_LIKED:
            query = query.order_by(desc(CommentModel.likes_count))

        # apply pagination
        query = query.offset((page - 1) * per_page).limit(per_page)

        return query.all()

    # field to get all replies for a comment
    @strawberry.field
    async def get_replies_for_comment(
        self,
        info: Info,
        comment_id: int,
        order_by: CommentOrderBy = CommentOrderBy.NEWEST,
        depth: Optional[int] = None,
        page: int = 1,
        per_page: int = 20
    ) -> List[Comment]:
        """Get all replies for a comment"""
        
        # Get context attributes
        context = info.context
        db = context["db"]  # Access db from context dict
        user = context["user"]  # Access user from context dict

        # query the comments
        query = db.query(CommentModel).filter(
            CommentModel.parent_id == comment_id,
            CommentModel.is_deleted == False
        )

        # apply ordering
        if order_by == CommentOrderBy.NEWEST:
            query = query.order_by(desc(CommentModel.created_at))
        elif order_by == CommentOrderBy.OLDEST:
            query = query.order_by(CommentModel.created_at)
        elif order_by == CommentOrderBy.MOST_LIKED:
            query = query.order_by(desc(CommentModel.likes_count))

        # apply pagination
        query = query.offset((page - 1) * per_page).limit(per_page)

        return query.all()
