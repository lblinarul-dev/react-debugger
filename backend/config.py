"""
Configuration settings from environment variables.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/news_db"
    
    # OpenAI
    openai_api_key: Optional[str] = None
    
    # Telegram
    telegram_bot_token: Optional[str] = None
    telegram_channel_chat_id: str = "2025726822"  # From n8n workflow
    
    # ImgBB (for image hosting)
    imgbb_api_key: Optional[str] = None
    
    # RSS Feeds (from n8n workflow)
    rss_feeds: list = [
        {"feed_url": "https://www.ansa.it/sito/ansait_rss.xml", "rss_title": "ANSA"},
        {"feed_url": "https://feeds.thelocal.com/rss/it", "rss_title": "The Local Italy"},
        {"feed_url": "https://www.fanpage.it/feed/", "rss_title": "Fanpage"},
        {"feed_url": "https://www.ilpost.it/feed/", "rss_title": "Il Post"},
        {"feed_url": "https://feeds.bbci.co.uk/news/world/rss.xml", "rss_title": "BBC News World"},
    ]
    
    # Categorization batch size (matching n8n's LIMIT 3)
    categorize_batch_size: int = 3

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
