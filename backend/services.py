"""
Services for RSS feed ingestion, LLM classification, image generation, and Telegram sending.
"""
import asyncio
import feedparser
import httpx
from openai import OpenAI
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from models import RSSSource, Post, PostCategory
from config import settings
import logging

logger = logging.getLogger(__name__)


class RSSIngestService:
    """Service for ingesting RSS feeds."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def upsert_source(self, rss_title: str, rss_link: str) -> Optional[RSSSource]:
        """Upsert an RSS source, returning the source record."""
        try:
            # Check if exists
            existing = self.db.query(RSSSource).filter(
                RSSSource.rss_link == rss_link
            ).first()
            
            if existing:
                return existing
            
            # Create new
            source = RSSSource(rss_title=rss_title, rss_link=rss_link)
            self.db.add(source)
            self.db.commit()
            self.db.refresh(source)
            return source
        except Exception as e:
            logger.error(f"Error upserting RSS source {rss_link}: {e}")
            self.db.rollback()
            return None
    
    def fetch_feed(self, feed_url: str) -> Tuple[bool, List[Dict[str, Any]]]:
        """Fetch and parse an RSS feed. Returns (success, items)."""
        try:
            feed = feedparser.parse(feed_url)
            
            if feed.bozo:
                # Feed parsing had issues, but we still try to process entries
                logger.warning(f"Feed {feed_url} had parsing issues (bozo={feed.bozo})")
            
            items = []
            for entry in feed.entries:
                # Extract fields similar to n8n's Read RSS Feeds node
                item = {
                    'guid': getattr(entry, 'guid', None),
                    'link': getattr(entry, 'link', None),
                    'title': getattr(entry, 'title', ''),
                    'contentSnippet': getattr(entry, 'summary', ''),  # summary is like contentSnippet
                    'content': getattr(entry, 'summary', ''),
                }
                items.append(item)
            
            return True, items
        except Exception as e:
            logger.error(f"Error fetching feed {feed_url}: {e}")
            return False, []
    
    def process_feed_item(self, item: Dict[str, Any], rss_source: RSSSource) -> Optional[Dict[str, Any]]:
        """Process a single feed item, returning normalized data or None if should skip."""
        try:
            # Match n8n's "Keep Needed Columns" logic
            if item.get('error'):
                return {'skip': True, 'post_id': None}
            
            # Generate post_id from guid, link, or title (same as n8n)
            post_id = str(item.get('guid') or item.get('link') or item.get('title') or '')
            
            if not post_id:
                return {'skip': True, 'post_id': None}
            
            description = item.get('contentSnippet') or item.get('content') or ''
            
            return {
                'skip': False,
                'post_id': post_id,
                'rss_id': rss_source.rss_id,
                'title': item.get('title', ''),
                'description': description,
            }
        except Exception as e:
            logger.error(f"Error processing feed item: {e}")
            return {'skip': True, 'post_id': None}
    
    def save_post(self, post_data: Dict[str, Any]) -> bool:
        """Save a post, skipping on conflict (same as n8n's skipOnConflict)."""
        try:
            # Check if post already exists
            existing = self.db.query(Post).filter(
                Post.post_id == post_data['post_id']
            ).first()
            
            if existing:
                return False  # Skipped due to conflict
            
            post = Post(
                post_id=post_data['post_id'],
                rss_id=post_data['rss_id'],
                title=post_data['title'],
                description=post_data.get('description', ''),
            )
            self.db.add(post)
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving post {post_data.get('post_id')}: {e}")
            self.db.rollback()
            return False
    
    def ingest_all_feeds(self) -> Dict[str, int]:
        """Run the full RSS ingest process. Returns summary counts."""
        stats = {
            'feeds_fetched': 0,
            'feeds_failed': 0,
            'items_processed': 0,
            'items_skipped_malformed': 0,
            'posts_inserted': 0,
            'posts_skipped_duplicate': 0,
        }
        
        for feed_config in settings.rss_feeds:
            feed_url = feed_config['feed_url']
            rss_title = feed_config['rss_title']
            
            # Upsert source
            source = self.upsert_source(rss_title, feed_url)
            if not source:
                stats['feeds_failed'] += 1
                continue
            
            stats['feeds_fetched'] += 1
            
            # Fetch feed (with error handling like n8n's continueRegularOutput)
            success, items = self.fetch_feed(feed_url)
            if not success:
                stats['feeds_failed'] += 1
                continue
            
            # Process each item
            for item in items:
                processed = self.process_feed_item(item, source)
                
                if not processed or processed.get('skip'):
                    stats['items_skipped_malformed'] += 1
                    continue
                
                stats['items_processed'] += 1
                
                # Save post (skipping duplicates)
                if self.save_post(processed):
                    stats['posts_inserted'] += 1
                else:
                    stats['posts_skipped_duplicate'] += 1
        
        return stats


class CategorizationService:
    """Service for categorizing posts and sending to Telegram."""
    
    # Audience mapping from n8n workflow
    AUD_MAP = {
        'child': 'child', 'children': 'child', 'kids': 'child',
        'women': 'women', 'woman': 'women',
        'man': 'man', 'men': 'man',
    }
    ID_MAP = {'child': 1, 'women': 2, 'man': 3}
    
    def __init__(self, db: Session):
        self.db = db
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
    
    def get_uncategorized_posts(self, limit: int = None) -> List[Post]:
        """Get posts where telegram_channel_id IS NULL, oldest first."""
        if limit is None:
            limit = settings.categorize_batch_size
        
        query = self.db.query(Post).filter(
            Post.telegram_channel_id.is_(None)
        ).order_by(Post.created_at.asc()).limit(limit)
        
        return query.all()
    
    def classify_audience(self, title: str, description: str) -> Tuple[str, int, str]:
        """
        Classify article audience using LLM.
        Returns (audience, telegram_channel_id, reason).
        
        Matches n8n's prompt logic exactly:
        - child (1): content for/about kids/children
        - women (2): content primarily for women
        - man (3): default fallback for anything else
        """
        if not self.client:
            # Fallback without LLM - default to man/3
            logger.warning("No OpenAI client, using fallback classification")
            return 'man', 3, 'No OpenAI API key configured'
        
        try:
            prompt = f"""Categorize the audience of this article from its description.
Title: {title}
Description: {description}

You categorize a news article into exactly ONE audience and its Telegram channel id.
Choose audience from: "child", "women", "man".
Map audience to telegram_channel_id:
- child  -> 1
- women  -> 2
- man    -> 3

Per-channel filters:
- child (1): content for or about kids/children, toys, playgrounds, schools, family fun, child education, kids activities.
- women (2): content primarily for or about women, womens health, womens events, topics targeted at a female audience.
- man (3): content primarily for or about men, or general/professional/other topics that do not clearly fit child or women (default fallback).

Return audience, telegram_channel_id (1, 2 or 3), and a short reason.
If it does not clearly fit child or women, choose man / 3.

Respond with JSON in this format:
{{"audience": "child|women|man", "telegram_channel_id": 1|2|3, "reason": "..."}}"""

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Using a reasonable default model
                messages=[
                    {"role": "system", "content": "You are a news classifier. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200,
            )
            
            # Parse response
            content = response.choices[0].message.content.strip()
            # Try to extract JSON
            import json
            import re
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(content)
            
            # Apply classification logic (matching n8n's Apply Classification node)
            audience_raw = str(result.get('audience', '')).lower()
            audience = self.AUD_MAP.get(audience_raw, 'man')
            
            channel_id = result.get('telegram_channel_id')
            if channel_id not in [1, 2, 3]:
                channel_id = self.ID_MAP[audience]
            
            reason = result.get('reason', '')
            
            return audience, channel_id, reason
            
        except Exception as e:
            logger.error(f"Error classifying audience: {e}")
            # Fallback to man/3 (business rule)
            return 'man', 3, f'Classification error: {str(e)}'
    
    def generate_image_prompt(self, audience: str, title: str, description: str) -> str:
        """Generate an image prompt based on audience style."""
        if not self.client:
            return f"Illustration for: {title}"
        
        try:
            style_instruction = {
                'child': 'playful, colorful, cartoon/child-friendly illustration style',
                'women': 'elegant, warm, lifestyle illustration style aimed at a female audience',
                'man': 'bold, modern, clean illustration style',
            }.get(audience, 'bold, modern, clean illustration style')
            
            prompt = f"""Write a short, vivid one-sentence image generation prompt for an illustration matching this article.
Audience: {audience}
Title: {title}
Description: {description}

Apply this visual style: {style_instruction}
Return only the prompt text."""

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You write image-generation prompts. Return only the prompt text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=100,
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating image prompt: {e}")
            return f"Illustration for: {title}"
    
    def generate_image(self, prompt: str) -> Optional[str]:
        """
        Generate an image using DALL-E and upload to imgbb.
        Returns image URL or None on failure.
        """
        if not self.client:
            logger.warning("No OpenAI client for image generation")
            return None
        
        try:
            # Generate image with DALL-E
            image_response = self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            
            image_url = image_response.data[0].url
            
            # Download the image from DALL-E
            import httpx
            image_data = httpx.get(image_url).content
            
            # Upload to imgbb (matching n8n workflow)
            imgbb_url = asyncio.run(self._upload_to_imgbb(image_data))
            if imgbb_url:
                return imgbb_url
            
            # Fallback to DALL-E URL if imgbb upload fails
            return image_url
            
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            return None
    
    async def _upload_to_imgbb(self, image_data: bytes) -> Optional[str]:
        """Upload image data to imgbb and return the display URL."""
        imgbb_api_key = settings.imgbb_api_key
        if not imgbb_api_key:
            logger.warning("IMG_BB_API_KEY not set, skipping imgbb upload")
            return None
        
        try:
            import base64
            encoded_image = base64.b64encode(image_data).decode('utf-8')
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.imgbb.com/1/upload",
                    params={"key": imgbb_api_key},
                    data={"image": encoded_image},
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("success") and result.get("data"):
                    display_url = result["data"]["display_url"]
                    logger.info(f"Image uploaded to imgbb: {display_url}")
                    return display_url
                else:
                    logger.error(f"imgbb upload failed: {result}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error uploading to imgbb: {e}")
            return None
    
    def build_caption(self, title: str, description: str) -> str:
        """Build HTML caption for Telegram post (matching n8n's Build Post Record)."""
        def escape_html(v):
            if v is None:
                return ""
            return (str(v)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))
        
        lf = "\n"
        return f"<b>{escape_html(title)}</b>{lf}{lf}{escape_html(description)}"
    
    async def send_to_telegram(self, image_url: str, caption: str, channel_id: int) -> bool:
        """Send photo to Telegram channel."""
        if not settings.telegram_bot_token:
            logger.warning("No Telegram bot token configured")
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                # All channels use the same chat_id from n8n workflow
                url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendPhoto"
                payload = {
                    "chat_id": settings.telegram_channel_chat_id,
                    "photo": image_url,
                    "caption": caption,
                    "parse_mode": "HTML",
                }
                response = await client.post(url, json=payload, timeout=30)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Error sending to Telegram: {e}")
            return False
    
    def update_post_channel(self, post_id: str, channel_id: int) -> bool:
        """Update post's telegram_channel_id."""
        try:
            post = self.db.query(Post).filter(Post.post_id == post_id).first()
            if post:
                post.telegram_channel_id = channel_id
                self.db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating post channel: {e}")
            self.db.rollback()
            return False
    
    def save_category_relationship(self, post_id: str, category_id: int, reason: str) -> bool:
        """Save post category relationship (skip on conflict)."""
        try:
            # Check existing
            existing = self.db.query(PostCategory).filter(
                PostCategory.post_id == post_id,
                PostCategory.category_id == category_id
            ).first()
            
            if existing:
                return False  # Skip on conflict
            
            pc = PostCategory(
                post_id=post_id,
                category_id=category_id,
                reason=reason,
            )
            self.db.add(pc)
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving category relationship: {e}")
            self.db.rollback()
            return False
    
    async def categorize_and_distribute(self) -> Dict[str, int]:
        """
        Run the full categorization and distribution process.
        Returns summary counts.
        """
        stats = {
            'posts_processed': 0,
            'posts_categorized': 0,
            'images_generated': 0,
            'posts_sent': 0,
            'errors': 0,
        }
        
        posts = self.get_uncategorized_posts()
        
        for post in posts:
            try:
                stats['posts_processed'] += 1
                
                # Classify audience
                audience, channel_id, reason = self.classify_audience(post.title, post.description or '')
                
                # Update post channel
                if not self.update_post_channel(post.post_id, channel_id):
                    stats['errors'] += 1
                    continue
                
                stats['posts_categorized'] += 1
                
                # Save category relationship
                self.save_category_relationship(post.post_id, channel_id, reason)
                
                # Generate image prompt
                image_prompt = self.generate_image_prompt(audience, post.title, post.description or '')
                
                # Generate image
                image_url = self.generate_image(image_prompt)
                if image_url:
                    stats['images_generated'] += 1
                    
                    # Build caption
                    caption = self.build_caption(post.title, post.description or '')
                    
                    # Send to Telegram
                    if await self.send_to_telegram(image_url, caption, channel_id):
                        stats['posts_sent'] += 1
                        # Update image_id
                        post.image_id = post.post_id
                        self.db.commit()
                
            except Exception as e:
                logger.error(f"Error processing post {post.post_id}: {e}")
                stats['errors'] += 1
        
        return stats
