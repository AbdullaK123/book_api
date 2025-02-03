import pytest
from book_api.services.notifications.email_service import email_service


class TestEmailService:

    @pytest.mark.asyncio
    async def test_send_welcome_email(self, mocker):
        
        # mock the send_message method
        mock_send = mocker.patch.object(email_service.fastmail, "send_message")

        # test the mock send_message method
        await email_service.send_welcome_email("test@example.com")

        # assert that the send_message method was called
        mock_send.assert_called_once()
        message = mock_send.call_args[0][0]
        assert message.subject == "Welcome to BookReads"
        assert message.recipients == ["test@example.com"]
        assert "Welcome to BookReads" in message.body


    @pytest.mark.asyncio
    async def test_follower_notification(self, mocker):

        # mock the send_message method
        mock_send = mocker.patch.object(email_service.fastmail, "send_message")

        # test the mock send_message method
        await email_service.follower_notification(
            "test@example.com",
            "TestFollower",
            "http://test.com/profile/1"
        )

        # assert that the send_message method was called
        mock_send.assert_called_once()
        message = mock_send.call_args[0][0]
        assert message.subject == "New Follower"
        assert message.recipients == ["test@example.com"]
        assert "New Follower" in message.body

    @pytest.mark.asyncio
    async def test_review_notification(self, mocker):

        # mock the send_message method
        mock_send = mocker.patch.object(email_service.fastmail, "send_message")

        # test the mock send_message method
        await email_service.review_notification(
            "test@example.com",
            "The Tale of Two Cities",
            "test_reviewer",
            "http://test.com/review/1"
        )

        # assert that the send_message method was called
        mock_send.assert_called_once()
        message = mock_send.call_args[0][0]
        assert message.subject == "New Review"
        assert message.recipients == ["test@example"]
        assert "New Review" in message.body
        assert "The Tale of Two Cities" in message.body