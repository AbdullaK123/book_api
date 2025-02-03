from fastapi.testclient import TestClient


class TestGraphQLMutations:
    """Test GraphQL mutation operations"""

    def test_create_comment(self, client: TestClient, auth_headers: dict, test_review: dict):
        """Test creating a comment"""
        mutation = """
        mutation {
            createComment(
                input: {
                    content: "Test comment",
                    reviewId: %d
                }
            ) {
                id
                content
                path
                depth
                user {
                    username
                }
            }
        }
        """ % test_review["id"]
        
        response = client.post(
            "/graphql",
            headers=auth_headers,
            json={"query": mutation}
        )
        
        assert response.status_code == 200
        data = response.json()
        print(data)
        assert "data" in data
        assert "errors" not in data
        created_comment = data["data"]["createComment"]
        assert created_comment["content"] == "Test comment"

    def test_update_comment(self, client: TestClient, auth_headers: dict, test_comment: dict):
        """Test updating a comment"""
        mutation = """
        mutation {
            updateComment(
                commentId: %d,
                input: {
                    content: "Updated comment"
                }
            ) {
                id
                content
            }
        }
        """ % test_comment["id"]
        
        response = client.post(
            "/graphql",
            headers=auth_headers,
            json={"query": mutation}
        )
        
        assert response.status_code == 200
        data = response.json()
        print(data)
        assert "data" in data
        assert "errors" not in data
        updated_comment = data["data"]["updateComment"]
        assert updated_comment["content"] == "Updated comment"

    def test_like_comment(self, client: TestClient, auth_headers: dict, test_comment: dict):
        """Test liking a comment"""
        mutation = """
        mutation {
            likeComment(commentId: %d) {
                id
                likesCount
            }
        }
        """ % test_comment["id"]
        
        response = client.post(
            "/graphql",
            headers=auth_headers,
            json={"query": mutation}
        )
        
        assert response.status_code == 200
        data = response.json()
        print(data)
        assert "data" in data
        assert "errors" not in data
        liked_comment = data["data"]["likeComment"]
        assert liked_comment["likesCount"] == 1

    def test_unlike_comment(self, client: TestClient, auth_headers: dict, test_comment: dict):
        """Test unliking a comment"""

        # Like the comment first
        like_mutation = """
        mutation {
            likeComment(commentId: %d) {
                id
                likesCount
            }
        }
        """ % test_comment["id"]

        like_response = client.post(
            "/graphql",
            headers=auth_headers,
            json={"query": like_mutation}
        )
        assert like_response.status_code == 200
        like_data = like_response.json()
        assert "data" in like_data
        assert "errors" not in like_data

        # Unlike the comment
        mutation = """
        mutation {
            unlikeComment(commentId: %d) {
                id
                likesCount
            }
        }
        """ % test_comment["id"]
        
        response = client.post(
            "/graphql",
            headers=auth_headers,
            json={"query": mutation}
        )
        
        assert response.status_code == 200
        data = response.json()
        print(data)
        assert "data" in data
        assert "errors" not in data
        unliked_comment = data["data"]["unlikeComment"]
        assert unliked_comment["likesCount"] == 0

    def test_delete_comment(self, client: TestClient, auth_headers: dict, test_comment: dict):
        """Test deleting a comment"""
        mutation = """
        mutation {
            deleteComment(commentId: %d) {
                id
                isDeleted
            }
        }
        """ % test_comment["id"]
        
        response = client.post(
            "/graphql",
            headers=auth_headers,
            json={"query": mutation}
        )
        
        assert response.status_code == 200
        data = response.json()
        print(data)
        assert "data" in data
        assert "errors" not in data
        deleted_comment = data["data"]["deleteComment"]
        assert deleted_comment["isDeleted"]

class TestGraphQLQueries:
    """Test GraphQL query operations"""

    def test_get_comment_by_id(self, client: TestClient, auth_headers: dict, test_comment: dict):
        """Test getting a single comment by ID"""
        query = """
        query {
            getCommentById(commentId: %d) {
                id
                content
                likesCount
                isDeleted
                user {
                    id
                    username
                }
            }
        }
        """ % test_comment["id"]
        
        response = client.post(
            "/graphql",
            headers=auth_headers,
            json={"query": query}
        )
        
        assert response.status_code == 200
        data = response.json()
        print(data)
        assert "data" in data
        assert "errors" not in data
        comment = data["data"]["getCommentById"]
        assert comment["id"] == test_comment["id"]
        assert comment["content"] == test_comment["content"]

    def test_get_comments_for_review(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        test_review: dict,
        test_comments: list
    ):
        """Test getting all comments for a review"""
        query = """
        query {
            getCommentsForReview(
                reviewId: %d,
                orderBy: NEWEST,
                page: 1,
                perPage: 10
            ) {
                id
                content
                path
                depth
                likesCount
                user {
                    username
                }
                isDeleted
            }
        }
        """ % test_review["id"]
        
        response = client.post(
            "/graphql",
            headers=auth_headers,
            json={"query": query}
        )
        
        assert response.status_code == 200
        data = response.json()
        print(data)
        assert "data" in data
        assert "errors" not in data
        
        comments = data["data"]["getCommentsForReview"]
        assert len(comments) == len(test_comments)
        assert all(not comment["isDeleted"] for comment in comments)
        assert all(comment["depth"] == 0 for comment in comments)  # All top-level comments


    def test_get_replies_for_comment(
        self, 
        client: TestClient, 
        auth_headers: dict,
        test_comment_with_replies: dict
    ):
        """Test getting replies for a comment"""
        query = """
        query {
            getRepliesForComment(
                commentId: %d,
                orderBy: NEWEST,
                page: 1,
                perPage: 10
            ) {
                id
                content
                path
                depth
                likesCount
                user {
                    username
                }
                isDeleted
            }
        }
        """ % test_comment_with_replies["parent"]["id"]
        
        response = client.post(
            "/graphql",
            headers=auth_headers,
            json={"query": query}
        )
        
        assert response.status_code == 200
        data = response.json()
        print(data)
        assert "data" in data
        assert "errors" not in data
        
        replies = data["data"]["getRepliesForComment"]
        assert len(replies) == len(test_comment_with_replies["replies"])
        assert all(not reply["isDeleted"] for reply in replies)
        assert all(reply["depth"] == 1 for reply in replies)  # All direct replies

class TestGraphQLAuthentication:
    """Test authentication requirements"""

    def test_unauthenticated_request(self, client: TestClient):
        """Test that unauthenticated requests return proper GraphQL errors"""
        query = """
        query {
            getCommentsForReview(reviewId: 1) {
                id
                content
            }
        }
        """
        
        response = client.post(
            "/graphql",
            json={"query": query}
        )
        
        # Either response should indicate auth error
        if response.status_code == 200:
            # GraphQL style error
            data = response.json()
            assert "errors" in data
            assert any("authenticated" in str(error).lower() for error in data["errors"])
        else:
            # REST style error
            assert response.status_code == 401
            assert "authenticated" in response.json()["detail"].lower()


    def test_invalid_token(self, client: TestClient):
        """Test that invalid tokens return proper GraphQL errors"""
        headers = {
            "Authorization": "Bearer invalid_token"
        }

        query = """
        query {
            getCommentsForReview(reviewId: 1) {
                id
                content
            }
        }
        """

        response = client.post(
            "/graphql",
            headers=headers,
            json={"query": query}
        )

        # Either response should indicate auth error
        if response.status_code == 200:
            # GraphQL style error
            data = response.json()
            assert "errors" in data
            assert any(
                "validate" in str(error).lower() or 
                "credentials" in str(error).lower() or 
                "authentication" in str(error).lower()
                for error in data["errors"]
            )
        else:
            # REST style error
            assert response.status_code == 401
            error_message = response.json()["detail"].lower()
            assert any(
                text in error_message
                for text in ["validate", "credentials", "authentication"]
            ), f"Expected auth error message, got: {error_message}"