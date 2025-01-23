import strawberry
from strawberry.fastapi import GraphQLRouter
from book_api.graphql_routes.queries import Query
from book_api.graphql_routes.mutations import Mutation
from book_api.graphql_routes.context import get_context

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation
)

router = GraphQLRouter(
    schema=schema,
    context_getter=get_context
)

