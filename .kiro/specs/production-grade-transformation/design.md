# Production-Grade System Design

## 🏗️ **ARCHITECTURAL OVERVIEW**

### Backend Architecture (Python/FastAPI)
```
cold_outreach_agent/
├── core/                    # Domain models and business logic
│   ├── models/             # Pydantic models and enums
│   ├── state_machines/     # Lead and email lifecycle state machines
│   ├── services/           # Business logic services
│   └── exceptions/         # Custom exception hierarchy
├── infrastructure/         # External integrations
│   ├── database/          # SQLite with proper migrations
│   ├── email/             # SMTP/Gmail API with failover
│   ├── scraping/          # Playwright with anti-detection
│   └── logging/           # Structured JSON logging
├── api/                   # FastAPI REST endpoints
├── background/            # Background job processing
├── desktop/               # Desktop packaging and deployment
└── config/                # Configuration management
```

### Frontend Architecture (React/TypeScript)
```
Frontend/src/
├── components/
│   ├── dashboard/         # Dashboard-specific components
│   ├── leads/            # Lead management components
│   ├── ui/               # Reusable UI components (shadcn/ui)
│   └── layout/           # Layout and navigation
├── hooks/                # Custom React hooks
├── services/             # API client and data fetching
├── stores/               # State management (TanStack Query)
├── types/                # TypeScript type definitions
└── utils/                # Utility functions
```

## 🔄 **STATE MACHINES**

### Lead Lifecycle State Machine
```
DISCOVERED → ANALYZING → ANALYZED → PENDING_REVIEW → APPROVED/REJECTED
    ↓           ↓           ↓            ↓              ↓
FAILED     FAILED     FAILED      EXPIRED        READY_FOR_OUTREACH
```

### Email Lifecycle State Machine  
```
QUEUED → SENDING → SENT → DELIVERED → OPENED → REPLIED
   ↓        ↓        ↓        ↓         ↓        ↓
FAILED   FAILED   FAILED   BOUNCED   FAILED   CATEGORIZED
```

## 🗄️ **DATABASE SCHEMA REDESIGN**

### Core Tables
```sql
-- Leads with proper state tracking
CREATE TABLE leads (
    id UUID PRIMARY KEY,
    business_name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    location VARCHAR(255),
    maps_url TEXT UNIQUE,
    website_url TEXT,
    email VARCHAR(255),
    phone VARCHAR(50),
    
    -- Discovery metadata
    discovery_source VARCHAR(50) NOT NULL,
    discovery_confidence DECIMAL(3,2),
    discovery_metadata JSONB,
    discovered_at TIMESTAMP NOT NULL,
    
    -- State tracking
    lifecycle_state VARCHAR(50) NOT NULL DEFAULT 'discovered',
    review_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    
    -- Audit fields
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1
);

-- Email campaigns and tracking
CREATE TABLE email_campaigns (
    id UUID PRIMARY KEY,
    lead_id UUID NOT NULL REFERENCES leads(id),
    campaign_type VARCHAR(50) NOT NULL, -- 'initial', 'followup_1', etc.
    
    -- Email content
    subject VARCHAR(255) NOT NULL,
    body_text TEXT NOT NULL,
    body_html TEXT,
    
    -- State tracking
    email_state VARCHAR(50) NOT NULL DEFAULT 'queued',
    
    -- Delivery tracking
    queued_at TIMESTAMP,
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    opened_at TIMESTAMP,
    replied_at TIMESTAMP,
    
    -- Error tracking
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    
    -- Audit fields
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Comprehensive audit log
CREATE TABLE audit_log (
    id UUID PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL, -- 'lead', 'email', 'system'
    entity_id UUID,
    action VARCHAR(100) NOT NULL,
    actor VARCHAR(100) NOT NULL, -- 'system', 'user', 'agent'
    
    -- Change tracking
    old_values JSONB,
    new_values JSONB,
    metadata JSONB,
    
    -- Context
    session_id UUID,
    request_id UUID,
    
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

## 🔧 **CORE SERVICES REDESIGN**

### 1. Enhanced Google Maps Scraper
```python
class ProductionMapsScraperService:
    """Production-grade Google Maps scraping with anti-detection"""
    
    async def discover_businesses(
        self, 
        query: str, 
        location: str, 
        max_results: int = 50
    ) -> DiscoveryResult:
        # Multi-strategy approach:
        # 1. Primary: Playwright with rotating user agents
        # 2. Fallback: Alternative selectors and search methods
        # 3. Last resort: API-based alternatives
        pass
    
    def _get_location_coordinates(self, location: str) -> Coordinates:
        # Geocoding with multiple providers
        pass
    
    def _apply_geo_bias(self, search_url: str, coords: Coordinates) -> str:
        # Add geographic biasing to search
        pass
```

### 2. Transactional Email Service
```python
class TransactionalEmailService:
    """Reliable email sending with state management"""
    
    async def send_email_transactional(
        self, 
        campaign: EmailCampaign
    ) -> EmailResult:
        # Atomic state transitions with rollback
        async with self.db.transaction():
            # Update state to 'sending'
            # Attempt delivery
            # Update final state based on result
            # Log all state changes
        pass
    
    async def retry_failed_emails(self) -> RetryResult:
        # Exponential backoff retry logic
        pass
```

### 3. Lead State Machine Service
```python
class LeadStateMachineService:
    """Manages lead lifecycle with proper state transitions"""
    
    def transition_state(
        self, 
        lead_id: UUID, 
        target_state: LeadState,
        actor: str,
        metadata: dict = None
    ) -> StateTransitionResult:
        # Validate transition is allowed
        # Execute transition atomically
        # Log state change
        # Trigger side effects
        pass
```

## 🖥️ **DESKTOP PACKAGING STRATEGY**

### PyInstaller Configuration
```python
# build_desktop.py
import PyInstaller.__main__

PyInstaller.__main__.run([
    'cold_outreach_agent/desktop/main.py',
    '--onefile',
    '--windowed',
    '--add-data', 'Frontend/dist;frontend',
    '--add-data', 'cold_outreach_agent/templates;templates',
    '--hidden-import', 'playwright',
    '--hidden-import', 'sqlite3',
    '--name', 'ColdOutreachAgent',
    '--icon', 'assets/icon.ico'
])
```

### Desktop Application Structure
```python
class DesktopApplication:
    """Main desktop application controller"""
    
    def __init__(self):
        self.backend_process = None
        self.browser_process = None
        self.config_manager = LocalConfigManager()
    
    def start(self):
        # Start FastAPI backend on random port
        # Bundle and serve React frontend
        # Launch browser or embedded webview
        # Setup graceful shutdown handlers
        pass
    
    def shutdown(self):
        # Stop all processes gracefully
        # Save state and configuration
        pass
```

## 📊 **OBSERVABILITY IMPLEMENTATION**

### Structured Logging
```python
import structlog

logger = structlog.get_logger()

# Example usage
logger.info(
    "lead_discovered",
    lead_id=lead.id,
    business_name=lead.business_name,
    discovery_source="google_maps",
    confidence=0.95,
    duration_ms=1250
)
```

### Error Boundaries and Recovery
```python
class ErrorBoundaryService:
    """Comprehensive error handling and recovery"""
    
    def handle_scraping_error(self, error: Exception, context: dict):
        # Log structured error
        # Attempt recovery strategies
        # Update system health metrics
        # Notify monitoring systems
        pass
    
    def handle_email_error(self, error: Exception, campaign: EmailCampaign):
        # Mark email as failed
        # Schedule retry if appropriate
        # Update delivery metrics
        pass
```

## 🔐 **SECURITY & COMPLIANCE**

### Data Protection
- All PII encrypted at rest
- Secure credential storage
- GDPR compliance features
- Data retention policies

### Email Compliance
- CAN-SPAM compliance
- Unsubscribe handling
- Rate limiting enforcement
- Reputation protection

## 🚀 **DEPLOYMENT STRATEGY**

### Development Environment
```bash
# Local development setup
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
playwright install
npm install --prefix Frontend
```

### Production Build
```bash
# Build frontend
cd Frontend && npm run build

# Build desktop application
python build_desktop.py

# Result: Single executable file
# ColdOutreachAgent.exe (Windows)
# ColdOutreachAgent (Linux/Mac)
```

### Update Mechanism
- Version checking on startup
- Automatic update downloads
- Graceful restart for updates
- Rollback capability

This design ensures a robust, production-ready system that addresses all the critical issues while maintaining the core functionality of automated lead discovery and email outreach.