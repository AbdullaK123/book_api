from typing import Dict, List, Any, Callable, Coroutine
from dataclasses import dataclass
import logging
from sqlalchemy.orm import Session
from book_api.database import SessionLocal
from book_api.utils.book_utils import (
    update_book_rating as update_book_rating_util, 
    create_default_shelves as create_default_shelves_util
) 

logger = logging.getLogger(__name__)

@dataclass
class Event:
    """Event data container for the event bus system.
    
    Attributes:
        name (str): The name of the event
        data (Dict[str, Any]): Dictionary containing event-related data
    """
    name: str
    data: Dict[str, Any]

class EventBus:
    """Event Bus implementation for handling asynchronous events and callbacks.
    
    This class provides a simple publish-subscribe (pub/sub) pattern implementation
    for asynchronous event handling. It allows components to subscribe to specific
    events and receive notifications when those events are published.
    
    Attributes:
        subscribers (Dict[str, List[Callable]]): Dictionary mapping event names to lists of callback functions
    
    Example:
        event_bus = EventBus()
        async def handle_user_created(event):
            print(f"User created: {event.data}")
        event_bus.subscribe("user_created", handle_user_created)
        await event_bus.publish(Event("user_created", {"id": 1, "name": "John"}))
    """
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        logger.info("EventBus initialized")
        
    def subscribe(self, event_name: str, callback: Callable[..., Coroutine]):
        """Subscribe a callback function to a specific event.
        
        Args:
            event_name (str): Name of the event to subscribe to
            callback (Callable): Async function to be called when event is published
        """
        if event_name not in self.subscribers:
            self.subscribers[event_name] = []
            logger.debug(f"Created new subscriber list for event: {event_name}")
        self.subscribers[event_name].append(callback)
        logger.info(f"Subscribed handler '{callback.__name__}' to event '{event_name}'")
        
    async def publish(self, event: Event):
        """Publish an event and execute all subscribed callbacks.
        
        Args:
            event (Event): Event instance containing the event name and data
        """
        logger.debug(f"Publishing event: {event.name} with data: {event.data}")
        if event.name in self.subscribers:
            logger.info(f"Found {len(self.subscribers[event.name])} handler(s) for event '{event.name}'")
            for callback in self.subscribers[event.name]:
                try:
                    await callback(event)
                    logger.debug(f"Successfully executed handler '{callback.__name__}' for event '{event.name}'")
                except Exception as e:
                    logger.error(f"Error in event handler '{callback.__name__}' for event '{event.name}': {str(e)}")
        else:
            logger.warning(f"No handlers found for event: {event.name}")

async def handle_update_book_rating(event: Event):
    """Handle the update_book_rating event by updating a book's rating.
    
    Args:
        event (Event): Event containing book_id in its data
    """
    logger.info(f"Processing update_book_rating event for book: {event.data.get('book_id')}")
    try:
        book_id = event.data.get('book_id')
        if not book_id:
            raise ValueError("book_id missing from event data")
            
        db = SessionLocal()
        try:
            await update_book_rating_util(db, book_id)
            logger.info(f"Successfully updated rating for book: {book_id}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to update book rating: {str(e)}", exc_info=True)

async def handle_user_created(event: Event):
    """Handle the user_created event by creating default shelves for the user.
    
    Args:
        event (Event): Event containing user_id in its data
    """
    logger.info(f"Processing user_created event for user: {event.data.get('user_id')}")
    try:
        user_id = event.data.get('user_id')
        if not user_id:
            raise ValueError("user_id missing from event data")
            
        db = SessionLocal()
        try:
            await create_default_shelves_util(db, user_id)
            logger.info(f"Successfully created default shelves for user: {user_id}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to create default shelves: {str(e)}", exc_info=True)

# Create event bus instance
event_bus = EventBus()

# Register event handlers
event_bus.subscribe("update_book_rating", handle_update_book_rating)
event_bus.subscribe("user_created", handle_user_created)

logger.info("Event bus system initialized with default handlers")
