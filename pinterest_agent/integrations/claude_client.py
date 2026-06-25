"""
Pinterest AI Agent — Quinn Bridge Client
Powers all AI content generation: titles, descriptions, board copy, strategies.
Routes through Quinn bridge (Rule 1: Quinn-First routing).
"""
import os
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"))
except ImportError:
    pass
import requests
import json
from typing import Any

# Quinn bridge routes all LLM calls (Rule 1: Quinn-First)
QUINN_BRIDGE = "http://localhost:8765"


SYSTEM_PROMPT = """You are an expert Pinterest content strategist and SEO copywriter
specializing in drop shipping and e-commerce. You understand Pinterest as a visual
search engine — not a social platform. You write pin titles and descriptions that:

1. Target exact search phrases people type into Pinterest
2. Lead with the most important keyword naturally
3. Create curiosity or clarity (not both — Pinterest rewards clarity)
4. Match buyer intent for the target audience
5. Drive saves AND clicks through specific, useful promises
6. Never use clickbait, keyword stuffing, or misleading claims

You think like a search-driven visual strategist. You write copy that is:
- Specific (not vague)
- Search-indexed (keyword-first)
- Value-clear (obvious benefit)
- Action-oriented (drives the next step)
- Pinterest-native (not Instagram, not Google, not Amazon)

When generating content, always output clean JSON as specified in each prompt."""


class ClaudeClient:
    def __init__(self, bridge_url: str = None, model: str = None):
        if model is None:
            model = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")
        self.model = model
        self.bridge_url = bridge_url or QUINN_BRIDGE

    def _call(self, prompt: str, max_tokens: int = 2000, temperature: float = 0.7) -> str:
        """
        Call Quinn bridge instead of Anthropic directly (Rule 1: Quinn-First).
        Quinn routes to Anthropic or local Ollama based on confidence.
        """
        response = requests.post(
            f"{self.bridge_url}/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()
        result = response.json()
        return result.get("content", "").strip()

    def _call_json(self, prompt: str, max_tokens: int = 3000) -> Any:
        """Call Claude and parse the JSON response."""
        response = self._call(prompt + "\n\nRespond ONLY with valid JSON. No markdown, no explanation.", max_tokens)
        # Strip markdown code blocks if present
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        return json.loads(response)

    # =========================================================
    # PIN CONTENT GENERATION
    # =========================================================
    def generate_pin_variations(
        self,
        product_name: str,
        product_description: str,
        target_url: str,
        primary_keyword: str,
        pin_count: int = 5,
        niche: str = "home & lifestyle",
        pin_types: list[str] = None,
    ) -> list[dict]:
        """
        Generate multiple unique pin variations for a single product.
        Returns list of {title, description, pin_type, keyword_primary,
                          content_angle, image_guidance, landing_page_type}
        """
        if pin_types is None:
            pin_types = ["product_feature", "problem_solution", "roundup", "educational", "seasonal"]

        prompt = f"""Generate {pin_count} unique Pinterest pin variations for this product:

PRODUCT: {product_name}
DESCRIPTION: {product_description}
TARGET URL: {target_url}
PRIMARY KEYWORD: {primary_keyword}
NICHE: {niche}
PIN TYPES TO USE: {', '.join(pin_types)}

For each pin variation, create:
1. A Pinterest-optimized title (max 100 chars, lead with keyword naturally)
2. A Pinterest-optimized description (max 500 chars, 3-5 keywords embedded naturally)
3. Pin type from the list provided
4. Primary keyword used
5. Content angle (what makes this pin unique)
6. Image guidance (what the pin image should show)
7. Landing page type recommendation

Each pin must have a completely different angle, title structure, and visual approach.
Cover angles: benefit-led, problem-solution, price-point, seasonal, identity/aspiration.

Return JSON array:
[
  {{
    "title": "pin title here",
    "description": "pin description here with keywords woven in naturally",
    "pin_type": "product_feature",
    "keyword_primary": "main keyword",
    "content_angle": "benefit-focused | problem-solution | price-point | seasonal | identity",
    "image_guidance": "specific visual direction for the pin image",
    "landing_page_type": "product_page | blog_post | lead_magnet | category_page"
  }}
]"""
        return self._call_json(prompt)

    def generate_pin_title(
        self,
        product: str,
        keyword: str,
        angle: str = "benefit",
        pin_type: str = "product_feature",
    ) -> str:
        """Generate a single optimized pin title."""
        prompt = f"""Write ONE Pinterest pin title for:
Product: {product}
Primary Keyword: {keyword}
Angle: {angle} (benefit | problem_solution | price_point | seasonal | list_format)
Pin Type: {pin_type}

Rules:
- Max 100 characters
- Lead with or near the keyword naturally
- Be specific, not vague
- Create curiosity OR clarity (not both)
- No clickbait, no all-caps, no punctuation spam

Return ONLY the title text, nothing else."""
        return self._call(prompt, max_tokens=100)

    def generate_pin_description(
        self,
        title: str,
        product: str,
        primary_keyword: str,
        secondary_keywords: list[str],
        url: str,
        niche: str,
    ) -> str:
        """Generate an SEO-optimized Pinterest pin description."""
        prompt = f"""Write a Pinterest pin description for:
Title: {title}
Product: {product}
Primary Keyword: {primary_keyword}
Secondary Keywords: {', '.join(secondary_keywords)}
Target URL: {url}
Niche: {niche}

Rules:
- Max 500 characters
- Include primary keyword in first sentence
- Weave in 2-3 secondary keywords naturally
- Be specific about who this is for and what they get
- Include a subtle call to action (tap to see more, save for later, visit link)
- No hashtags (Pinterest doesn't use them like Instagram)
- Write in second person (you/your)

Return ONLY the description text."""
        return self._call(prompt, max_tokens=300)

    # =========================================================
    # BOARD CONTENT
    # =========================================================
    def generate_board_structure(
        self,
        niche: str,
        business_type: str = "drop shipping",
        website_url: str = "",
        num_boards: int = 12,
    ) -> list[dict]:
        """
        Generate complete board structure for a Pinterest account.
        Returns list of board configs with names, descriptions, keywords.
        """
        prompt = f"""Design a complete Pinterest board architecture for:
Business Type: {business_type}
Niche: {niche}
Website: {website_url}
Number of Boards: {num_boards}

Create boards that:
1. Are named with real Pinterest search phrases (not clever names)
2. Have SEO-rich descriptions with natural keyword clusters
3. Cover different product categories AND content types (educational, seasonal, etc.)
4. Build topical authority in the niche
5. Are ordered by priority (highest traffic potential first)

Return JSON array:
[
  {{
    "name": "board name here (search phrase people type)",
    "description": "SEO-rich board description, 150-200 chars, with keyword clusters",
    "keyword_cluster": "primary | secondary | seasonal | educational",
    "priority": 1,
    "content_themes": ["theme1", "theme2", "theme3"],
    "target_audience": "who saves from this board",
    "traffic_type": "buyer_intent | research | inspiration | problem_solving",
    "best_pin_types": ["product_feature", "roundup", "educational"]
  }}
]"""
        return self._call_json(prompt, max_tokens=4000)

    def generate_board_description(
        self,
        board_name: str,
        keywords: list[str],
        niche: str,
    ) -> str:
        """Generate an SEO-optimized board description."""
        prompt = f"""Write a Pinterest board description for:
Board Name: {board_name}
Niche: {niche}
Keywords to include: {', '.join(keywords)}

Rules:
- 150-200 characters
- Include 3-5 keywords naturally
- Describe what someone will find on this board
- Write for search discovery, not social engagement
- No hashtags, no emojis

Return ONLY the description text."""
        return self._call(prompt, max_tokens=200)

    # =========================================================
    # KEYWORD RESEARCH
    # =========================================================
    def expand_keyword_cluster(
        self,
        seed_keyword: str,
        niche: str,
        intent_types: list[str] = None,
    ) -> list[dict]:
        """
        Expand a seed keyword into a full cluster of Pinterest-optimized keywords.
        """
        if intent_types is None:
            intent_types = ["informational", "problem_aware", "buyer_intent", "seasonal", "comparison"]

        prompt = f"""Expand this seed keyword into a Pinterest keyword cluster for drop shipping:
Seed Keyword: {seed_keyword}
Niche: {niche}

Generate 20-25 keyword variations covering:
- Long-tail variations (3-5 words)
- Problem-aware phrases
- Buyer-intent phrases
- Seasonal variations
- Comparison keywords
- Price-point keywords
- "Best" and "top" variations
- "Ideas" and "inspiration" variations

Return JSON array:
[
  {{
    "keyword": "exact keyword phrase",
    "intent_type": "informational | problem_aware | buyer_intent | seasonal | comparison",
    "buyer_intent_score": 7,
    "save_potential_score": 8,
    "click_potential_score": 6,
    "traffic_potential_score": 7,
    "competition": "low | medium | high",
    "seasonal": false,
    "evergreen": true,
    "best_pin_type": "roundup | product_feature | educational | problem_solution"
  }}
]"""
        return self._call_json(prompt, max_tokens=3000)

    # =========================================================
    # CONTENT STRATEGY
    # =========================================================
    def score_opportunity(
        self,
        niche: str,
        topic: str,
        context: str = "",
    ) -> dict:
        """Score a content opportunity using the 10-point framework."""
        prompt = f"""Score this Pinterest drop shipping opportunity:
Niche: {niche}
Topic/Product: {topic}
Context: {context}

Score each dimension 1-10:
- traffic_potential: search volume and Pinterest distribution potential
- buyer_intent: likelihood visitors are ready to buy
- save_potential: likelihood of saves (saves = free redistribution)
- click_potential: likelihood of outbound clicks
- conversion_quality: quality of traffic for email/purchase conversion
- keyword_opportunity: keyword gap and long-tail opportunity
- creative_fit: visual/creative potential on Pinterest
- competition_level: INVERTED (10 = low competition = better)
- evergreen_value: how long content stays relevant

Calculate overall_score as weighted average.
Add recommended_action with specific next step.

Return JSON:
{{
  "niche": "{niche}",
  "topic": "{topic}",
  "traffic_potential": 7,
  "buyer_intent": 8,
  "save_potential": 9,
  "click_potential": 7,
  "conversion_quality": 8,
  "keyword_opportunity": 8,
  "creative_fit": 9,
  "competition_level": 7,
  "evergreen_value": 8,
  "overall_score": 7.9,
  "recommended_action": "specific action to take",
  "priority_rank": null
}}"""
        return self._call_json(prompt)

    def generate_weekly_content_plan(
        self,
        niche: str,
        boards: list[dict],
        keywords: list[str],
        products: list[dict] = None,
        pin_count: int = 15,
    ) -> list[dict]:
        """Generate a full weekly content plan with pin specs."""
        board_summary = json.dumps([{"name": b.get("name"), "id": b.get("id")} for b in boards[:10]])
        kw_summary = ", ".join(keywords[:15])

        prompt = f"""Create a weekly Pinterest content plan for a drop shipping business:
Niche: {niche}
Available Boards: {board_summary}
Top Keywords: {kw_summary}
Target Pin Count: {pin_count}

Generate a balanced weekly plan covering:
- Monday (2-3 pins): Product feature pins — high buyer intent
- Tuesday (2-3 pins): Educational / how-to pins — top-of-funnel
- Wednesday (2-3 pins): Roundup / list pins — high save volume
- Thursday (2-3 pins): Problem-solution pins — buyer intent
- Friday (2-3 pins): Lifestyle / aspirational pins — save volume
- Saturday (1-2 pins): Seasonal or trending pins
- Sunday (1-2 pins): Lead magnet pins — email capture

For each pin include:
- day: "Monday"
- title: optimized title
- description: full description
- board_name: which board it goes to
- pin_type: the type
- keyword_primary: main keyword
- content_angle: what makes it unique
- image_guidance: visual direction
- landing_page_type: where to send traffic
- priority: 1-10

Return JSON array of {pin_count} pins ordered by day."""
        return self._call_json(prompt, max_tokens=5000)

    def generate_seasonal_calendar(
        self,
        niche: str,
        year: int = 2026,
    ) -> list[dict]:
        """Generate a full seasonal content calendar with lead times."""
        prompt = f"""Create a Pinterest seasonal content calendar for {year} for:
Niche: {niche}
Business Type: Drop shipping e-commerce

For each major seasonal event, include:
- season: season name
- event: specific event (e.g., "Valentine's Day", "Back to School")
- target_date: actual date (YYYY-MM-DD)
- publish_by: when to start publishing (45-90 days before event)
- lead_days: days of lead time
- content_themes: list of 3-5 content themes for this event
- keyword_focus: list of 3-5 target keywords
- board_targets: which board types to target
- pin_types: which pin types work best for this event
- notes: any strategic notes

Include ALL major events: New Year, Valentine's, Easter, Mother's Day, Memorial Day,
Father's Day, 4th of July, Back to School, Labor Day, Halloween, Thanksgiving,
Black Friday/Cyber Monday, Christmas, New Year's Eve.

Return JSON array ordered by target_date."""
        return self._call_json(prompt, max_tokens=4000)

    def generate_lead_magnet(
        self,
        niche: str,
        audience: str,
        product_category: str,
    ) -> dict:
        """Generate a complete lead magnet concept optimized for Pinterest traffic."""
        prompt = f"""Design a Pinterest-optimized lead magnet for:
Niche: {niche}
Audience: {audience}
Product Category: {product_category}

Create a lead magnet that:
1. Matches what Pinterest users in this niche would save/click
2. Bridges naturally to product purchases
3. Has a clear, specific value promise
4. Can be delivered digitally (PDF, checklist, guide)

Return JSON:
{{
  "name": "lead magnet name",
  "type": "checklist | guide | toolkit | swipe_file | planner",
  "headline": "opt-in page headline",
  "subheadline": "opt-in page subheadline",
  "value_promise": "specific transformation or result",
  "content_outline": ["section 1", "section 2", "section 3", "section 4", "section 5"],
  "pin_title": "Pinterest pin title to promote this lead magnet",
  "pin_description": "Pinterest pin description",
  "image_guidance": "what the pin image should show",
  "keyword_primary": "main keyword for the pin",
  "email_sequence_hook": "first email subject line to send after opt-in",
  "product_bridge": "how this leads naturally to product recommendations"
}}"""
        return self._call_json(prompt)

    def analyze_competitor_strategy(
        self,
        competitor_data: dict,
        your_niche: str,
    ) -> dict:
        """Analyze competitor Pinterest data and extract actionable insights."""
        prompt = f"""Analyze this Pinterest competitor data and extract actionable strategy:

Competitor Data: {json.dumps(competitor_data)}
Your Niche: {your_niche}

Identify:
1. Content themes that are working for them
2. Keyword patterns in their high-performing pin titles
3. Board structure gaps you can exploit
4. Content angles they're missing
5. Visual style patterns
6. Timing patterns if visible

Return JSON:
{{
  "working_themes": ["theme1", "theme2"],
  "keyword_patterns": ["pattern1", "pattern2"],
  "content_gaps": ["gap1", "gap2"],
  "board_opportunities": ["opportunity1", "opportunity2"],
  "visual_patterns": "description of visual style",
  "recommended_actions": ["action1", "action2", "action3"]
}}"""
        return self._call_json(prompt)

    def generate_blog_outline(
        self,
        topic: str,
        primary_keyword: str,
        secondary_keywords: list[str],
        pin_count: int = 8,
    ) -> dict:
        """Generate a blog post outline optimized for Pinterest traffic and products."""
        prompt = f"""Create a blog post outline optimized for Pinterest traffic and drop shipping conversions:

Topic: {topic}
Primary Keyword: {primary_keyword}
Secondary Keywords: {', '.join(secondary_keywords)}
Target Pin Count (pins to generate from this post): {pin_count}

The post should:
1. Rank for the primary keyword on Pinterest search
2. Feature 5-10 products naturally embedded
3. Generate {pin_count} unique pin angles
4. Include an email capture opportunity (lead magnet)
5. Have high save potential (checklist, guide, or roundup format)

Return JSON:
{{
  "title": "blog post title (Pinterest SEO optimized)",
  "meta_description": "160 char meta description",
  "intro_hook": "opening paragraph hook",
  "sections": [
    {{"heading": "H2 heading", "content_type": "list|paragraph|comparison", "product_opportunity": true}}
  ],
  "product_slots": 8,
  "lead_magnet_placement": "where to embed the opt-in",
  "pin_angles": ["angle1", "angle2"],
  "estimated_read_time": "5 min",
  "content_upgrade_idea": "specific bonus to offer"
}}"""
        return self._call_json(prompt, max_tokens=3000)

    def audit_existing_board(
        self,
        board_name: str,
        board_description: str,
        pin_titles: list[str],
    ) -> dict:
        """Audit an existing Pinterest board and provide optimization recommendations."""
        prompt = f"""Audit this Pinterest board for SEO and performance optimization:

Board Name: {board_name}
Current Description: {board_description}
Sample Pin Titles (up to 10): {json.dumps(pin_titles[:10])}

Evaluate:
1. Board name SEO (is it a real search phrase?)
2. Description keyword density and quality
3. Pin title patterns (keyword alignment, specificity)
4. Content coherence (is it topically focused?)
5. Improvement opportunities

Return JSON:
{{
  "name_score": 7,
  "description_score": 6,
  "content_coherence_score": 8,
  "overall_score": 7,
  "name_recommendation": "optimized board name",
  "description_recommendation": "optimized description",
  "issues": ["issue1", "issue2"],
  "quick_wins": ["win1", "win2"],
  "estimated_improvement": "description of expected improvement"
}}"""
        return self._call_json(prompt)
