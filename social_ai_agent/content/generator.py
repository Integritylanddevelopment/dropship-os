"""
content/generator.py — AI-powered content generation engine
Supports OpenAI GPT-4o and Anthropic Claude. Swap via AI_PROVIDER in .env.
"""

import asyncio
import json
import requests
from typing import Optional
from loguru import logger

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from config import config

# Quinn bridge routes all Anthropic calls (Rule 1: Quinn-First routing)
QUINN_BRIDGE = "http://localhost:8765"


class ContentGenerator:
    """
    AI content generation with platform-specific context injection.
    All prompts are engineered to produce Reddit-native or Pinterest-native output.
    """

    def __init__(self):
        self.provider = config.ai.provider
        self._openai_client = None
        self._anthropic_client = None  # sentinel; Quinn bridge path does not use a client object
        self._setup_clients()

    def _setup_clients(self):
        if self.provider == "anthropic":
            self._anthropic_client = True  # truthy sentinel so generate() gate passes
            logger.info("Anthropic routing through Quinn bridge at " + QUINN_BRIDGE)
        elif self.provider == "openai" and OPENAI_AVAILABLE and config.ai.openai_api_key:
            self._openai_client = AsyncOpenAI(api_key=config.ai.openai_api_key)
            logger.info("OpenAI client initialized")
        else:
            logger.warning(f"AI provider '{self.provider}' not configured — add API key to .env")

    async def generate(self, prompt: str, system: str = None, max_tokens: int = None) -> str:
        """Core generation method — routes to configured provider"""
        if not system:
            system = "You are an expert content strategist who writes native, authentic content."
        if not max_tokens:
            max_tokens = config.ai.max_tokens

        if self.provider == "anthropic" and self._anthropic_client:
            return await self._generate_anthropic(prompt, system, max_tokens)
        elif self.provider == "openai" and self._openai_client:
            return await self._generate_openai(prompt, system, max_tokens)
        else:
            logger.error("No AI client configured. Add your API key to .env")
            return "[AI not configured — add ANTHROPIC_API_KEY or OPENAI_API_KEY to .env]"

    async def _generate_anthropic(self, prompt: str, system: str, max_tokens: int) -> str:
        """
        Route Anthropic request through Quinn bridge (Rule 1: Quinn-First).
        Quinn decides: local Ollama or remote Anthropic based on confidence.
        """
        try:
            loop = asyncio.get_event_loop()

            def call_quinn_bridge():
                response = requests.post(
                    f"{QUINN_BRIDGE}/chat",
                    json={
                        "model": config.ai.model_anthropic,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": max_tokens,
                        "stream": False,
                    },
                    timeout=600,
                )
                response.raise_for_status()
                result = response.json()
                return result.get("content", "")

            return await loop.run_in_executor(None, call_quinn_bridge)
        except Exception as e:
            logger.error(f"Quinn bridge generation error: {e}")
            raise

    async def _generate_openai(self, prompt: str, system: str, max_tokens: int) -> str:
        try:
            response = await self._openai_client.chat.completions.create(
                model=config.ai.model_openai,
                max_tokens=max_tokens,
                temperature=config.ai.temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            raise

    # ─────────────────────────────────────────────
    # REDDIT CONTENT GENERATION
    # ─────────────────────────────────────────────

    async def generate_reddit_post(
        self,
        post_format: str,
        subreddit: str,
        topic: str,
        pain_points: list = None,
        niche: str = None,
        is_promotional: bool = False
    ) -> dict:
        """
        Generate a Reddit-native post in the specified format.
        post_format options: question, experience, case_study, failure, lessons,
                            comparison, myth_bust, what_would_you_do, resource
        """
        niche = niche or config.niche
        pain_context = "\n".join([f"- {p}" for p in (pain_points or [])]) or "general community pain points"

        promo_instruction = ""
        if is_promotional:
            promo_instruction = """
If mentioning a product or service, do it casually and naturally — once, in context.
Never sound like an ad. Frame it as personal experience. No calls to action.
Reddit will destroy you if you sound promotional.
"""
        else:
            promo_instruction = "Do NOT mention any products, services, or links. Pure value only."

        system = """You are a Reddit power user who has been active for 8 years.
You understand Reddit culture deeply. You write authentically, specifically, and helpfully.
You never write content that sounds like marketing copy.
You write like a real person sharing real experience or asking a real question.
Your posts get upvoted because they are specific, useful, and honest."""

        prompt = f"""Write a Reddit post for r/{subreddit} about: {topic}

Post format: {post_format}
Niche/context: {niche}
Community pain points to address: {pain_context}

Format guidelines by type:
- question: Genuine curiosity, specific scenario, invites discussion. Not leading.
- experience: First-person story, specific details, honest outcome, what you learned.
- case_study: Detailed breakdown, real numbers if possible, lessons extracted.
- failure: What went wrong, what you'd do differently, vulnerable and honest.
- lessons: Numbered insights from real experience, specific and actionable.
- comparison: Honest pros/cons of two approaches, personal preference stated.
- myth_bust: Challenge a widely held belief with evidence or experience.
- what_would_you_do: Present a real dilemma, ask community for input.
- resource: Share something genuinely useful, explain why it helped you.

{promo_instruction}

Reddit tone rules:
- No corporate language
- No buzzwords
- First-person, conversational
- Specific details > vague generalities
- Honest > polished
- Useful > impressive

Return JSON format:
{{
  "title": "the post title (under 300 chars, intriguing, specific)",
  "body": "the full post body",
  "format": "{post_format}",
  "estimated_upvote_potential": "high/medium/low",
  "best_time_to_post": "suggested day and time",
  "tags": ["relevant", "tags"]
}}"""

        result = await self.generate(prompt, system)
        try:
            import json
            return json.loads(result)
        except Exception:
            return {"title": "Generated post", "body": result, "format": post_format}

    async def generate_reddit_comment(
        self,
        thread_title: str,
        thread_body: str,
        comment_to_reply_to: str,
        subreddit: str,
        value_angle: str,
        niche: str = None,
        include_soft_mention: bool = False
    ) -> str:
        """
        Generate a Reddit comment that adds genuine value and gets upvoted.
        Comments are the highest-leverage Reddit activity — this gets extra care.
        """
        niche = niche or config.niche

        system = """You are a recognized expert and active community member on Reddit.
Your comments consistently get upvoted because they add real value.
You give specific, actionable answers. You acknowledge other viewpoints.
You never give generic advice. You never sound like you're selling anything.
You write like someone who genuinely wants to help."""

        prompt = f"""Write a high-value Reddit comment for this thread in r/{subreddit}.

Thread title: {thread_title}
Thread content: {thread_body[:500]}
Comment/context you're replying to: {comment_to_reply_to[:300] if comment_to_reply_to else "top-level comment"}
Value angle to deliver: {value_angle}
Your niche expertise: {niche}

{"Optionally mention your experience with a related product/service ONCE if it's genuinely relevant and helpful. Frame it as personal experience, never as a recommendation." if include_soft_mention else "Do NOT mention any products or services."}

Comment requirements:
- Length: 150-600 words
- Start with the actual answer/value, not a preamble
- Use specific examples or numbers if possible
- Acknowledge the original question or comment directly
- Add a perspective others haven't mentioned
- End naturally, not with a call to action
- Sound like a real person, not a content writer

Write only the comment text, no JSON, no formatting labels."""

        return await self.generate(prompt, system)

    async def analyze_subreddit_for_strategy(
        self,
        subreddit_name: str,
        sample_posts: list,
        niche: str = None
    ) -> dict:
        """Analyze subreddit posts and return strategic scoring + recommendations"""
        niche = niche or config.niche

        post_samples = "\n---\n".join([
            f"Title: {p.get('title', '')}\nScore: {p.get('score', 0)}\nComments: {p.get('num_comments', 0)}\nBody preview: {str(p.get('selftext', ''))[:200]}"
            for p in sample_posts[:20]
        ])

        system = "You are a Reddit growth strategist with deep knowledge of community dynamics and content performance."

        prompt = f"""Analyze r/{subreddit_name} for organic growth strategy in the {niche} niche.

Sample posts from this subreddit:
{post_samples}

Return a complete strategic analysis as JSON:
{{
  "subreddit": "{subreddit_name}",
  "audience_profile": "description of who is here",
  "dominant_post_types": ["list of formats that perform well"],
  "key_pain_points": ["top 5 pain points expressed"],
  "buyer_signals": ["signals that suggest purchase intent"],
  "best_content_angles": ["top 5 content angles for {niche}"],
  "best_comment_angles": ["top 3 comment value plays"],
  "promotion_tolerance": "strict/moderate/lenient",
  "moderation_strictness": 5,
  "scores": {{
    "audience_quality": 7,
    "pain_intensity": 6,
    "relevance": 8,
    "post_opportunity": 7,
    "comment_opportunity": 9,
    "promotion_tolerance": 3,
    "lead_potential": 6,
    "authority_potential": 7,
    "ease_of_entry": 6,
    "overall": 7
  }},
  "tier": "research|credibility|engagement|buyer_intent",
  "fast_wins": ["quick opportunities"],
  "risks": ["things that could get you banned or downvoted"],
  "recommended_approach": "tactical summary"
}}"""

        result = await self.generate(prompt, system, max_tokens=3000)
        try:
            import json
            return json.loads(result)
        except Exception:
            return {"subreddit": subreddit_name, "raw_analysis": result}

    # ─────────────────────────────────────────────
    # PINTEREST CONTENT GENERATION
    # ─────────────────────────────────────────────

    async def generate_pin_content(
        self,
        topic: str,
        keyword: str,
        pin_format: str,
        destination_url: str,
        funnel_stage: str,
        niche: str = None
    ) -> dict:
        """
        Generate a complete pin: title, description, keywords, CTA.
        pin_format: standard, idea, product, comparison, checklist, tutorial, problem_solution
        funnel_stage: awareness, consideration, conversion
        """
        niche = niche or config.niche

        system = """You are a Pinterest SEO and content expert.
You understand that Pinterest is a visual search engine, not a social network.
You write pin titles and descriptions that rank in search AND drive clicks.
You balance search optimization with human curiosity.
You know that saves beat likes and clicks beat impressions."""

        prompt = f"""Create Pinterest pin content for:
Topic: {topic}
Primary keyword: {keyword}
Pin format: {pin_format}
Destination URL: {destination_url}
Funnel stage: {funnel_stage}
Niche: {niche}

Pin format guidelines:
- standard: Clean hook + value + keyword. Drives blog/landing page clicks.
- idea: Step-by-step or tips format. Gets saves. Drives profile/website visits.
- product: Feature + benefit + social proof. Drives purchase clicks.
- comparison: X vs Y structure. High saves, high clicks from researchers.
- checklist: Numbered list format. Extremely saveable. Authority builder.
- tutorial: How-to structure. Gets saves. Drives traffic to full tutorial.
- problem_solution: Pain → solution structure. Conversion-focused.

Return JSON:
{{
  "title": "pin title (under 100 chars, keyword-first, curiosity-driven)",
  "description": "pin description (200-500 chars, keyword-rich, human-readable, ends with soft CTA)",
  "primary_keyword": "{keyword}",
  "secondary_keywords": ["5-7 related keywords"],
  "hashtags": ["3-5 relevant hashtags"],
  "text_overlay": "short text to put ON the image (under 12 words, punchy)",
  "image_direction": "brief description of what the image should show",
  "cta": "soft call to action phrase",
  "save_hook": "why someone would save this pin",
  "click_hook": "why someone would click through",
  "estimated_performance": "high/medium/low saves and clicks potential"
}}"""

        result = await self.generate(prompt, system)
        try:
            import json
            return json.loads(result)
        except Exception:
            return {"title": topic, "description": result, "primary_keyword": keyword}

    async def generate_keyword_clusters(self, niche: str, products: list = None) -> dict:
        """Generate a complete Pinterest keyword strategy"""
        products_str = ", ".join(products) if products else "general products"

        system = "You are a Pinterest SEO expert who builds keyword strategies for ecommerce and content creators."

        prompt = f"""Build a complete Pinterest keyword strategy for:
Niche: {niche}
Products/services: {products_str}

Return JSON with keyword clusters:
{{
  "core_clusters": [
    {{
      "cluster_name": "cluster topic",
      "primary_keyword": "main keyword",
      "long_tail_keywords": ["8-10 long tail variations"],
      "intent_type": "inspiration|problem|comparison|buyer",
      "search_volume": "high|medium|low",
      "competition": "high|medium|low",
      "priority": 8
    }}
  ],
  "seasonal_keywords": [
    {{
      "keyword": "seasonal keyword",
      "season": "Q1|Q2|Q3|Q4|holiday|spring|etc",
      "lead_days": 45
    }}
  ],
  "buyer_intent_keywords": ["keywords that signal purchase intent"],
  "problem_aware_keywords": ["keywords showing a pain point"],
  "content_calendar_themes": ["monthly theme ideas based on keywords"]
}}

Generate at least 8 core clusters and 20 total unique keywords."""

        result = await self.generate(prompt, system, max_tokens=3000)
        try:
            import json
            return json.loads(result)
        except Exception:
            return {"raw": result}

    async def generate_board_strategy(self, niche: str, products: list = None) -> dict:
        """Design a complete Pinterest board structure"""
        products_str = ", ".join(products) if products else "general products"

        system = "You are a Pinterest account strategist who builds board structures that rank in search and support topical authority."

        prompt = f"""Design a complete Pinterest board strategy for:
Niche: {niche}
Products: {products_str}

Return JSON:
{{
  "boards": [
    {{
      "name": "board name (keyword-optimized)",
      "description": "board description (150-200 chars, keyword-rich)",
      "primary_keyword": "main keyword for this board",
      "board_type": "core|supporting|seasonal|niche",
      "pin_topics": ["5-8 types of pins for this board"],
      "audience_intent": "what this board serves",
      "priority": 8
    }}
  ],
  "board_architecture_notes": "how boards relate to each other",
  "total_boards_recommended": 20,
  "first_10_to_create": ["prioritized list"]
}}

Design 20 boards total."""

        result = await self.generate(prompt, system, max_tokens=3000)
        try:
            import json
            return json.loads(result)
        except Exception:
            return {"raw": result}

    async def extract_market_research(self, posts_and_comments: list, platform: str) -> dict:
        """Extract market intelligence from Reddit posts/Pinterest comments"""

        raw_content = "\n---\n".join([
            str(item)[:300] for item in posts_and_comments[:30]
        ])

        system = "You are a market research analyst extracting buyer psychology insights from social content."

        prompt = f"""Extract market intelligence from these {platform} posts/comments:

{raw_content}

Return JSON:
{{
  "pain_points": [
    {{
      "pain": "specific pain point",
      "frequency": "high|medium|low",
      "emotional_intensity": 8,
      "exact_quote": "quote from the content if available"
    }}
  ],
  "customer_language": ["exact phrases customers use to describe their problem/desire"],
  "buying_objections": ["objections to purchasing a solution"],
  "emotional_triggers": ["emotional drivers — fear, desire, frustration, hope"],
  "competitor_mentions": ["competitors mentioned and sentiment"],
  "feature_requests": ["things people want that don't exist yet"],
  "content_angles": ["content ideas suggested by this research"],
  "ad_copy_hooks": ["hooks that could work in ad copy"],
  "landing_page_language": ["phrases to use on product pages"]
}}"""

        result = await self.generate(prompt, system, max_tokens=3000)
        try:
            import json
            return json.loads(result)
        except Exception:
            return {"raw": result}


# Singleton
generator = ContentGenerator()
