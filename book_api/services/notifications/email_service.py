from fastapi_mail import FastMail, MessageSchema
from book_api.settings import config
from pydantic import EmailStr
from typing import List
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.fastmail = FastMail(config.email_config)

    async def __send_email(
        self,
        subject: str,
        recipients: List[EmailStr],
        body: str
    ):
        try: 
            message = MessageSchema(
                subject=subject,
                recipients=recipients,
                body=body,
                subtype="html"
            )

            await self.fastmail.send_message(message)
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error sending email"
            )


    async def send_welcome_email(self, email: EmailStr):
        subject = "Welcome to BookReads"
        body = f"""
        <h1>Welcome to BookReads</h1>
        <p>Thank you for signing up for BookReads. We hope you enjoy the service.</p>
        """

        await self.__send_email(subject, [email], body)

    async def send_password_reset_email(self, email: EmailStr, token: str):
        subject = "Password Reset Request"
        body = f"""
        <h1>Password Reset Request</h1>
        <p>You have requested a password reset. Click the link below to reset your password.</p>
        <a href="{config.FRONTEND_URL}/reset-password?token={token}">Reset Password</a>
        """

        await self.__send_email(subject, [email], body)

    async def follower_notification(
        self, 
        email: EmailStr, 
        follower: str,
        follower_profile_url: str  # Add more context
    ):
        subject = "New Follower"
        body = f"""
        <h1>New Follower</h1>
        <p>You have a new follower: {follower}</p>
        <p>View their profile: <a href="{follower_profile_url}">here</a></p>
        """
        await self.__send_email(subject, [email], body)

    async def review_notification(
        self, 
        email: EmailStr, 
        book: str,
        reviewer: str,
        review_url: str  # Add more context
    ):
        subject = "New Review"
        body = f"""
        <h1>New Review</h1>
        <p>{reviewer} posted a new review for {book}</p>
        <p>Read the review: <a href="{review_url}">here</a></p>
        """
        await self.__send_email(subject, [email], body)


email_service = EmailService()
