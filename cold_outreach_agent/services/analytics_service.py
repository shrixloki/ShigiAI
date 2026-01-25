"""Analytics and insights service."""

import asyncio
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List
from uuid import UUID
from collections import defaultdict

from ..core.models.analytics import (
    LeadFunnelData, FunnelStage, CampaignPerformance, TemplatePerformance,
    IndustryResponseRate, LocationHeatmapData, TimeSeriesMetric, TimeSeriesDataPoint,
    MetricPeriod, MetricType, AnalyticsQuery, AnalyticsDashboard
)
from ..core.exceptions import ColdOutreachAgentError
from ..modules.logger import action_logger


class AnalyticsError(ColdOutreachAgentError):
    """Analytics operation failed."""
    pass


class AnalyticsService:
    """
    Analytics and insights service.
    
    Features:
    - Lead funnel conversion tracking
    - Campaign performance metrics
    - Template effectiveness ranking
    - Industry response rates
    - Location-based heatmaps
    - Time series metrics
    """
    
    # Funnel stages in order
    FUNNEL_STAGES = [
        ("discovered", "Discovered"),
        ("analyzed", "Analyzed"),
        ("pending_review", "Pending Review"),
        ("approved", "Approved"),
        ("sent_initial", "Email Sent"),
        ("replied", "Replied"),
        ("converted", "Converted")
    ]
    
    def __init__(self, db_service):
        self.db = db_service
        self._metrics_cache: Dict[str, Any] = {}
        self._cache_ttl = timedelta(minutes=5)
    
    async def get_lead_funnel(self, period: MetricPeriod = MetricPeriod.WEEKLY,
                               start_date: Optional[date] = None,
                               end_date: Optional[date] = None) -> LeadFunnelData:
        """
        Get lead funnel conversion data.
        
        Args:
            period: Time period for analysis
            start_date: Start date (optional)
            end_date: End date (optional)
        
        Returns:
            LeadFunnelData with funnel stages
        """
        # Calculate date range
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = self._get_period_start(end_date, period)
        
        # Get leads in date range
        leads = await self._get_leads_in_range(start_date, end_date)
        
        # Count leads at each stage
        stage_counts = defaultdict(int)
        for lead in leads:
            review_status = lead.get('review_status', 'pending')
            outreach_status = lead.get('outreach_status', 'not_sent')
            
            # Determine which stage lead is in
            stage_counts['discovered'] += 1
            
            if lead.get('tag'):
                stage_counts['analyzed'] += 1
            
            if review_status == 'pending':
                stage_counts['pending_review'] += 1
            elif review_status == 'approved':
                stage_counts['approved'] += 1
                
                if outreach_status in ['sent_initial', 'sent_followup', 'replied']:
                    stage_counts['sent_initial'] += 1
                    
                    if outreach_status == 'replied':
                        stage_counts['replied'] += 1
        
        # Build funnel stages
        total_leads = len(leads)
        stages = []
        prev_count = total_leads
        
        for stage_key, stage_name in self.FUNNEL_STAGES:
            count = stage_counts.get(stage_key, 0)
            
            pct_of_total = Decimal(str(count / total_leads * 100)) if total_leads > 0 else Decimal("0")
            pct_of_prev = Decimal(str(count / prev_count * 100)) if prev_count > 0 else Decimal("0")
            drop_off = Decimal("100") - pct_of_prev if count < prev_count else Decimal("0")
            
            stages.append(FunnelStage(
                name=stage_name,
                count=count,
                percentage_of_total=pct_of_total,
                percentage_of_previous=pct_of_prev,
                drop_off_rate=drop_off
            ))
            
            if count > 0:
                prev_count = count
        
        # Calculate conversion metrics
        converted = stage_counts.get('replied', 0)
        conversion_rate = Decimal(str(converted / total_leads * 100)) if total_leads > 0 else Decimal("0")
        
        return LeadFunnelData(
            period=period,
            start_date=start_date,
            end_date=end_date,
            stages=stages,
            total_leads=total_leads,
            total_converted=converted,
            overall_conversion_rate=conversion_rate
        )
    
    async def get_campaign_performance(self, campaign_id: Optional[UUID] = None,
                                         period: MetricPeriod = MetricPeriod.WEEKLY,
                                         start_date: Optional[date] = None,
                                         end_date: Optional[date] = None) -> CampaignPerformance:
        """
        Get campaign performance metrics.
        
        Args:
            campaign_id: Specific campaign (optional, None for all)
            period: Time period
            start_date: Start date
            end_date: End date
        
        Returns:
            CampaignPerformance metrics
        """
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = self._get_period_start(end_date, period)
        
        # Get email campaigns in range
        campaigns = await self._get_campaigns_in_range(start_date, end_date, campaign_id)
        
        # Aggregate metrics
        sent = len(campaigns)
        delivered = sum(1 for c in campaigns if c.get('email_state') not in ['failed', 'bounced'])
        opened = sum(1 for c in campaigns if c.get('opened_at'))
        clicked = sum(1 for c in campaigns if c.get('clicked_at'))
        replied = sum(1 for c in campaigns if c.get('replied_at'))
        bounced = sum(1 for c in campaigns if c.get('email_state') == 'bounced')
        
        # Calculate rates
        delivery_rate = Decimal(str(delivered / sent * 100)) if sent > 0 else Decimal("0")
        open_rate = Decimal(str(opened / delivered * 100)) if delivered > 0 else Decimal("0")
        click_rate = Decimal(str(clicked / opened * 100)) if opened > 0 else Decimal("0")
        reply_rate = Decimal(str(replied / sent * 100)) if sent > 0 else Decimal("0")
        bounce_rate = Decimal(str(bounced / sent * 100)) if sent > 0 else Decimal("0")
        
        # Calculate engagement score (weighted)
        engagement = (
            open_rate * Decimal("0.3") +
            click_rate * Decimal("0.2") +
            reply_rate * Decimal("0.5")
        )
        
        return CampaignPerformance(
            campaign_id=campaign_id,
            period=period,
            start_date=start_date,
            end_date=end_date,
            emails_sent=sent,
            emails_delivered=delivered,
            emails_opened=opened,
            emails_clicked=clicked,
            emails_replied=replied,
            emails_bounced=bounced,
            delivery_rate=delivery_rate,
            open_rate=open_rate,
            click_rate=click_rate,
            reply_rate=reply_rate,
            bounce_rate=bounce_rate,
            engagement_score=engagement
        )
    
    async def get_template_rankings(self, limit: int = 10) -> List[TemplatePerformance]:
        """
        Get template performance rankings.
        
        Args:
            limit: Maximum templates to return
        
        Returns:
            List of TemplatePerformance ranked by effectiveness
        """
        # Get all campaigns grouped by template
        campaigns = await self._get_all_campaigns()
        
        template_stats = defaultdict(lambda: {
            'times_used': 0,
            'leads': set(),
            'opens': 0,
            'clicks': 0,
            'replies': 0,
            'bounces': 0
        })
        
        for campaign in campaigns:
            template_id = campaign.get('template_id', 'default')
            stats = template_stats[template_id]
            
            stats['times_used'] += 1
            stats['leads'].add(campaign.get('lead_id'))
            
            if campaign.get('opened_at'):
                stats['opens'] += 1
            if campaign.get('clicked_at'):
                stats['clicks'] += 1
            if campaign.get('replied_at'):
                stats['replies'] += 1
            if campaign.get('email_state') == 'bounced':
                stats['bounces'] += 1
        
        # Calculate rankings
        rankings = []
        for template_id, stats in template_stats.items():
            used = stats['times_used']
            if used == 0:
                continue
            
            open_rate = Decimal(str(stats['opens'] / used * 100))
            click_rate = Decimal(str(stats['clicks'] / max(stats['opens'], 1) * 100))
            reply_rate = Decimal(str(stats['replies'] / used * 100))
            bounce_rate = Decimal(str(stats['bounces'] / used * 100))
            
            # Performance score (heavily weighted toward replies)
            score = (
                open_rate * Decimal("0.2") +
                click_rate * Decimal("0.1") +
                reply_rate * Decimal("0.6") -
                bounce_rate * Decimal("0.1")
            )
            score = max(Decimal("0"), min(Decimal("100"), score))
            
            rankings.append(TemplatePerformance(
                template_id=template_id,
                template_name=template_id.replace('_', ' ').title(),
                times_used=used,
                unique_leads=len(stats['leads']),
                open_rate=open_rate,
                click_rate=click_rate,
                reply_rate=reply_rate,
                bounce_rate=bounce_rate,
                performance_score=score
            ))
        
        # Sort by performance score
        rankings.sort(key=lambda x: x.performance_score, reverse=True)
        
        # Assign ranks
        for i, ranking in enumerate(rankings[:limit], 1):
            ranking.rank = i
        
        return rankings[:limit]
    
    async def get_industry_response_rates(self) -> List[IndustryResponseRate]:
        """
        Get response rates by industry/category.
        
        Returns:
            List of IndustryResponseRate
        """
        leads = await self._get_all_leads()
        campaigns = await self._get_all_campaigns()
        
        # Group campaigns by lead category
        lead_categories = {l.get('lead_id'): l.get('category', 'Unknown') for l in leads}
        
        industry_stats = defaultdict(lambda: {
            'leads': 0,
            'emails_sent': 0,
            'opens': 0,
            'replies': 0
        })
        
        # Count leads per industry
        for lead in leads:
            category = lead.get('category', 'Unknown') or 'Unknown'
            industry_stats[category]['leads'] += 1
        
        # Count email metrics per industry
        for campaign in campaigns:
            lead_id = campaign.get('lead_id')
            category = lead_categories.get(lead_id, 'Unknown')
            
            industry_stats[category]['emails_sent'] += 1
            if campaign.get('opened_at'):
                industry_stats[category]['opens'] += 1
            if campaign.get('replied_at'):
                industry_stats[category]['replies'] += 1
        
        # Build response rate list
        results = []
        for industry, stats in industry_stats.items():
            sent = stats['emails_sent']
            if sent == 0:
                continue
            
            open_rate = Decimal(str(stats['opens'] / sent * 100))
            reply_rate = Decimal(str(stats['replies'] / sent * 100))
            
            # Score based on reply rate and volume
            score = reply_rate
            if stats['leads'] >= 10:
                score += Decimal("5")  # Volume bonus
            
            results.append(IndustryResponseRate(
                industry=industry,
                total_leads=stats['leads'],
                total_emails_sent=sent,
                open_rate=open_rate,
                reply_rate=reply_rate,
                score=score
            ))
        
        # Sort by reply rate
        results.sort(key=lambda x: x.reply_rate, reverse=True)
        
        return results
    
    async def get_location_heatmap(self) -> List[LocationHeatmapData]:
        """
        Get location-based response heatmap data.
        
        Returns:
            List of LocationHeatmapData
        """
        leads = await self._get_all_leads()
        campaigns = await self._get_all_campaigns()
        
        # Group campaigns by lead location
        lead_locations = {l.get('lead_id'): l.get('location', 'Unknown') for l in leads}
        
        location_stats = defaultdict(lambda: {
            'leads': 0,
            'emails': 0,
            'replies': 0
        })
        
        # Count leads per location
        for lead in leads:
            location = lead.get('location', 'Unknown') or 'Unknown'
            location_stats[location]['leads'] += 1
        
        # Count replies per location
        for campaign in campaigns:
            lead_id = campaign.get('lead_id')
            location = lead_locations.get(lead_id, 'Unknown')
            
            location_stats[location]['emails'] += 1
            if campaign.get('replied_at'):
                location_stats[location]['replies'] += 1
        
        # Build heatmap data
        results = []
        max_replies = max(s['replies'] for s in location_stats.values()) if location_stats else 1
        
        for location, stats in location_stats.items():
            emails = stats['emails']
            
            reply_rate = Decimal(str(stats['replies'] / emails * 100)) if emails > 0 else Decimal("0")
            
            # Heat intensity based on reply volume
            intensity = Decimal(str(stats['replies'] / max_replies)) if max_replies > 0 else Decimal("0")
            
            results.append(LocationHeatmapData(
                location=location,
                lead_count=stats['leads'],
                email_count=emails,
                reply_count=stats['replies'],
                reply_rate=reply_rate,
                heat_intensity=intensity
            ))
        
        # Sort by reply count
        results.sort(key=lambda x: x.reply_count, reverse=True)
        
        return results[:50]  # Top 50 locations
    
    async def get_time_series(self, metric_type: MetricType,
                               period: MetricPeriod = MetricPeriod.DAILY,
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None) -> TimeSeriesMetric:
        """
        Get time series data for a specific metric.
        
        Args:
            metric_type: Type of metric
            period: Aggregation period
            start_date: Start date
            end_date: End date
        
        Returns:
            TimeSeriesMetric with data points
        """
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            if period == MetricPeriod.HOURLY:
                start_date = end_date - timedelta(days=1)
            elif period == MetricPeriod.DAILY:
                start_date = end_date - timedelta(days=30)
            elif period == MetricPeriod.WEEKLY:
                start_date = end_date - timedelta(weeks=12)
            else:
                start_date = end_date - timedelta(days=365)
        
        # Get raw data based on metric type
        if metric_type in [MetricType.LEAD_COUNT]:
            data = await self._get_leads_in_range(start_date.date(), end_date.date())
            date_field = 'discovered_at'
        else:
            data = await self._get_campaigns_in_range(start_date.date(), end_date.date())
            date_field = 'created_at'
        
        # Aggregate by period
        data_points = self._aggregate_by_period(data, date_field, metric_type, period)
        
        # Calculate stats
        values = [dp.value for dp in data_points]
        total = sum(values, Decimal("0"))
        avg = total / max(len(values), 1)
        min_val = min(values) if values else Decimal("0")
        max_val = max(values) if values else Decimal("0")
        
        # Determine trend
        if len(values) >= 2:
            first_half = sum(values[:len(values)//2], Decimal("0"))
            second_half = sum(values[len(values)//2:], Decimal("0"))
            
            if second_half > first_half * Decimal("1.1"):
                trend = "up"
                trend_pct = ((second_half - first_half) / max(first_half, Decimal("1"))) * 100
            elif second_half < first_half * Decimal("0.9"):
                trend = "down"
                trend_pct = ((first_half - second_half) / max(first_half, Decimal("1"))) * 100
            else:
                trend = "stable"
                trend_pct = Decimal("0")
        else:
            trend = None
            trend_pct = None
        
        return TimeSeriesMetric(
            metric_type=metric_type,
            period=period,
            start_date=start_date,
            end_date=end_date,
            data_points=data_points,
            total=total,
            average=avg,
            min_value=min_val,
            max_value=max_val,
            trend_direction=trend,
            trend_percentage=trend_pct
        )
    
    def _aggregate_by_period(self, data: List[Dict], date_field: str,
                             metric_type: MetricType,
                             period: MetricPeriod) -> List[TimeSeriesDataPoint]:
        """Aggregate data into time series points."""
        buckets = defaultdict(int)
        
        count_field = None
        if metric_type == MetricType.EMAIL_SENT:
            count_field = None  # Just count
        elif metric_type == MetricType.EMAIL_OPENED:
            count_field = 'opened_at'
        elif metric_type == MetricType.EMAIL_REPLIED:
            count_field = 'replied_at'
        
        for item in data:
            date_str = item.get(date_field)
            if not date_str:
                continue
            
            if isinstance(date_str, str):
                try:
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except:
                    continue
            else:
                dt = date_str
            
            # Get bucket key based on period
            if period == MetricPeriod.HOURLY:
                bucket = dt.replace(minute=0, second=0, microsecond=0)
            elif period == MetricPeriod.DAILY:
                bucket = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == MetricPeriod.WEEKLY:
                # Start of week
                bucket = dt - timedelta(days=dt.weekday())
                bucket = bucket.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                # Monthly
                bucket = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Check if should count
            if count_field is None:
                buckets[bucket] += 1
            elif item.get(count_field):
                buckets[bucket] += 1
        
        # Convert to data points
        points = []
        for timestamp, value in sorted(buckets.items()):
            points.append(TimeSeriesDataPoint(
                timestamp=timestamp,
                value=Decimal(str(value))
            ))
        
        return points
    
    async def get_dashboard_summary(self) -> Dict[str, Any]:
        """
        Get summary metrics for dashboard.
        
        Returns:
            Dict with key metrics
        """
        # Get basic counts
        leads = await self._get_all_leads()
        campaigns = await self._get_all_campaigns()
        
        today = date.today()
        week_ago = today - timedelta(days=7)
        
        # Filter for this week
        leads_this_week = [l for l in leads if self._in_date_range(l.get('discovered_at'), week_ago, today)]
        campaigns_this_week = [c for c in campaigns if self._in_date_range(c.get('created_at'), week_ago, today)]
        
        # Calculate metrics
        total_leads = len(leads)
        new_leads = len(leads_this_week)
        
        total_sent = len(campaigns)
        sent_this_week = len(campaigns_this_week)
        
        total_opens = sum(1 for c in campaigns if c.get('opened_at'))
        total_replies = sum(1 for c in campaigns if c.get('replied_at'))
        
        open_rate = (total_opens / total_sent * 100) if total_sent > 0 else 0
        reply_rate = (total_replies / total_sent * 100) if total_sent > 0 else 0
        
        return {
            "total_leads": total_leads,
            "new_leads_this_week": new_leads,
            "total_emails_sent": total_sent,
            "emails_sent_this_week": sent_this_week,
            "total_opens": total_opens,
            "total_replies": total_replies,
            "open_rate": round(open_rate, 1),
            "reply_rate": round(reply_rate, 1),
            "avg_emails_per_day": round(sent_this_week / 7, 1)
        }
    
    def _get_period_start(self, end_date: date, period: MetricPeriod) -> date:
        """Get start date based on period."""
        if period == MetricPeriod.DAILY:
            return end_date
        elif period == MetricPeriod.WEEKLY:
            return end_date - timedelta(days=7)
        elif period == MetricPeriod.MONTHLY:
            return end_date - timedelta(days=30)
        elif period == MetricPeriod.QUARTERLY:
            return end_date - timedelta(days=90)
        elif period == MetricPeriod.YEARLY:
            return end_date - timedelta(days=365)
        else:
            return end_date - timedelta(days=30)
    
    def _in_date_range(self, date_str: Optional[str], start: date, end: date) -> bool:
        """Check if date string is in range."""
        if not date_str:
            return False
        try:
            if isinstance(date_str, str):
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
            else:
                dt = date_str.date() if hasattr(date_str, 'date') else date_str
            return start <= dt <= end
        except:
            return False
    
    async def _get_leads_in_range(self, start: date, end: date) -> List[Dict]:
        """Get leads in date range."""
        # For simplicity in this implementation, we get all leads and filter in memory
        # In a real high-volume system, we would query with WHERE created_at BETWEEN
        leads = await self._get_all_leads()
        
        # Convert date to datetime for comparison if needed, though _in_date_range handles it
        return [l for l in leads if self._in_date_range(l.get('discovered_at'), start, end)]
    
    async def _get_campaigns_in_range(self, start: date, end: date,
                                       campaign_id: Optional[UUID] = None) -> List[Dict]:
        """Get campaigns in date range."""
        # We can use the optimized DB query for campaigns
        start_dt = datetime.combine(start, datetime.min.time())
        end_dt = datetime.combine(end, datetime.max.time())
        
        campaigns = await self.db.get_campaigns_by_range(start_dt, end_dt)
        
        # Convert to dicts
        campaign_dicts = [c.dict() for c in campaigns]
        
        if campaign_id:
            campaign_dicts = [c for c in campaign_dicts if str(c.get('id')) == str(campaign_id)]
            
        return campaign_dicts
    
    async def _get_all_leads(self) -> List[Dict]:
        """Get all leads from database."""
        try:
            leads = await self.db.get_all_leads_for_analytics()
            return [l.dict() for l in leads]
        except Exception:
            return []
    
    async def _get_all_campaigns(self) -> List[Dict]:
        """Get all email campaigns."""
        try:
            campaigns = await self.db.get_all_campaigns()
            return [c.dict() for c in campaigns]
        except Exception:
            return []
