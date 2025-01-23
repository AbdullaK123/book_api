from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from book_api.routers import users, books, reviews, shelves, files
from book_api.core.rate_limiter import limiter
from book_api.graphql_routes.schema import router as graphql_router
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded


app = FastAPI(
    title="Book API",
    description="A simple API to manage books and reviews",
    version="1.0.0"
)

# Add rate limiter to the application
app.state.limiter = limiter

# Add rate limit exceeded handler
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:3000",  
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router)
app.include_router(books.router)
app.include_router(reviews.router)
app.include_router(shelves.router)
app.include_router(files.router)
app.include_router(graphql_router, prefix="/graphql")

# Create a sub-application for the token endpoint
@app.post("/token", tags=["auth"])
def get_token():
    return RedirectResponse(url="/users/login", status_code=307)

@app.get("/", tags=["root"])
def root():
    """Welcome message for the API"""
    return {
        "message": "Welcome to Book API",
        "docs": "/docs",  # Link to auto-generated docs
        "endpoints": {
            "users": "/users",
            "books": "/books",
            "reviews": "/reviews",
            "shelves": "/shelves",
            "files": "/files",
            "graphql": "/graphql"
        }
    }

# Optional: Health check endpoint
@app.get("/health", tags=["health"])
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0"
    }