"""
api_stubs/reddit_api.py — Official Reddit API via PRAW
STUB: Ready to activate once you add Reddit credentials to .env

To activate:
1. Go to https://www.reddit.com/prefs/apps
2. Click "create another app"
3. Choose "script"
4. Add credentials to your .env file
5. Change REDDIT_MODE=api in .env

All methods match the interface of RedditBrowserAutomation so you can swap seamlessly.
"""

from loguru import logger
from typing import Optional
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config

try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False


class RedditAPI:
    """
    Official Reddit API wrapper via PRAW.
    Much faster and more reliable than browser automation.
    Same interface as RedditBrowserAutomation.
    """

    def __init__(self):
        self._reddit = None
        self._setup()

    def _setup(self):
        if not PRAW_AVAILABLE:
            logger.warning("PRAW not installed. Run: pip install praw")
            return

        if not config.reddit_api.is_configured:
            logger.warning("Reddit API not configured. Add credentials to .env")
            return

        try:
            self._reddit = praw.Reddit(
                client_id=config.reddit_api.client_id,
                client_secret=config.reddit_api.client_secret,
                username=config.reddit_api.username,
                password=config.reddit_api.password,
                user_agent=config.reddit_api.user_agent,
            )
            logger.info(f"Reddit API initialized as u/{config.reddit_api.username}")
        except Exception as e:
            logger.error(f"Reddit API setup failed: {e}")

    def _check_ready(self) -> bool:
        if not self._reddit:
            logger.error("Reddit API not initialized. Check credentials in .env")
            return False
        return True

    # ─────────────────────────────────────────────
    # READ (these work without auth for public data)
    # ─────────────────────────────────────────────

    async def get_subreddit_posts(self, subreddit: str, sort: str = "hot", limit: int = 50) -> list:
        """Get posts from a subreddit via API"""
        if not self._check_ready():
            return []

        try:
            sub = self._reddit.subreddit(subreddit)
            feed = getattr(sub, sort)(limit=limit)
            posts = []
            for post in feed:
                posts.append({
                    "id": post.id,
                    "title": post.title,
                    "selftext": post.selftext[:1000],
                    "score": post.score,
                    "upvote_ratio": post.upvote_ratio,
                    "num_comments": post.num_comments,
                    "url": post.url,
                    "permalink": post.permalink,
                    "author": str(post.author) if post.author else "[deleted]",
                    "created_utc": post.created_utc,
                    "is_self": post.is_self,
                })
            return posts
        except Exception as e:
            logger.error(f"API get posts failed: {e}")
            return []

    async def search_subreddit(self, subreddit: str, query: str, limit: int = 25) -> list:
        """Search within a subreddit"""
        if not self._check_ready():
            return []
        try:
            sub = self._reddit.subreddit(subreddit)
            results = []
            for post in sub.search(query, limit=limit):
                results.append({
                    "id": post.id,
                    "title": post.title,
                    "selftext": post.selftext[:500],
                    "score": post.score,
                    "permalink": post.permalink,
                })
            return results
        except Exception as e:
            logger.error(f"API search failed: {e}")
            return []

    async def get_post_comments(self, post_id: str, limit: int = 20) -> list:
        """Get comments from a post"""
        if not self._check_ready():
            return []
        try:
            submission = self._reddit.submission(id=post_id)
            submission.comments.replace_more(limit=0)
            comments = []
            for comment in submission.comments[:limit]:
                comments.append({
                    "id": comment.id,
                    "body": comment.body[:500],
                    "score": comment.score,
                    "author": str(comment.author) if comment.author else "[deleted]",
                })
            return comments
        except Exception as e:
            logger.error(f"API get comments failed: {e}")
            return []

    # ─────────────────────────────────────────────
    # WRITE (requires auth)
    # ─────────────────────────────────────────────

    async def submit_post(self, subreddit: str, title: str, body: str) -> Optional[str]:
        """Submit a text post via API"""
        if not self._check_ready():
            return None
        try:
            sub = self._reddit.subreddit(subreddit)
            post = sub.submit(title=title, selftext=body)
            url = f"https://www.reddit.com{post.permalink}"
            logger.info(f"✅ Post submitted via API: {url}")
            return url
        except Exception as e:
            logger.error(f"API post submission failed: {e}")
            return None

    async def submit_comment(self, post_id: str, comment_text: str) -> Optional[str]:
        """Comment on a post via API"""
        if not self._check_ready():
            return None
        try:
            submission = self._reddit.submission(id=post_id)
            comment = submission.reply(comment_text)
            logger.info(f"✅ Comment submitted via API: {comment.id}")
            return comment.id
        except Exception as e:
            logger.error(f"API comment failed: {e}")
            return None

    async def upvote(self, post_id: str) -> bool:
        """Upvote a post"""
        if not self._check_ready():
            return False
        try:
            post = self._reddit.submission(id=post_id)
            post.upvote()
            return True
        except Exception as e:
            logger.error(f"Upvote failed: {e}")
            return False

    async def get_karma(self) -> dict:
        """Get current account karma"""
        if not self._check_ready():
            return {}
        try:
            me = self._reddit.user.me()
            return {
                "post_karma": me.link_karma,
                "comment_karma": me.comment_karma,
                "total": me.link_karma + me.comment_karma,
            }
        except Exception as e:
            logger.error(f"Karma check failed: {e}")
            return {}

    async def get_my_posts(self, limit: int = 25) -> list:
        """Get your own posts"""
        if not self._check_ready():
            return []
        try:
            me = self._reddit.user.me()
            posts = []
            for post in me.submissions.new(limit=limit):
                posts.append({
                    "id": post.id,
                    "title": post.title,
                    "score": post.score,
                    "num_comments": post.num_comments,
                    "subreddit": post.subreddit.display_name,
                    "permalink": post.permalink,
                })
            return posts
        except Exception as e:
            logger.error(f"Get my posts failed: {e}")
            return []
