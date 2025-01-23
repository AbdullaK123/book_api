import pytest
from fastapi.testclient import TestClient
from book_api.utils.book_utils import update_book_rating
from typing import List
from book_api import models
from sqlalchemy.orm import Session
from fastapi import UploadFile

# -------- Test Classes --------

class TestAuth:
    """Test authentication functionality"""
    
    def test_create_user(self, client: TestClient, user_data: dict, mock_request_headers: dict):
        response = client.post("/users/", json=user_data, headers=mock_request_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == user_data["username"]
        assert "password" not in data

    def test_login(self, client: TestClient, user_data: dict, mock_request_headers: dict):
        # Create user first
        client.post("/users/", json=user_data, headers=mock_request_headers)
        
        # Try login
        response = client.post(
            "/users/login",
            data={
                "username": user_data["username"],
                "password": user_data["password"]
            },
            headers=mock_request_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_token_ip_binding(self, client: TestClient, auth_headers: dict):
        """Test token fails with different IP"""
        different_headers = auth_headers.copy()
        different_headers['Host'] = '192.168.1.1'
        
        response = client.get("/books/", headers=different_headers)
        assert response.status_code == 401
        assert "IP address mismatch" in response.json()["detail"]

    def test_token_browser_binding(self, client: TestClient, auth_headers: dict):
        """Test token fails with different browser"""
        different_headers = auth_headers.copy()
        different_headers['User-Agent'] = 'Different Browser'
        
        response = client.get("/books/", headers=different_headers)
        assert response.status_code == 401
        assert "Browser mismatch" in response.json()["detail"]

    def test_token_device_binding(self, client: TestClient, auth_headers: dict):
        """Test token fails with different device"""
        different_headers = auth_headers.copy()
        different_headers['X-Device-Id'] = 'different-device'
        
        response = client.get("/books/", headers=different_headers)
        assert response.status_code == 401
        assert "Device mismatch" in response.json()["detail"]

class TestFollowers:
    """Test suite for follower operations"""
    
    def test_follow_user(self, client, auth_headers, test_follow_user, mock_request_headers):
        """Test that a user can follow another user"""
        # Create a user to follow
        response = client.post("/users/", json=test_follow_user, headers=mock_request_headers)
        user_to_follow = response.json()
        
        # Follow the user
        response = client.post(
            f"/users/{user_to_follow['id']}/follow",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert "Successfully followed user" in response.json()["message"]

        # destroy the test user aferwards
        client.delete(f"/users/{user_to_follow['id']}", headers=auth_headers)
        assert response.status_code == 200

    def test_unfollow_user(self, client, auth_headers, test_unfollow_user, mock_request_headers):
        """Test that a user can unfollow another user"""
        # Create and follow a user first
        response = client.post("/users/", json=test_unfollow_user, headers=mock_request_headers)
        user_to_unfollow = response.json()
        
        client.post(
            f"/users/{user_to_unfollow['id']}/follow",
            headers=auth_headers
        )
        
        # Now unfollow
        response = client.delete(
            f"/users/{user_to_unfollow['id']}/unfollow",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert "Successfully unfollowed user" in response.json()["message"]

        # destroy the test user aferwards
        client.delete(f"/users/{user_to_unfollow['id']}", headers=auth_headers)
        assert response.status_code == 200

    def test_follow_counts_update(self, client, auth_headers, test_follow_user, mock_request_headers):
        """Test that follower/following counts update correctly"""
        # Create a user to follow
        response = client.post("/users/", json=test_follow_user, headers=mock_request_headers)
        user_to_follow = response.json()
        
        # Get initial counts
        current_user = client.get("/users/me", headers=auth_headers).json()
        initial_following = current_user["following_count"]
        
        # Follow user
        client.post(
            f"/users/{user_to_follow['id']}/follow",
            headers=auth_headers
        )
        
        # Check counts updated
        current_user = client.get("/users/me", headers=auth_headers).json()
        assert current_user["following_count"] == initial_following + 1

        # destroy the test user aferwards
        client.delete(f"/users/{user_to_follow['id']}", headers=auth_headers)
        assert response.status_code == 200

    def test_cannot_follow_self(self, client, auth_headers):
        """Test that a user cannot follow themselves"""
        current_user = client.get("/users/me", headers=auth_headers).json()
        
        response = client.post(
            f"/users/{current_user['id']}/follow",
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "cannot follow yourself" in response.json()["detail"]

    def test_cannot_follow_twice(self, client, auth_headers, test_follow_user, mock_request_headers):
        """Test that a user cannot follow the same user twice"""
        # Create a user to follow
        response = client.post("/users/", json=test_follow_user, headers=mock_request_headers)
        user_to_follow = response.json()
        
        # Follow once
        client.post(
            f"/users/{user_to_follow['id']}/follow",
            headers=auth_headers
        )
        
        # Try to follow again
        response = client.post(
            f"/users/{user_to_follow['id']}/follow",
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "Already following" in response.json()["detail"]

    def test_get_followers_pagination(self, client, auth_headers):
        """Test pagination of followers list"""
        response = client.get(
            "/users/followers?page=1&per_page=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "page" in data
        assert "items" in data

    def test_get_following_pagination(self, client, auth_headers):
        """Test pagination of following list"""
        response = client.get(
            "/users/following?page=1&per_page=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "page" in data
        assert "items" in data

class TestBooks:
    """Test book-related functionality"""

    def test_create_book(self, client: TestClient, auth_headers: dict, book_data: dict):
        response = client.post("/books/", json=book_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == book_data["title"]
        assert data["author"] == book_data["author"]

    def test_get_books(self, client: TestClient, auth_headers: dict, book_data: dict):
        # Create a book first
        client.post("/books/", json=book_data, headers=auth_headers)
        
        response = client.get("/books/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_get_book_detail(self, client: TestClient, auth_headers: dict, book_data: dict):
        # Create book first
        create_response = client.post("/books/", json=book_data, headers=auth_headers)
        book_id = create_response.json()["id"]
        
        response = client.get(f"/books/{book_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == book_data["title"]

    def test_update_book(self, client: TestClient, auth_headers: dict, book_data: dict):
        # Create book first
        create_response = client.post("/books/", json=book_data, headers=auth_headers)
        book_id = create_response.json()["id"]
        
        update_data = {"title": "Updated Title"}
        response = client.put(f"/books/{book_id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["title"] == "Updated Title"

    def test_delete_book(self, client: TestClient, auth_headers: dict, book_data: dict):
        # Create book first
        create_response = client.post("/books/", json=book_data, headers=auth_headers)
        book_id = create_response.json()["id"]
        
        response = client.delete(f"/books/{book_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Book deleted successfully"

class TestReviews:
    """Test review-related functionality"""

    @pytest.mark.asyncio
    async def test_create_review(self, client: TestClient, auth_headers: dict, admin_headers: dict, book_data: dict, review_data: dict):
        # Create book as admin
        book_response = client.post("/books/", json=book_data, headers=admin_headers)
        book_id = book_response.json()["id"]
        
        # Create review as user
        review_with_book = {**review_data, "book_id": book_id}
        response = client.post("/reviews/", json=review_with_book, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == review_data["rating"]
        assert data["content"] == review_data["content"]


    @pytest.mark.asyncio
    async def test_update_average_rating(
        self, 
        client: TestClient, 
        db: Session,  # Add db dependency
        test_users: List[dict], 
        test_author: dict, 
        book_data: dict, 
        test_reviews: List[dict]
    ):
        """Test that book ratings are properly updated when reviews are added"""
        
        # Register the author
        response = client.post("/users/", json=test_author)
        assert response.status_code == 200

        # Login the author
        response = client.post(
            "/users/login", 
            data={"username": test_author["username"], "password": test_author["password"]}
        )
        assert response.status_code == 200
        
        # Create a book
        author_token = response.json()["access_token"]
        author_headers = {"Authorization": f"Bearer {author_token}"}
        response = client.post("/books/", json=book_data, headers=author_headers)
        assert response.status_code == 200
        book_id = response.json()["id"]

        # Add reviews from different users
        for test_user, test_review in zip(test_users, test_reviews):
            # Register user
            response = client.post("/users/", json=test_user)
            assert response.status_code == 200

            # Login user
            response = client.post(
                "/users/login",
                data={"username": test_user["username"], "password": test_user["password"]}
            )
            assert response.status_code == 200

            # Create review
            user_token = response.json()["access_token"]
            user_headers = {"Authorization": f"Bearer {user_token}"}
            review_with_book = {**test_review, "book_id": book_id}
            response = client.post("/reviews/", json=review_with_book, headers=user_headers)
            assert response.status_code == 200

        # Calculate expected average
        expected_avg = sum(review["rating"] for review in test_reviews) / len(test_reviews)
        expected_avg = round(expected_avg, 2)

        # Give time for async event processing
        await update_book_rating(db, book_id)

        # Verify the book's average rating
        book = db.query(models.Book).filter(models.Book.id == book_id).first()
        assert book.average_rating == expected_avg



    @pytest.mark.asyncio
    async def test_get_review_stats(self, client: TestClient, auth_headers: dict, admin_headers: dict, book_data: dict, review_data: dict):
        # Create book and review first
        book_response = client.post("/books/", json=book_data, headers=admin_headers)
        book_id = book_response.json()["id"]
        
        review_with_book = {**review_data, "book_id": book_id}
        client.post("/reviews/", json=review_with_book, headers=auth_headers)
        
        response = client.get(f"/reviews/book/{book_id}/stats", headers=auth_headers)
        assert response.status_code == 200
        stats = response.json()
        assert stats["total_reviews"] == 1
        assert str(review_data["rating"]) in str(stats["rating_distribution"])

    def test_like_review(self, client: TestClient, auth_headers: dict, admin_headers: dict, book_data: dict, review_data: dict):
        """Test liking a review"""
        # Create book as admin
        book_response = client.post("/books/", json=book_data, headers=admin_headers)
        book_id = book_response.json()["id"]
        
        # Create review as user
        review_with_book = {**review_data, "book_id": book_id}
        review_response = client.post("/reviews/", json=review_with_book, headers=auth_headers)
        review_id = review_response.json()["id"]
        
        # Like the review
        response = client.post(f"/users/{review_id}/like", headers=auth_headers)
        assert response.status_code == 200
        assert "Review liked successfully" in response.json()["message"]

        # Verify like count increased
        review = client.get(f"/reviews/{review_id}", headers=auth_headers).json()
        assert review["likes_count"] == 1

    def test_unlike_review(self, client: TestClient, auth_headers: dict, admin_headers: dict, book_data: dict, review_data: dict):
        """Test unliking a review"""
        # Create and like review first
        book_response = client.post("/books/", json=book_data, headers=admin_headers)
        book_id = book_response.json()["id"]
        
        review_with_book = {**review_data, "book_id": book_id}
        review_response = client.post("/reviews/", json=review_with_book, headers=auth_headers)
        review_id = review_response.json()["id"]
        
        client.post(f"/users/{review_id}/like", headers=auth_headers)
        
        # Unlike the review
        response = client.delete(f"/users/{review_id}/unlike", headers=auth_headers)
        assert response.status_code == 200
        assert "Review unliked successfully" in response.json()["message"]

        # Verify like count decreased
        review = client.get(f"/reviews/{review_id}", headers=auth_headers).json()
        assert review["likes_count"] == 0

    def test_cannot_like_review_twice(self, client: TestClient, auth_headers: dict, admin_headers: dict, book_data: dict, review_data: dict):
        """Test that a user cannot like the same review twice"""
        # Create and like review
        book_response = client.post("/books/", json=book_data, headers=admin_headers)
        book_id = book_response.json()["id"]
        
        review_with_book = {**review_data, "book_id": book_id}
        review_response = client.post("/reviews/", json=review_with_book, headers=auth_headers)
        review_id = review_response.json()["id"]
        
        client.post(f"/users/{review_id}/like", headers=auth_headers)
        
        # Try to like again
        response = client.post(f"/users/{review_id}/like", headers=auth_headers)
        assert response.status_code == 400
        assert "already liked this review" in response.json()["detail"]

    def test_cannot_unlike_not_liked_review(self, client: TestClient, auth_headers: dict, admin_headers: dict, book_data: dict, review_data: dict):
        """Test that a user cannot unlike a review they haven't liked"""
        # Create review
        book_response = client.post("/books/", json=book_data, headers=admin_headers)
        book_id = book_response.json()["id"]
        
        review_with_book = {**review_data, "book_id": book_id}
        review_response = client.post("/reviews/", json=review_with_book, headers=auth_headers)
        review_id = review_response.json()["id"]
        
        # Try to unlike without liking first
        response = client.delete(f"/users/{review_id}/unlike", headers=auth_headers)
        assert response.status_code == 400
        assert "have not liked this review" in response.json()["detail"]

    def test_get_liked_reviews(self, client: TestClient, auth_headers: dict, admin_headers: dict, book_data: dict, review_data: dict):
        """Test getting all reviews liked by a user"""
        liked_reviews = []
        
        # Create multiple books and reviews
        for i in range(3):
            # Create a book
            book_response = client.post(
                "/books/", 
                json={**book_data, "title": f"Test Book {i}"}, 
                headers=admin_headers
            )
            book_id = book_response.json()["id"]
            
            # Create a review for the book
            review_with_book = {**review_data, "book_id": book_id, "content": f"Review {i}"}
            review_response = client.post("/reviews/", json=review_with_book, headers=auth_headers)
            review_id = review_response.json()["id"]
            
            # Like the review
            client.post(f"/users/{review_id}/like", headers=auth_headers)
            liked_reviews.append(review_id)
        
        # Get liked reviews
        response = client.get("/users/liked_reviews", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == len(liked_reviews)
        assert all(review["id"] in liked_reviews for review in data["items"])

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_get_nonexistent_book(self, client: TestClient, auth_headers: dict):
        response = client.get("/books/99999", headers=auth_headers)
        assert response.status_code == 404
        assert "Book not found" in response.json()["detail"]

    def test_create_duplicate_user(self, client: TestClient, user_data: dict, mock_request_headers: dict):
        # Create user first time
        client.post("/users/", json=user_data, headers=mock_request_headers)
        
        # Try to create same user again
        response = client.post("/users/", json=user_data, headers=mock_request_headers)
        assert response.status_code == 400
        assert "Username already exists" in response.json()["detail"]

    def test_invalid_credentials(self, client: TestClient, user_data: dict, mock_request_headers: dict):
        # Create user first
        client.post("/users/", json=user_data, headers=mock_request_headers)
        
        # Try login with wrong password
        response = client.post(
            "/users/login",
            data={
                "username": user_data["username"],
                "password": "wrongpassword"
            },
            headers=mock_request_headers
        )
        assert response.status_code == 400
        assert "Invalid credentials" in response.json()["detail"]

    def test_review_own_book(self, client: TestClient, auth_headers: dict, book_data: dict, review_data: dict):
        # Create book
        book_response = client.post("/books/", json=book_data, headers=auth_headers)
        book_id = book_response.json()["id"]
        
        # Try to review own book
        review_with_book = {**review_data, "book_id": book_id}
        response = client.post("/reviews/", json=review_with_book, headers=auth_headers)
        assert response.status_code == 400
        assert "You cannot review your own book" in response.json()["detail"]


class TestShelves:
    """Test suite for shelf operations"""

    @pytest.fixture
    def shelf_data(self):
        """Fixture for shelf creation data"""
        return {
            "name": "Test Shelf",
            "description": "A test shelf",
            "is_public": True
        }

    @pytest.fixture
    def create_book(self, client, auth_headers):
        """Fixture to create a test book"""
        book_data = {
            "title": "Test Book",
            "author": "Test Author",
            "genre": "Fiction",
            "page_count": 200
        }
        response = client.post("/books/", json=book_data, headers=auth_headers)
        assert response.status_code == 200
        return response.json()

    def test_create_shelf(self, client, auth_headers, shelf_data):
        """Test creating a new shelf"""
        response = client.post(
            "/shelves/",
            json=shelf_data,
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == shelf_data["name"]
        assert data["description"] == shelf_data["description"]
        assert data["is_public"] == shelf_data["is_public"]
        assert "id" in data
        assert not data["is_default"]

    def test_create_duplicate_shelf(self, client, auth_headers, shelf_data):
        """Test creating a shelf with duplicate name"""
        # Create first shelf
        client.post("/shelves/", json=shelf_data, headers=auth_headers)
        
        # Try to create duplicate
        response = client.post(
            "/shelves/",
            json=shelf_data,
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_get_shelves(self, client, auth_headers, shelf_data):
        """Test getting user's shelves"""
        # Create some shelves
        client.post("/shelves/", json=shelf_data, headers=auth_headers)
        client.post(
            "/shelves/",
            json={**shelf_data, "name": "Second Shelf"},
            headers=auth_headers
        )

        response = client.get("/shelves/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        assert len(data["items"]) >= 2

    def test_get_shelf_by_id(self, client, auth_headers, shelf_data):
        """Test getting a specific shelf"""
        create_response = client.post(
            "/shelves/",
            json=shelf_data,
            headers=auth_headers
        )
        shelf_id = create_response.json()["id"]

        response = client.get(f"/shelves/{shelf_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["name"] == shelf_data["name"]

    def test_update_shelf(self, client, auth_headers, shelf_data):
        """Test updating a shelf"""
        create_response = client.post(
            "/shelves/",
            json=shelf_data,
            headers=auth_headers
        )
        shelf_id = create_response.json()["id"]

        update_data = {
            "name": "Updated Shelf",
            "description": "Updated description"
        }
        response = client.put(
            f"/shelves/{shelf_id}",
            json=update_data,
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["name"] == update_data["name"]
        assert response.json()["description"] == update_data["description"]

    def test_delete_shelf(self, client, auth_headers, shelf_data):
        """Test deleting a shelf"""
        create_response = client.post(
            "/shelves/",
            json=shelf_data,
            headers=auth_headers
        )
        shelf_id = create_response.json()["id"]

        response = client.delete(
            f"/shelves/{shelf_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Shelf deleted successfully"

        # Verify shelf is deleted
        get_response = client.get(
            f"/shelves/{shelf_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 404

    def test_add_book_to_shelf(self, client, auth_headers, shelf_data, create_book):
        """Test adding a book to a shelf"""
        # Create shelf
        shelf_response = client.post(
            "/shelves/",
            json=shelf_data,
            headers=auth_headers
        )
        shelf_id = shelf_response.json()["id"]
        book = create_book

        # Add book to shelf
        book_data = {
            "book_id": book["id"],
            "reading_status": "WANT_TO_READ"
        }
        response = client.post(
            f"/shelves/{shelf_id}/books",
            json=book_data,
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["book"]["id"] == book["id"]
        assert data["status"]["reading_status"] == "WANT_TO_READ"

    def test_move_book_between_shelves(
        self, client, auth_headers, shelf_data, create_book
    ):
        """Test moving a book between shelves"""
        # Create source shelf
        source_shelf = client.post(
            "/shelves/",
            json=shelf_data,
            headers=auth_headers
        ).json()

        # Create target shelf
        target_shelf = client.post(
            "/shelves/",
            json={**shelf_data, "name": "Target Shelf"},
            headers=auth_headers
        ).json()

        # Add book to source shelf
        book = create_book
        book_data = {
            "book_id": book["id"],
            "reading_status": "WANT_TO_READ"
        }
        client.post(
            f"/shelves/{source_shelf['id']}/books",
            json=book_data,
            headers=auth_headers
        )

        # Move book to target shelf
        response = client.put(
            f"/shelves/{source_shelf['id']}/books/{book['id']}/move",
            params={"target_shelf_id": target_shelf["id"]},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert "moved successfully" in response.json()["message"]

    def test_get_shelf_books(self, client, auth_headers, shelf_data, create_book):
        """Test getting all books in a shelf"""
        # Create shelf
        shelf_response = client.post(
            "/shelves/",
            json=shelf_data,
            headers=auth_headers
        )
        shelf_id = shelf_response.json()["id"]
        book = create_book

        # Add book to shelf
        book_data = {
            "book_id": book["id"],
            "reading_status": "WANT_TO_READ"
        }
        client.post(
            f"/shelves/{shelf_id}/books",
            json=book_data,
            headers=auth_headers
        )

        # Get shelf books
        response = client.get(
            f"/shelves/{shelf_id}/books",
            headers=auth_headers
        )
        assert response.status_code == 200
        books = response.json()
        assert len(books) >= 1
        assert any(b["book"]["id"] == book["id"] for b in books)

    def test_batch_move_books(
        self, client, auth_headers, shelf_data, create_book
    ):
        """Test moving multiple books between shelves"""
        # Create shelves
        source_shelf = client.post(
            "/shelves/",
            json=shelf_data,
            headers=auth_headers
        ).json()

        target_shelf = client.post(
            "/shelves/",
            json={**shelf_data, "name": "Target Shelf"},
            headers=auth_headers
        ).json()

        # Create and add multiple books
        book_ids = []
        for i in range(3):
            book = create_book
            book_data = {
                "book_id": book["id"],
                "reading_status": "WANT_TO_READ"
            }
            client.post(
                f"/shelves/{source_shelf['id']}/books",
                json=book_data,
                headers=auth_headers
            )
            book_ids.append(book["id"])

        # Move books in batch
        response = client.put(
            f"/shelves/{source_shelf['id']}/books/batch/move",
            json={"book_ids": book_ids},
            params={"target_shelf_id": target_shelf["id"]},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert "Successfully moved" in response.json()["message"]

    @pytest.mark.parametrize("invalid_shelf_id", [-1, 0, 99999])
    def test_invalid_shelf_access(
        self, client, auth_headers, invalid_shelf_id
    ):
        """Test accessing invalid shelf IDs"""
        endpoints = [
            ("get", f"/shelves/{invalid_shelf_id}"),
            ("put", f"/shelves/{invalid_shelf_id}"),
            ("delete", f"/shelves/{invalid_shelf_id}"),
            ("get", f"/shelves/{invalid_shelf_id}/books"),
        ]

        for method, endpoint in endpoints:
            response = client.request(
                method,
                endpoint,
                headers=auth_headers,
                json={} if method == "put" else None
            )
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

# -------- Test Files Router --------
class TestFilesRouter:
    """Test suite for file upload, retrieval, update and deletion operations"""

    @pytest.mark.asyncio
    async def test_upload_profile_picture_success(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        test_image: UploadFile
    ):
        """
        Tests successful profile picture upload.
        Verifies:
        1. Response status code is 200
        2. Response contains valid S3 URL
        3. URL is stored in user profile
        """
        # Upload the profile picture
        files = {"file": ("test.jpg", test_image.file, "image/jpeg")}
        response = client.post(
            "/files/profile-picture",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 200
        assert "profile_picture" in response.json()
        assert response.json()["profile_picture"].startswith(
            "https://bookapi-images.s3.amazonaws.com/profiles/"
        )

    @pytest.mark.asyncio
    async def test_get_profile_picture_success(
        self,
        client: TestClient,
        auth_headers: dict,
        test_user: models.User,
        test_image: UploadFile
    ):
        """Tests successful profile picture retrieval"""
        # First upload a profile picture
        files = {"file": ("test.jpg", test_image.file, "image/jpeg")}
        upload_response = client.post(
            "/files/profile-picture",
            headers=auth_headers,
            files=files
        )
        assert upload_response.status_code == 200
        
        # Get the current user's ID from the auth headers
        current_user = client.get("/users/me", headers=auth_headers).json()
        user_id = current_user["id"]
        
        # Now try to retrieve it
        response = client.get(
            f"/files/profile-picture/{user_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"

    @pytest.mark.asyncio
    async def test_get_book_cover_success(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        book_data: dict,
        test_image: UploadFile
    ):
        """
        Tests successful book cover retrieval.
        Creates a book, uploads its cover, then verifies retrieval.
        """
        # First create a book
        book_response = client.post("/books/", json=book_data, headers=auth_headers)
        book_id = book_response.json()["id"]
        
        # Upload a cover for the book
        files = {"file": ("test.jpg", test_image.file, "image/jpeg")}
        client.post(
            f"/files/book-cover/{book_id}",
            headers=auth_headers,
            files=files
        )
        
        # Try to retrieve the cover
        response = client.get(
            f"/files/book-cover/{book_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"

    @pytest.mark.asyncio
    async def test_upload_book_cover_success(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        book_data: dict,
        test_image: UploadFile
    ):
        """
        Tests successful book cover upload.
        Creates a book first, then verifies cover upload.
        """
        # Create a book first
        book_response = client.post("/books/", json=book_data, headers=auth_headers)
        book_id = book_response.json()["id"]
        
        # Upload the cover
        files = {"file": ("test.jpg", test_image.file, "image/jpeg")}
        response = client.post(
            f"/files/book-cover/{book_id}",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 200
        assert "cover_url" in response.json()
        assert response.json()["cover_url"].startswith(
            "https://bookapi-images.s3.amazonaws.com/covers/"
        )

    @pytest.mark.asyncio
    async def test_update_profile_picture_success(
        self,
        client: TestClient,
        auth_headers: dict,
        test_image: UploadFile
    ):
        """Tests successful profile picture update."""
        # Upload initial profile picture
        files = {"file": ("test.jpg", test_image.file, "image/jpeg")}
        initial_response = client.post(
            "/files/profile-picture",
            headers=auth_headers,
            files=files
        )
        assert initial_response.status_code == 200

        # Update the profile picture
        test_image.file.seek(0)  # Reset file pointer
        files = {"file": ("test2.jpg", test_image.file, "image/jpeg")}
        response = client.put(
            "/files/profile-picture",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_book_cover_success(
        self,
        client: TestClient,
        auth_headers: dict,
        book_data: dict,
        test_image: UploadFile
    ):
        """Tests successful book cover update."""
        # Create book and upload initial cover
        book_response = client.post("/books/", json=book_data, headers=auth_headers)
        book_id = book_response.json()["id"]

        files = {"file": ("test.jpg", test_image.file, "image/jpeg")}
        initial_response = client.post(
            f"/files/book-cover/{book_id}",
            headers=auth_headers,
            files=files
        )
        assert initial_response.status_code == 200

        # Update the cover
        test_image.file.seek(0)  # Reset file pointer
        files = {"file": ("test2.jpg", test_image.file, "image/jpeg")}
        response = client.put(
            f"/files/book-cover/{book_id}",
            headers=auth_headers,
            files=files
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_book_cover_success(
        self,
        client: TestClient,
        auth_headers: dict,
        book_data: dict,
        test_image: UploadFile
    ):
        """Tests successful book cover deletion."""
        # Create book and upload cover
        book_response = client.post("/books/", json=book_data, headers=auth_headers)
        book_id = book_response.json()["id"]

        files = {"file": ("test.jpg", test_image.file, "image/jpeg")}
        client.post(
            f"/files/book-cover/{book_id}",
            headers=auth_headers,
            files=files
        )

        # Delete the cover
        response = client.delete(
            f"/files/book-cover/{book_id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Book cover deleted successfully"


    @pytest.mark.asyncio
    async def test_delete_book_cover_success(
        self, 
        client: TestClient, 
        auth_headers: dict, 
        book_data: dict,
        test_image: UploadFile
    ):
        """
        Tests successful book cover deletion.
        Creates book, uploads cover, then verifies deletion.
        """
        # Create book and upload cover
        book_response = client.post("/books/", json=book_data, headers=auth_headers)
        book_id = book_response.json()["id"]
        
        files = {"file": ("test.jpg", test_image.file, "image/jpeg")}
        client.post(
            f"/files/book-cover/{book_id}",
            headers=auth_headers,
            files=files
        )
        
        # Delete the cover
        response = client.delete(
            f"/files/book-cover/{book_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Book cover deleted successfully"