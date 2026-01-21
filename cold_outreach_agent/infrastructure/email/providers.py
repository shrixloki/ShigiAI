"""Production-grade email providers with failover and retry logic."""

import asyncio
import smtplib
import ssl
from abc import ABC, abstractmethod
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional

import aiosmtplib
from email.message import EmailMessage

from ...core.models.common import OperationResult
from ...core.exceptions import EmailProviderError, ConfigurationError


class EmailProvider(ABC):
    """Abstract base class for email providers."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__.replace('Provider', '').lower()
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self):
        """Validate provider configuration."""
        pass
    
    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        to_name: Optional[str],
        from_email: str,
        from_name: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None
    ) -> OperationResult[Dict[str, Any]]:
        """Send email and return result with message ID."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available and configured."""
        pass
    
    @abstractmethod
    def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary (without sensitive data)."""
        pass


class SMTPProvider(EmailProvider):
    """SMTP email provider with async support."""
    
    def _validate_config(self):
        """Validate SMTP configuration."""
        required_fields = ['host', 'port', 'username', 'password']
        missing_fields = [field for field in required_fields if not self.config.get(field)]
        
        if missing_fields:
            raise ConfigurationError(
                f"SMTP provider missing required configuration: {', '.join(missing_fields)}"
            )
        
        # Validate port
        try:
            port = int(self.config['port'])
            if not (1 <= port <= 65535):
                raise ValueError("Port must be between 1 and 65535")
        except (ValueError, TypeError):
            raise ConfigurationError("SMTP port must be a valid integer")
    
    async def send_email(
        self,
        to_email: str,
        to_name: Optional[str],
        from_email: str,
        from_name: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None
    ) -> OperationResult[Dict[str, Any]]:
        """Send email via SMTP."""
        
        try:
            # Create message
            message = EmailMessage()
            message['Subject'] = subject
            message['From'] = f"{from_name} <{from_email}>"
            message['To'] = f"{to_name} <{to_email}>" if to_name else to_email
            message['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
            message['Message-ID'] = f"<{datetime.now().timestamp()}@{self.config['host']}>"
            
            # Set body content
            message.set_content(body_text)
            
            if body_html:
                message.add_alternative(body_html, subtype='html')
            
            # Send via SMTP
            smtp_config = {
                'hostname': self.config['host'],
                'port': int(self.config['port']),
                'username': self.config['username'],
                'password': self.config['password'],
                'use_tls': self.config.get('use_tls', True),
                'start_tls': self.config.get('start_tls', True),
                'timeout': self.config.get('timeout', 60)
            }
            
            await aiosmtplib.send(
                message,
                **smtp_config
            )
            
            return OperationResult.success_result(
                data={
                    'message_id': message['Message-ID'],
                    'provider': self.name,
                    'sent_at': datetime.now().isoformat(),
                    'to_email': to_email,
                    'subject': subject
                }
            )
            
        except aiosmtplib.SMTPException as e:
            return OperationResult.error_result(
                error=f"SMTP error: {str(e)}",
                error_code="SMTP_ERROR"
            )
        except Exception as e:
            return OperationResult.error_result(
                error=f"Email sending failed: {str(e)}",
                error_code="SEND_ERROR"
            )
    
    def is_available(self) -> bool:
        """Check if SMTP provider is available."""
        try:
            required_fields = ['host', 'port', 'username', 'password']
            return all(self.config.get(field) for field in required_fields)
        except Exception:
            return False
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get SMTP configuration summary."""
        return {
            'provider': self.name,
            'host': self.config.get('host'),
            'port': self.config.get('port'),
            'username': self.config.get('username'),
            'use_tls': self.config.get('use_tls', True),
            'configured': self.is_available()
        }


class GmailAPIProvider(EmailProvider):
    """Gmail API provider (placeholder for future implementation)."""
    
    def _validate_config(self):
        """Validate Gmail API configuration."""
        required_fields = ['credentials_path']
        missing_fields = [field for field in required_fields if not self.config.get(field)]
        
        if missing_fields:
            raise ConfigurationError(
                f"Gmail API provider missing required configuration: {', '.join(missing_fields)}"
            )
    
    async def send_email(
        self,
        to_email: str,
        to_name: Optional[str],
        from_email: str,
        from_name: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None
    ) -> OperationResult[Dict[str, Any]]:
        """Send email via Gmail API."""
        
        # TODO: Implement Gmail API integration
        # This would require:
        # 1. Google API client library
        # 2. OAuth2 authentication
        # 3. Gmail API service setup
        # 4. Message creation and sending
        
        return OperationResult.error_result(
            error="Gmail API provider not yet implemented",
            error_code="NOT_IMPLEMENTED"
        )
    
    def is_available(self) -> bool:
        """Check if Gmail API provider is available."""
        # TODO: Check if credentials file exists and is valid
        return False
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get Gmail API configuration summary."""
        return {
            'provider': self.name,
            'credentials_path': self.config.get('credentials_path'),
            'configured': self.is_available(),
            'status': 'not_implemented'
        }


class MockEmailProvider(EmailProvider):
    """Mock email provider for testing and development."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.sent_emails = []
    
    def _validate_config(self):
        """Mock provider doesn't require configuration."""
        pass
    
    async def send_email(
        self,
        to_email: str,
        to_name: Optional[str],
        from_email: str,
        from_name: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None
    ) -> OperationResult[Dict[str, Any]]:
        """Mock email sending."""
        
        # Simulate network delay
        await asyncio.sleep(0.1)
        
        # Simulate occasional failures for testing
        if self.config.get('simulate_failures', False) and len(self.sent_emails) % 10 == 9:
            return OperationResult.error_result(
                error="Simulated email failure",
                error_code="SIMULATED_FAILURE"
            )
        
        # Record sent email
        email_record = {
            'message_id': f"mock_{datetime.now().timestamp()}",
            'to_email': to_email,
            'to_name': to_name,
            'from_email': from_email,
            'from_name': from_name,
            'subject': subject,
            'body_text': body_text,
            'body_html': body_html,
            'sent_at': datetime.now().isoformat(),
            'provider': self.name
        }
        
        self.sent_emails.append(email_record)
        
        return OperationResult.success_result(data=email_record)
    
    def is_available(self) -> bool:
        """Mock provider is always available."""
        return True
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get mock provider configuration summary."""
        return {
            'provider': self.name,
            'configured': True,
            'sent_count': len(self.sent_emails),
            'simulate_failures': self.config.get('simulate_failures', False)
        }
    
    def get_sent_emails(self) -> list:
        """Get list of sent emails (for testing)."""
        return self.sent_emails.copy()
    
    def clear_sent_emails(self):
        """Clear sent emails list (for testing)."""
        self.sent_emails.clear()


class EmailProviderFactory:
    """Factory for creating email providers."""
    
    PROVIDERS = {
        'smtp': SMTPProvider,
        'gmail_api': GmailAPIProvider,
        'mock': MockEmailProvider
    }
    
    @classmethod
    def create_provider(cls, provider_type: str, config: Dict[str, Any]) -> EmailProvider:
        """Create email provider instance."""
        
        if provider_type not in cls.PROVIDERS:
            raise ConfigurationError(
                f"Unknown email provider type: {provider_type}. "
                f"Available providers: {', '.join(cls.PROVIDERS.keys())}"
            )
        
        provider_class = cls.PROVIDERS[provider_type]
        
        try:
            return provider_class(config)
        except Exception as e:
            raise ConfigurationError(
                f"Failed to create {provider_type} provider: {str(e)}"
            )
    
    @classmethod
    def get_available_providers(cls) -> list:
        """Get list of available provider types."""
        return list(cls.PROVIDERS.keys())


class EmailProviderManager:
    """Manages multiple email providers with failover."""
    
    def __init__(self):
        self.providers: Dict[str, EmailProvider] = {}
        self.primary_provider: Optional[str] = None
        self.failover_order: list = []
    
    def add_provider(self, name: str, provider: EmailProvider, is_primary: bool = False):
        """Add email provider."""
        self.providers[name] = provider
        
        if is_primary or not self.primary_provider:
            self.primary_provider = name
        
        if name not in self.failover_order:
            self.failover_order.append(name)
    
    def remove_provider(self, name: str):
        """Remove email provider."""
        if name in self.providers:
            del self.providers[name]
        
        if name in self.failover_order:
            self.failover_order.remove(name)
        
        if self.primary_provider == name:
            self.primary_provider = self.failover_order[0] if self.failover_order else None
    
    def get_provider(self, name: Optional[str] = None) -> Optional[EmailProvider]:
        """Get email provider by name or primary."""
        if name:
            return self.providers.get(name)
        
        if self.primary_provider:
            return self.providers.get(self.primary_provider)
        
        return None
    
    async def send_email_with_failover(
        self,
        to_email: str,
        to_name: Optional[str],
        from_email: str,
        from_name: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        preferred_provider: Optional[str] = None
    ) -> OperationResult[Dict[str, Any]]:
        """Send email with automatic failover to backup providers."""
        
        # Determine provider order
        provider_order = []
        
        if preferred_provider and preferred_provider in self.providers:
            provider_order.append(preferred_provider)
        
        # Add other providers in failover order
        for provider_name in self.failover_order:
            if provider_name not in provider_order:
                provider_order.append(provider_name)
        
        if not provider_order:
            return OperationResult.error_result(
                error="No email providers available",
                error_code="NO_PROVIDERS"
            )
        
        # Try providers in order
        last_error = None
        
        for provider_name in provider_order:
            provider = self.providers.get(provider_name)
            
            if not provider or not provider.is_available():
                continue
            
            try:
                result = await provider.send_email(
                    to_email=to_email,
                    to_name=to_name,
                    from_email=from_email,
                    from_name=from_name,
                    subject=subject,
                    body_text=body_text,
                    body_html=body_html
                )
                
                if result.success:
                    # Add provider info to result
                    result.metadata['provider_used'] = provider_name
                    result.metadata['failover_attempted'] = len(provider_order) > 1
                    return result
                else:
                    last_error = result.error
            
            except Exception as e:
                last_error = str(e)
                continue
        
        return OperationResult.error_result(
            error=f"All email providers failed. Last error: {last_error}",
            error_code="ALL_PROVIDERS_FAILED"
        )
    
    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all providers."""
        status = {}
        
        for name, provider in self.providers.items():
            status[name] = {
                'available': provider.is_available(),
                'is_primary': name == self.primary_provider,
                'config': provider.get_config_summary()
            }
        
        return status