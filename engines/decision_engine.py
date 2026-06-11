#!/usr/bin/env python3
"""
Decision Engine — Product Scoring & Ranking
============================================

Core algorithm for evaluating which products to pursue.

Scores products based on:
- Supplier cost + margin potential
- Niche alignment + search volume
- Competition level + trend signal
- Review sentiment + conversion probability

Used by ShipStack Engine (/api/decide).
Routes to Quinn bridge for LLM-assisted analysis.
"""

import os
import json
import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

QUINN_ENDPOINT = os.getenv("QUINN_ENDPOINT", "http://localhost:8765")


@dataclass
class Product:
    """Product model."""
    id: str
    title: str
    price: float
    supplier: str
    reviews: int
    rating: float
    niche: str
    description: str = ""


@dataclass
class Decision:
    """Decision output."""
    product_id: str
    score: float
    rationale: str
    margin_potential: float
    competition_level: str
    trend_signal: str


class DecisionEngine:
    """
    Evaluates products and ranks them by profitability + viability.
    """
    
    def __init__(self):
        self.min_rating = 4.0
        self.min_reviews = 10
        self.target_margin = 0.50  # 50% markup
        self.cost_per_unit_limit = 15.00
    
    def score_cost_margin(self, product: Product, target_cost: float = 8.0) -> Tuple[float, float]:
        """
        Score: cost + margin potential.
        
        Returns: (score, margin_potential)
        """
        cost = product.price
        
        # Margin calculation: retail_price = cost / (1 - margin_percent)
        # If cost=$5 and we want 50% margin: retail=$10
        retail_price = cost / (1 - self.target_margin)
        margin_potential = (retail_price - cost) / retail_price
        
        if cost > self.cost_per_unit_limit:
            return 0.0, margin_potential  # Too expensive
        
        if cost <= 3.00:
            score = 1.0  # Ideal
        elif cost <= target_cost:
            score = 0.9
        elif cost <= 12.00:
            score = 0.7
        else:
            score = 0.5
        
        return score, margin_potential
    
    def score_reviews(self, product: Product) -> float:
        """
        Score: review count + rating.
        
        High review count = social proof.
        High rating = product quality.
        """
        if product.rating < self.min_rating:
            return 0.0  # Too risky
        
        if product.reviews < self.min_reviews:
            return 0.3  # Unproven
        
        # Sigmoid: more reviews = higher confidence
        # 50 reviews = 0.7, 100 reviews = 0.85, 500+ reviews = 0.95
        review_score = min(1.0, product.reviews / 500.0)
        
        # Rating: 4.0-4.3 = 0.6, 4.3-4.7 = 0.8, 4.7+ = 0.95
        rating_score = (product.rating - 4.0) / (5.0 - 4.0) if product.rating >= 4.0 else 0.0
        
        return (review_score * 0.6) + (rating_score * 0.4)
    
    def score_niche(self, product: Product, target_niches: List[str] = None) -> float:
        """
        Score: niche relevance + trend signal.
        
        Exact niche match = 1.0.
        Related niche = 0.7.
        Random niche = 0.3.
        """
        if target_niches is None:
            target_niches = ["pet accessories", "home kitchen", "fitness tools", "posture corrector"]
        
        product_niche = product.niche.lower()
        
        # Exact match
        if product_niche in [n.lower() for n in target_niches]:
            return 1.0
        
        # Partial match (e.g., "pet collar" contains "pet")
        for target in target_niches:
            if target.lower() in product_niche or product_niche in target.lower():
                return 0.7
        
        # No match
        return 0.3
    
    def score_competition(self, product: Product) -> Tuple[float, str]:
        """
        Score: competition level (estimated from reviews).
        
        Returns: (score, level_string)
        """
        # Heuristic: more reviews = more competition
        if product.reviews < 50:
            return 0.95, "low"  # Underserved
        elif product.reviews < 200:
            return 0.7, "moderate"
        elif product.reviews < 1000:
            return 0.5, "high"
        else:
            return 0.2, "very_high"  # Saturated
    
    def decide(self, product: Product, target_niches: List[str] = None) -> Decision:
        """
        Evaluate a single product.
        
        Returns: Decision with score + rationale.
        """
        # Score each dimension
        cost_score, margin_pot = self.score_cost_margin(product)
        review_score = self.score_reviews(product)
        niche_score = self.score_niche(product, target_niches)
        comp_score, comp_level = self.score_competition(product)
        
        # Weighted sum (cost + reviews are most important)
        overall_score = (
            cost_score * 0.30 +
            review_score * 0.35 +
            niche_score * 0.20 +
            comp_score * 0.15
        )
        
        # Determine trend signal
        if niche_score >= 0.9 and comp_score >= 0.7:
            trend = "hot"
        elif niche_score >= 0.7 and review_score >= 0.7:
            trend = "growing"
        elif comp_level == "very_high":
            trend = "saturated"
        else:
            trend = "steady"
        
        # Build rationale
        rationale = f"Cost: {cost_score:.0%} | Reviews: {review_score:.0%} | Niche: {niche_score:.0%} | Competition: {comp_score:.0%}"
        
        return Decision(
            product_id=product.id,
            score=overall_score,
            rationale=rationale,
            margin_potential=margin_pot,
            competition_level=comp_level,
            trend_signal=trend,
        )
    
    def rank(self, products: List[Product], target_niches: List[str] = None) -> List[Decision]:
        """
        Rank a list of products.
        
        Returns: sorted list (highest score first).
        """
        decisions = [self.decide(p, target_niches) for p in products]
        return sorted(decisions, key=lambda d: d.score, reverse=True)


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    engine = DecisionEngine()
    
    test_products = [
        Product(id="p1", title="Pet Collar", price=4.50, supplier="zendrop", reviews=150, rating=4.8, niche="pet accessories"),
        Product(id="p2", title="Kitchen Gadget", price=6.00, supplier="autods", reviews=50, rating=4.2, niche="home kitchen"),
        Product(id="p3", title="Gaming Mouse", price=12.00, supplier="aliexpress", reviews=800, rating=3.9, niche="electronics"),
        Product(id="p4", title="Yoga Mat", price=8.50, supplier="zendrop", reviews=200, rating=4.6, niche="fitness tools"),
    ]
    
    print("\n=== Decision Engine Test ===\n")
    
    rankings = engine.rank(test_products)
    for i, decision in enumerate(rankings, 1):
        print(f"{i}. {decision.product_id}: {decision.score:.2f}")
        print(f"   Rationale: {decision.rationale}")
        print(f"   Competition: {decision.competition_level}")
        print(f"   Trend: {decision.trend_signal}")
        print()
