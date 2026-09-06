"""
FastAPI main application.
"""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from database import get_db, engine, Base
from models import RSSSource, Post, PostCategory
from services import RSSIngestService, CategorizationService
from config import settings

# Create tables if they don't exist (for development)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="News Aggregation API",
    description="RSS feed ingestion and Telegram distribution pipeline",
    version="1.0.0"
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic schemas
class RSSSourceSchema(BaseModel):
    rss_id: int
    rss_title: str
    rss_link: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PostSchema(BaseModel):
    post_id: str
    rss_id: int
    title: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    image_id: Optional[str] = None
    telegram_channel_id: Optional[int] = None
    status: Optional[str] = None  # computed field

    class Config:
        from_attributes = True


class IngestResult(BaseModel):
    feeds_fetched: int
    feeds_failed: int
    items_processed: int
    items_skipped_malformed: int
    posts_inserted: int
    posts_skipped_duplicate: int


class CategorizeResult(BaseModel):
    posts_processed: int
    posts_categorized: int
    images_generated: int
    posts_sent: int
    errors: int


# Endpoints
@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "News Aggregation API"}


@app.get("/sources", response_model=List[RSSSourceSchema])
def get_sources(db: Session = Depends(get_db)):
    """Get all RSS sources."""
    sources = db.query(RSSSource).all()
    return sources


@app.get("/posts", response_model=List[PostSchema])
def get_posts(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get paginated list of posts with optional status filter.
    
    Status values:
    - 'uncategorized': telegram_channel_id IS NULL
    - 'categorized': telegram_channel_id IS NOT NULL AND image_id IS NULL
    - 'sent': telegram_channel_id IS NOT NULL AND image_id IS NOT NULL
    """
    query = db.query(Post).order_by(Post.created_at.desc())
    
    # Apply status filter
    if status == 'uncategorized':
        query = query.filter(Post.telegram_channel_id.is_(None))
    elif status == 'categorized':
        query = query.filter(
            Post.telegram_channel_id.isnot(None),
            Post.image_id.is_(None)
        )
    elif status == 'sent':
        query = query.filter(Post.image_id.isnot(None))
    
    # Pagination
    offset = (page - 1) * page_size
    posts = query.offset(offset).limit(page_size).all()
    
    # Add computed status to each post
    result = []
    for post in posts:
        post_dict = {
            'post_id': post.post_id,
            'rss_id': post.rss_id,
            'title': post.title,
            'description': post.description,
            'created_at': post.created_at,
            'updated_at': post.updated_at,
            'image_id': post.image_id,
            'telegram_channel_id': post.telegram_channel_id,
        }
        
        # Compute status
        if post.telegram_channel_id is None:
            post_dict['status'] = 'uncategorized'
        elif post.image_id is None:
            post_dict['status'] = 'categorized'
        else:
            post_dict['status'] = 'sent'
        
        result.append(post_dict)
    
    return result


@app.post("/ingest", response_model=IngestResult)
def run_ingest(db: Session = Depends(get_db)):
    """
    Run Stage 1: RSS Ingest.
    
    Fetches all 5 RSS feeds, upserts sources, inserts new posts,
    skips duplicates and malformed items.
    """
    service = RSSIngestService(db)
    stats = service.ingest_all_feeds()
    return IngestResult(**stats)


@app.post("/categorize", response_model=CategorizeResult)
async def run_categorize(db: Session = Depends(get_db)):
    """
    Run Stage 2: Categorize & Distribute.
    
    Processes uncategorized posts, classifies audience, generates images,
    and sends to Telegram channels.
    """
    service = CategorizationService(db)
    stats = await service.categorize_and_distribute()
    return CategorizeResult(**stats)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
