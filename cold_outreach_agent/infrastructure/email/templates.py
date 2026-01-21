"""Production-grade email template system with dynamic content generation."""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from jinja2 import Environment, FileSystemLoader, Template, TemplateError

from ...core.models.lead import Lead
from ...core.models.email import CampaignType
from ...core.models.common import OperationResult
from ...core.exceptions import EmailTemplateError


class EmailTemplateManager:
    """Manages email templates with dynamic content generation."""
    
    def __init__(self, templates_dir: Optional[Path] = None):
        self.templates_dir = templates_dir or Path(__file__).parent.parent.parent / "templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Built-in templates
        self.builtin_templates = self._get_builtin_templates()
        
        # Ensure built-in templates exist
        self._create_builtin_templates()
    
    def _get_builtin_templates(self) -> Dict[str, Dict[str, Any]]:
        """Define built-in email templates."""
        return {
            "initial_outreach": {
                "name": "Initial Outreach",
                "description": "First contact email for new leads",
                "subject_template": "Quick question about {{ business_name }}",
                "text_template": """Hi {{ contact_name or 'there' }},

I came across {{ business_name }} and was impressed by what you're doing in {{ location }}.

I help businesses like yours {{ value_proposition }}.

Would you be interested in a quick 15-minute call to discuss how this could benefit {{ business_name }}?

Best regards,
{{ sender_name }}

P.S. If this isn't relevant, just reply "not interested" and I won't reach out again.""",
                "html_template": """<p>Hi {{ contact_name or 'there' }},</p>

<p>I came across <strong>{{ business_name }}</strong> and was impressed by what you're doing in {{ location }}.</p>

<p>I help businesses like yours {{ value_proposition }}.</p>

<p>Would you be interested in a quick 15-minute call to discuss how this could benefit {{ business_name }}?</p>

<p>Best regards,<br>
{{ sender_name }}</p>

<p><em>P.S. If this isn't relevant, just reply "not interested" and I won't reach out again.</em></p>""",
                "variables": ["business_name", "contact_name", "location", "sender_name", "value_proposition"]
            },
            
            "followup_1": {
                "name": "First Follow-up",
                "description": "First follow-up email after initial outreach",
                "subject_template": "Re: {{ business_name }} - Following up",
                "text_template": """Hi {{ contact_name or 'there' }},

I wanted to follow up on my previous email about {{ business_name }}.

I understand you're busy, but I thought you might be interested in knowing that businesses similar to yours have seen {{ benefit_example }}.

If you'd like to learn more, I'm happy to share a quick case study that might be relevant to {{ business_name }}.

Just reply with "yes" and I'll send it over.

Best,
{{ sender_name }}""",
                "html_template": """<p>Hi {{ contact_name or 'there' }},</p>

<p>I wanted to follow up on my previous email about <strong>{{ business_name }}</strong>.</p>

<p>I understand you're busy, but I thought you might be interested in knowing that businesses similar to yours have seen {{ benefit_example }}.</p>

<p>If you'd like to learn more, I'm happy to share a quick case study that might be relevant to {{ business_name }}.</p>

<p>Just reply with "yes" and I'll send it over.</p>

<p>Best,<br>
{{ sender_name }}</p>""",
                "variables": ["business_name", "contact_name", "sender_name", "benefit_example"]
            },
            
            "followup_2": {
                "name": "Second Follow-up",
                "description": "Second follow-up email with social proof",
                "subject_template": "Last follow-up about {{ business_name }}",
                "text_template": """Hi {{ contact_name or 'there' }},

This will be my last email about this topic.

I recently helped {{ similar_business_example }} and thought the results might interest you:
- {{ result_1 }}
- {{ result_2 }}

If you're curious about how this could apply to {{ business_name }}, I'm happy to discuss.

Otherwise, I'll respect your time and won't reach out again.

Best regards,
{{ sender_name }}""",
                "html_template": """<p>Hi {{ contact_name or 'there' }},</p>

<p>This will be my last email about this topic.</p>

<p>I recently helped <strong>{{ similar_business_example }}</strong> and thought the results might interest you:</p>
<ul>
<li>{{ result_1 }}</li>
<li>{{ result_2 }}</li>
</ul>

<p>If you're curious about how this could apply to {{ business_name }}, I'm happy to discuss.</p>

<p>Otherwise, I'll respect your time and won't reach out again.</p>

<p>Best regards,<br>
{{ sender_name }}</p>""",
                "variables": ["business_name", "contact_name", "sender_name", "similar_business_example", "result_1", "result_2"]
            }
        }
    
    def _create_builtin_templates(self):
        """Create built-in template files if they don't exist."""
        for template_id, template_data in self.builtin_templates.items():
            # Create text template file
            text_file = self.templates_dir / f"{template_id}_text.txt"
            if not text_file.exists():
                text_file.write_text(template_data["text_template"], encoding='utf-8')
            
            # Create HTML template file
            html_file = self.templates_dir / f"{template_id}_html.html"
            if not html_file.exists():
                html_file.write_text(template_data["html_template"], encoding='utf-8')
            
            # Create subject template file
            subject_file = self.templates_dir / f"{template_id}_subject.txt"
            if not subject_file.exists():
                subject_file.write_text(template_data["subject_template"], encoding='utf-8')
    
    async def generate_email(
        self,
        lead: Lead,
        campaign_type: CampaignType,
        template_id: Optional[str] = None,
        custom_variables: Optional[Dict[str, Any]] = None
    ) -> OperationResult[tuple]:
        """
        Generate email content from template.
        
        Returns:
            OperationResult containing (subject, body_text, body_html) tuple
        """
        try:
            # Determine template ID
            if not template_id:
                template_id = self._get_default_template_id(campaign_type)
            
            # Get template context
            context = self._build_template_context(lead, custom_variables or {})
            
            # Generate subject
            subject_result = await self._render_template(f"{template_id}_subject.txt", context)
            if not subject_result.success:
                return subject_result
            
            # Generate text body
            text_result = await self._render_template(f"{template_id}_text.txt", context)
            if not text_result.success:
                return text_result
            
            # Generate HTML body (optional)
            html_result = await self._render_template(f"{template_id}_html.html", context)
            html_body = html_result.data if html_result.success else None
            
            return OperationResult.success_result(
                data=(subject_result.data, text_result.data, html_body)
            )
            
        except Exception as e:
            return OperationResult.error_result(
                error=f"Email generation failed: {str(e)}",
                error_code="EMAIL_GENERATION_FAILED"
            )
    
    def _get_default_template_id(self, campaign_type: CampaignType) -> str:
        """Get default template ID for campaign type."""
        template_mapping = {
            CampaignType.INITIAL: "initial_outreach",
            CampaignType.FOLLOWUP_1: "followup_1",
            CampaignType.FOLLOWUP_2: "followup_2",
            CampaignType.FOLLOWUP_3: "followup_2",  # Reuse followup_2 for now
            CampaignType.CUSTOM: "initial_outreach"  # Default fallback
        }
        
        return template_mapping.get(campaign_type, "initial_outreach")
    
    def _build_template_context(self, lead: Lead, custom_variables: Dict[str, Any]) -> Dict[str, Any]:
        """Build template context with lead data and custom variables."""
        
        # Extract contact name from business name or email
        contact_name = self._extract_contact_name(lead)
        
        # Build base context
        context = {
            # Lead information
            "business_name": lead.business_name,
            "location": lead.location,
            "category": lead.category or "business",
            "website_url": lead.website_url,
            "contact_name": contact_name,
            
            # Sender information (these should come from config)
            "sender_name": custom_variables.get("sender_name", "Your Name"),
            "sender_email": custom_variables.get("sender_email", "your@email.com"),
            
            # Dynamic content based on business category
            "value_proposition": self._get_value_proposition(lead.category),
            "benefit_example": self._get_benefit_example(lead.category),
            "similar_business_example": self._get_similar_business_example(lead.category, lead.location),
            "result_1": self._get_result_example(lead.category, 1),
            "result_2": self._get_result_example(lead.category, 2),
            
            # Utility variables
            "current_date": datetime.now().strftime("%B %d, %Y"),
            "current_year": datetime.now().year,
        }
        
        # Add custom variables (override defaults)
        context.update(custom_variables)
        
        return context
    
    def _extract_contact_name(self, lead: Lead) -> Optional[str]:
        """Extract contact name from lead data."""
        
        # Try to extract from business name
        business_name = lead.business_name.lower()
        
        # Common patterns that might indicate a person's name
        personal_indicators = [
            "dr.", "dr ", "doctor", "attorney", "lawyer", "cpa", 
            "& associates", "& co", "law office", "dental", "medical"
        ]
        
        # If business name contains personal indicators, try to extract name
        for indicator in personal_indicators:
            if indicator in business_name:
                # Simple extraction - take first part before indicator
                parts = business_name.split(indicator)[0].strip()
                if parts and len(parts.split()) <= 3:  # Reasonable name length
                    return parts.title()
        
        # Try to extract from email if available
        if lead.email:
            email_parts = lead.email.split('@')[0]
            # If email part looks like a name (contains . or _)
            if '.' in email_parts or '_' in email_parts:
                name_parts = email_parts.replace('.', ' ').replace('_', ' ')
                if len(name_parts.split()) <= 3:
                    return name_parts.title()
        
        return None
    
    def _get_value_proposition(self, category: Optional[str]) -> str:
        """Get value proposition based on business category."""
        
        if not category:
            return "improve their online presence and attract more customers"
        
        category_lower = category.lower()
        
        value_props = {
            "restaurant": "increase table bookings and improve online reviews",
            "cafe": "boost foot traffic and build customer loyalty",
            "coffee": "increase daily sales and improve customer retention",
            "plumber": "generate more service calls and build trust with homeowners",
            "dentist": "attract new patients and improve appointment booking",
            "lawyer": "generate qualified leads and establish thought leadership",
            "attorney": "attract new clients and improve online reputation",
            "gym": "increase membership sign-ups and improve retention",
            "fitness": "grow their member base and boost class attendance",
            "salon": "book more appointments and increase customer lifetime value",
            "spa": "attract new clients and increase service bookings",
            "retail": "drive more foot traffic and increase online sales",
            "shop": "attract more customers and boost sales"
        }
        
        for key, value in value_props.items():
            if key in category_lower:
                return value
        
        return "grow their business and reach more customers online"
    
    def _get_benefit_example(self, category: Optional[str]) -> str:
        """Get benefit example based on business category."""
        
        if not category:
            return "30% increase in customer inquiries within 60 days"
        
        category_lower = category.lower()
        
        benefits = {
            "restaurant": "25% increase in reservations and improved online ratings",
            "cafe": "40% boost in morning rush customers",
            "coffee": "35% increase in daily sales and repeat customers",
            "plumber": "50% more emergency service calls and higher booking rates",
            "dentist": "30% increase in new patient appointments",
            "lawyer": "45% more qualified consultation requests",
            "attorney": "40% increase in case inquiries",
            "gym": "60% improvement in membership conversion rates",
            "fitness": "35% increase in class bookings",
            "salon": "50% more appointment bookings and reduced no-shows",
            "spa": "40% increase in treatment bookings",
            "retail": "25% boost in foot traffic and online engagement",
            "shop": "30% increase in customer visits"
        }
        
        for key, value in benefits.items():
            if key in category_lower:
                return value
        
        return "significant improvement in customer acquisition and retention"
    
    def _get_similar_business_example(self, category: Optional[str], location: str) -> str:
        """Get similar business example."""
        
        if not category:
            business_type = "local business"
        else:
            business_type = category.lower()
        
        # Extract city from location
        city = location.split(',')[0].strip()
        
        # Generic business names by category
        business_names = {
            "restaurant": f"a family restaurant in {city}",
            "cafe": f"a local coffee shop in {city}",
            "coffee": f"an independent coffee roaster in {city}",
            "plumber": f"a plumbing company in {city}",
            "dentist": f"a dental practice in {city}",
            "lawyer": f"a law firm in {city}",
            "attorney": f"a legal practice in {city}",
            "gym": f"a fitness center in {city}",
            "fitness": f"a local gym in {city}",
            "salon": f"a hair salon in {city}",
            "spa": f"a wellness spa in {city}",
            "retail": f"a retail store in {city}",
            "shop": f"a local shop in {city}"
        }
        
        if category:
            for key, value in business_names.items():
                if key in category.lower():
                    return value
        
        return f"a {business_type} in {city}"
    
    def _get_result_example(self, category: Optional[str], result_number: int) -> str:
        """Get specific result example."""
        
        if not category:
            results = [
                "Increased online visibility by 200%",
                "Generated 50+ new customer inquiries per month"
            ]
            return results[result_number - 1] if result_number <= len(results) else results[0]
        
        category_lower = category.lower()
        
        result_sets = {
            "restaurant": [
                "Increased online reservations by 40%",
                "Improved Google rating from 3.8 to 4.6 stars"
            ],
            "cafe": [
                "Boosted morning rush sales by 35%",
                "Increased social media followers by 300%"
            ],
            "plumber": [
                "Generated 25+ service calls per week",
                "Improved emergency response booking rate by 60%"
            ],
            "dentist": [
                "Attracted 15+ new patients per month",
                "Reduced appointment cancellations by 30%"
            ],
            "lawyer": [
                "Generated 20+ consultation requests per month",
                "Improved online reputation and trust signals"
            ],
            "gym": [
                "Increased membership sign-ups by 45%",
                "Improved member retention rate by 25%"
            ],
            "salon": [
                "Boosted appointment bookings by 50%",
                "Increased average service value by 30%"
            ]
        }
        
        for key, results in result_sets.items():
            if key in category_lower:
                return results[result_number - 1] if result_number <= len(results) else results[0]
        
        # Default results
        default_results = [
            "Increased customer inquiries by 40%",
            "Improved online presence and brand visibility"
        ]
        
        return default_results[result_number - 1] if result_number <= len(default_results) else default_results[0]
    
    async def _render_template(self, template_name: str, context: Dict[str, Any]) -> OperationResult[str]:
        """Render template with context."""
        try:
            template = self.jinja_env.get_template(template_name)
            rendered = template.render(**context)
            
            # Clean up whitespace
            rendered = re.sub(r'\n\s*\n', '\n\n', rendered.strip())
            
            return OperationResult.success_result(data=rendered)
            
        except TemplateError as e:
            return OperationResult.error_result(
                error=f"Template rendering failed: {str(e)}",
                error_code="TEMPLATE_RENDER_ERROR"
            )
        except Exception as e:
            return OperationResult.error_result(
                error=f"Template processing failed: {str(e)}",
                error_code="TEMPLATE_PROCESSING_ERROR"
            )
    
    def get_available_templates(self) -> Dict[str, Dict[str, Any]]:
        """Get list of available templates."""
        templates = {}
        
        # Add built-in templates
        for template_id, template_data in self.builtin_templates.items():
            templates[template_id] = {
                "id": template_id,
                "name": template_data["name"],
                "description": template_data["description"],
                "variables": template_data["variables"],
                "type": "builtin"
            }
        
        # Scan for custom templates
        for template_file in self.templates_dir.glob("*_subject.txt"):
            template_id = template_file.stem.replace("_subject", "")
            
            if template_id not in templates:
                templates[template_id] = {
                    "id": template_id,
                    "name": template_id.replace("_", " ").title(),
                    "description": "Custom template",
                    "variables": [],
                    "type": "custom"
                }
        
        return templates
    
    def validate_template(self, template_id: str) -> Dict[str, Any]:
        """Validate template completeness and syntax."""
        
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "missing_files": []
        }
        
        # Check required files
        required_files = [
            f"{template_id}_subject.txt",
            f"{template_id}_text.txt"
        ]
        
        optional_files = [
            f"{template_id}_html.html"
        ]
        
        for filename in required_files:
            file_path = self.templates_dir / filename
            if not file_path.exists():
                validation_result["missing_files"].append(filename)
                validation_result["errors"].append(f"Required template file missing: {filename}")
                validation_result["is_valid"] = False
        
        for filename in optional_files:
            file_path = self.templates_dir / filename
            if not file_path.exists():
                validation_result["warnings"].append(f"Optional template file missing: {filename}")
        
        # Validate template syntax
        for filename in required_files + optional_files:
            file_path = self.templates_dir / filename
            if file_path.exists():
                try:
                    template = self.jinja_env.get_template(filename)
                    # Try rendering with dummy context
                    dummy_context = {var: f"test_{var}" for var in ["business_name", "contact_name", "sender_name", "location"]}
                    template.render(**dummy_context)
                except TemplateError as e:
                    validation_result["errors"].append(f"Template syntax error in {filename}: {str(e)}")
                    validation_result["is_valid"] = False
                except Exception as e:
                    validation_result["warnings"].append(f"Template warning in {filename}: {str(e)}")
        
        return validation_result