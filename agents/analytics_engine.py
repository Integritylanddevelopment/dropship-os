#!/usr/bin/env python3
"""
Analytics Engine — Metrics & Performance Tracking
=================================================

Aggregates KPIs across ShipStack:
- Product decisions made
- Video generation success rate
- Social media engagement
- Revenue & margin projections

Reads from shipstack_actions.jsonl and platform APIs.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List
from collections import defaultdict

logger = logging.getLogger(__name__)

DROPSHIP_OS_ROOT = Path(__file__).parent
ACTIONS_LOG = DROPSHIP_OS_ROOT / "logs" / "shipstack_actions.jsonl"


class AnalyticsEngine:
    """
    Computes metrics from action logs and service APIs.
    """
    
    def __init__(self):
        self.actions_log = ACTIONS_LOG
    
    def load_actions(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Load actions from past N hours."""
        if not self.actions_log.exists():
            return []
        
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        actions = []
        
        try:
            with open(self.actions_log, "r") as f:
                for line in f:
                    if not line.strip():
                        continue
                    action = json.loads(line)
                    action_time = datetime.fromisoformat(action.get("timestamp", "").replace("Z", "+00:00"))
                    if action_time > cutoff:
                        actions.append(action)
        except Exception as e:
            logger.error(f"Error loading actions: {e}")
        
        return actions
    
    def get_summary_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Compute high-level KPIs.
        """
        actions = self.load_actions(hours)
        
        if not actions:
            return {
                "period_hours": hours,
                "total_actions": 0,
                "success_rate": 0.0,
                "tool_breakdown": {},
            }
        
        total = len(actions)
        successful = sum(1 for a in actions if a.get("success", False))
        success_rate = successful / total if total > 0 else 0.0
        
        # Tool breakdown
        tool_breakdown = defaultdict(int)
        for action in actions:
            tool = action.get("tool_name", "unknown")
            tool_breakdown[tool] += 1
        
        # Action breakdown
        action_breakdown = defaultdict(int)
        for action in actions:
            action_type = action.get("action", "unknown")
            action_breakdown[action_type] += 1
        
        return {
            "period_hours": hours,
            "total_actions": total,
            "successful_actions": successful,
            "success_rate": success_rate,
            "tool_breakdown": dict(tool_breakdown),
            "action_breakdown": dict(action_breakdown),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    
    def get_decision_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Metrics related to product decisions.
        """
        actions = self.load_actions(hours)
        
        decision_actions = [a for a in actions if "decide" in a.get("tool_name", "").lower()]
        
        total_decisions = len(decision_actions)
        avg_decisions_per_hour = total_decisions / max(1, hours)
        
        return {
            "total_decisions_made": total_decisions,
            "avg_decisions_per_hour": avg_decisions_per_hour,
            "success_rate": sum(1 for a in decision_actions if a.get("success")) / max(1, total_decisions),
        }
    
    def get_video_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Metrics related to video generation.
        """
        actions = self.load_actions(hours)
        
        video_actions = [a for a in actions if "video" in a.get("tool_name", "").lower()]
        
        total_videos = len(video_actions)
        successful_videos = sum(1 for a in video_actions if a.get("success"))
        success_rate = successful_videos / max(1, total_videos)
        
        return {
            "videos_generated": total_videos,
            "videos_successful": successful_videos,
            "success_rate": success_rate,
            "avg_time_seconds": 120,  # placeholder
        }
    
    def get_engagement_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Metrics related to social media engagement.
        """
        actions = self.load_actions(hours)
        
        social_actions = [a for a in actions if "social" in a.get("tool_name", "").lower() or "post" in a.get("action", "").lower()]
        
        total_posts = len(social_actions)
        
        # Placeholder: would fetch from social APIs
        total_engagement = total_posts * 150  # Assume ~150 avg engagement per post
        avg_engagement_per_post = 150
        
        return {
            "posts_published": total_posts,
            "total_engagement": total_engagement,
            "avg_engagement_per_post": avg_engagement_per_post,
            "platforms": ["tiktok", "instagram", "pinterest", "youtube"],
        }
    
    def get_revenue_projection(self, hours: int = 24, avg_product_margin: float = 15.0, conversion_rate: float = 0.02) -> Dict[str, Any]:
        """
        Project revenue based on decisions made.
        
        Assumes:
        - avg_product_margin: $15 per sale
        - conversion_rate: 2% of viewers buy
        """
        metrics = self.get_engagement_metrics(hours)
        total_engagement = metrics.get("total_engagement", 0)
        
        estimated_sales = int(total_engagement * conversion_rate)
        projected_revenue = estimated_sales * avg_product_margin
        
        return {
            "estimated_viewers": total_engagement,
            "estimated_conversion_rate": conversion_rate,
            "estimated_sales": estimated_sales,
            "avg_product_margin": avg_product_margin,
            "projected_revenue": projected_revenue,
            "period_hours": hours,
        }
    
    def get_full_dashboard(self, hours: int = 24) -> Dict[str, Any]:
        """
        Comprehensive dashboard snapshot.
        """
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "period_hours": hours,
            "summary": self.get_summary_metrics(hours),
            "decisions": self.get_decision_metrics(hours),
            "videos": self.get_video_metrics(hours),
            "engagement": self.get_engagement_metrics(hours),
            "revenue_projection": self.get_revenue_projection(hours),
        }


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    analytics = AnalyticsEngine()
    
    print("\n=== Analytics Engine Test ===\n")
    
    dashboard = analytics.get_full_dashboard(hours=24)
    print(json.dumps(dashboard, indent=2))
