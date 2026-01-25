"""Analytics and insights models."""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MetricPeriod(str, Enum):
    """Time periods for metrics."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    ALL_TIME = "all_time"


class MetricType(str, Enum):
    """Types of metrics."""
    LEAD_COUNT = "lead_count"
    EMAIL_SENT = "email_sent"
    EMAIL_OPENED = "email_opened"
    EMAIL_CLICKED = "email_clicked"
    EMAIL_REPLIED = "email_replied"
    EMAIL_BOUNCED = "email_bounced"
    CONVERSION_RATE = "conversion_rate"
    OPEN_RATE = "open_rate"
    REPLY_RATE = "reply_rate"
    BOUNCE_RATE = "bounce_rate"


class ChartType(str, Enum):
    """Types of charts for visualization."""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    DOUGHNUT = "doughnut"
    AREA = "area"
    FUNNEL = "funnel"
    HEATMAP = "heatmap"
    TABLE = "table"


class FunnelStage(BaseModel):
    """Stage in a conversion funnel."""
    name: str = Field(..., max_length=50)
    count: int = Field(default=0, ge=0)
    percentage_of_total: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    percentage_of_previous: Optional[Decimal] = Field(None, ge=0, le=100)
    drop_off_rate: Optional[Decimal] = Field(None, ge=0, le=100)


class LeadFunnelData(BaseModel):
    """Lead funnel conversion data."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    
    # Period
    period: MetricPeriod
    start_date: date
    end_date: date
    
    # Funnel stages
    stages: List[FunnelStage] = Field(default_factory=list)
    
    # Key metrics
    total_leads: int = Field(default=0, ge=0)
    total_converted: int = Field(default=0, ge=0)
    overall_conversion_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    
    # Timing
    avg_time_to_conversion_hours: Optional[Decimal] = Field(None, ge=0)
    
    # Generated at
    generated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: float(v)
        }


class CampaignPerformance(BaseModel):
    """Campaign performance metrics."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    campaign_id: Optional[UUID] = None
    campaign_name: Optional[str] = Field(None, max_length=200)
    
    # Period
    period: MetricPeriod
    start_date: date
    end_date: date
    
    # Email metrics
    emails_sent: int = Field(default=0, ge=0)
    emails_delivered: int = Field(default=0, ge=0)
    emails_opened: int = Field(default=0, ge=0)
    emails_clicked: int = Field(default=0, ge=0)
    emails_replied: int = Field(default=0, ge=0)
    emails_bounced: int = Field(default=0, ge=0)
    emails_unsubscribed: int = Field(default=0, ge=0)
    
    # Calculated rates
    delivery_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    open_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    click_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    reply_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    bounce_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    unsubscribe_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    
    # Engagement score (composite)
    engagement_score: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    
    # Comparison to previous period
    vs_previous_period: Optional[Dict[str, Decimal]] = None
    
    # Generated at
    generated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: float(v)
        }


class TemplatePerformance(BaseModel):
    """Template performance ranking."""
    
    # Template info
    template_id: str = Field(..., max_length=100)
    template_name: str = Field(..., max_length=200)
    template_category: Optional[str] = Field(None, max_length=50)
    
    # Usage
    times_used: int = Field(default=0, ge=0)
    unique_leads: int = Field(default=0, ge=0)
    
    # Performance
    open_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    click_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    reply_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    bounce_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    
    # Ranking
    performance_score: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    rank: Optional[int] = Field(None, ge=1)
    
    # Trend
    trend_direction: Optional[str] = Field(None)  # "up", "down", "stable"
    trend_percentage: Optional[Decimal] = Field(None)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class IndustryResponseRate(BaseModel):
    """Response rates by industry."""
    
    industry: str = Field(..., max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    
    # Volume
    total_leads: int = Field(default=0, ge=0)
    total_emails_sent: int = Field(default=0, ge=0)
    
    # Rates
    open_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    reply_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    conversion_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    
    # Best time to send
    best_send_hour: Optional[int] = Field(None, ge=0, le=23)
    best_send_day: Optional[str] = Field(None, max_length=20)
    
    # Ranking
    score: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class LocationHeatmapData(BaseModel):
    """Location-based response heatmap."""
    
    # Location
    location: str = Field(..., max_length=200)
    country: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    
    # Coordinates (for map visualization)
    latitude: Optional[Decimal] = Field(None)
    longitude: Optional[Decimal] = Field(None)
    
    # Metrics
    lead_count: int = Field(default=0, ge=0)
    email_count: int = Field(default=0, ge=0)
    reply_count: int = Field(default=0, ge=0)
    
    # Rates
    reply_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    conversion_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=100)
    
    # Heat intensity (for visualization)
    heat_intensity: Decimal = Field(default=Decimal("0.0"), ge=0, le=1)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class TimeSeriesDataPoint(BaseModel):
    """Single data point in a time series."""
    timestamp: datetime
    value: Decimal
    label: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


class TimeSeriesMetric(BaseModel):
    """Time series metric data for charts."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    metric_type: MetricType
    
    # Period
    period: MetricPeriod
    start_date: datetime
    end_date: datetime
    
    # Data
    data_points: List[TimeSeriesDataPoint] = Field(default_factory=list)
    
    # Aggregations
    total: Decimal = Field(default=Decimal("0.0"))
    average: Decimal = Field(default=Decimal("0.0"))
    min_value: Decimal = Field(default=Decimal("0.0"))
    max_value: Decimal = Field(default=Decimal("0.0"))
    
    # Trend
    trend_direction: Optional[str] = Field(None)  # "up", "down", "stable"
    trend_percentage: Optional[Decimal] = Field(None)
    
    # Generated at
    generated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: float(v)
        }


class DashboardWidget(BaseModel):
    """Dashboard widget configuration."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    
    # Widget info
    title: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    
    # Type and data
    chart_type: ChartType
    metric_types: List[MetricType] = Field(default_factory=list)
    
    # Configuration
    config: Dict[str, Any] = Field(default_factory=dict)
    
    # Layout
    position_x: int = Field(default=0, ge=0)
    position_y: int = Field(default=0, ge=0)
    width: int = Field(default=2, ge=1, le=12)
    height: int = Field(default=2, ge=1, le=12)
    
    # Visibility
    is_visible: bool = Field(default=True)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: lambda v: str(v)
        }


class AnalyticsDashboard(BaseModel):
    """Full analytics dashboard."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(default="Main Dashboard", max_length=100)
    
    # Widgets
    widgets: List[DashboardWidget] = Field(default_factory=list)
    
    # Summary metrics (quick stats)
    summary: Dict[str, Any] = Field(default_factory=dict)
    
    # Period
    default_period: MetricPeriod = Field(default=MetricPeriod.WEEKLY)
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: str = Field(default="system", max_length=100)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class AnalyticsQuery(BaseModel):
    """Query parameters for analytics data."""
    metric_types: List[MetricType] = Field(default_factory=list)
    period: MetricPeriod = Field(default=MetricPeriod.WEEKLY)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    group_by: Optional[str] = Field(None, max_length=50)  # e.g., "industry", "location"
    filters: Dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=100, ge=1, le=1000)


class AnalyticsExportRequest(BaseModel):
    """Request to export analytics data."""
    query: AnalyticsQuery
    format: str = Field(default="csv", max_length=10)  # csv, json, xlsx
    include_charts: bool = Field(default=False)
