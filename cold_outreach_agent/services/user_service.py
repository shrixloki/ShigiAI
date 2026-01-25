"""User and role management service."""

import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from ..core.models.users import (
    User, UserRole, Permission, ROLE_PERMISSIONS, LeadAssignment,
    ApprovalDelegation, UserActivityLog, UserSession, UserCreate,
    UserUpdate, AssignLeadRequest, DelegateApprovalRequest
)
from ..core.exceptions import ColdOutreachAgentError
from ..modules.logger import action_logger


class UserError(ColdOutreachAgentError):
    """User operation failed."""
    pass


class UserService:
    """
    Service for user management, authentication, and authorization.
    
    Features:
    - User CRUD
    - Role-based access control (RBAC)
    - Session management
    - Lead assignment
    - Approval delegation
    - Activity logging
    """
    
    def __init__(self, db_service):
        self.db = db_service
        
        self._users: Dict[str, User] = {}
        self._sessions: Dict[str, UserSession] = {}
        self._assignments: List[LeadAssignment] = []
        self._delegations: List[ApprovalDelegation] = []
        
        # Initialize default admin if no users exist
        self._ensure_default_admin()
    
    def _ensure_default_admin(self):
        """Create default admin user if none exists."""
        if not self._users:
            admin_id = uuid4()
            admin = User(
                id=admin_id,
                email="admin@example.com",
                username="admin",
                display_name="System Administrator",
                role=UserRole.ADMIN,
                password_hash=self._hash_password("admin123"),  # Change in production!
                is_active=True,
                is_email_verified=True
            )
            self._users[str(admin.id)] = admin
    
    def _hash_password(self, password: str) -> str:
        """Hash a password (placeholder implementation)."""
        # In production: use bcrypt or argon2
        return hashlib.sha256(password.encode()).hexdigest()
    
    async def create_user(self, request: UserCreate, creator_id: str) -> User:
        """
        Create a new user.
        
        Args:
            request: User creation request
            creator_id: ID of user creating the account
        
        Returns:
            Created User
        """
        # Check permissions
        if not await self.check_permission(creator_id, Permission.MANAGE_USERS):
            raise UserError("Insufficient permissions to create user")
        
        # Check email uniqueness
        for user in self._users.values():
            if user.email.lower() == request.email.lower():
                raise UserError("Email already in use")
        
        user_id = str(UUID(int=secrets.token_hex(16))) if not getattr(request, 'id', None) else request.id
        
        user = User(
            id=user_id,
            email=request.email,
            name=request.name,
            role=request.role,
            password_hash=self._hash_password(request.password),
            is_active=True
        )
        
        self._users[user.id] = user
        
        action_logger.log_action(
            lead_id=None,
            module_name="users",
            action="create_user",
            result="success",
            details={"new_user_id": user.id, "role": user.role.value}
        )
        
        return user
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        return self._users.get(user_id)
    
    async def list_users(self) -> List[User]:
        """List all users."""
        return list(self._users.values())
    
    async def update_user(self, user_id: str, update: UserUpdate,
                           updater_id: str) -> Optional[User]:
        """Update a user."""
        # Check permissions
        if updater_id != user_id and not await self.check_permission(updater_id, Permission.MANAGE_USERS):
            raise UserError("Insufficient permissions to update user")
        
        user = self._users.get(user_id)
        if not user:
            return None
        
        if update.name is not None:
            user.name = update.name
        if update.role is not None:
            # Only existing admins can change roles
            if await self.check_permission(updater_id, Permission.MANAGE_USERS):
                user.role = update.role
        if update.is_active is not None:
            if await self.check_permission(updater_id, Permission.MANAGE_USERS):
                user.is_active = update.is_active
        if update.password is not None:
            user.password_hash = self._hash_password(update.password)
        
        user.updated_at = datetime.now()
        
        return user
    
    async def authenticate(self, email: str, password: str) -> Optional[UserSession]:
        """
        Authenticate a user and create session.
        
        Args:
            email: User email
            password: User password
        
        Returns:
            UserSession if successful, None otherwise
        """
        user = next((u for u in self._users.values() if u.email.lower() == email.lower()), None)
        
        if not user or not user.is_active:
            return None
        
        if user.password_hash != self._hash_password(password):
            user.failed_login_attempts += 1
            return None
        
        # Successful login
        user.last_login_at = datetime.now()
        user.failed_login_attempts = 0
        
        # Create session
        token = secrets.token_urlsafe(32)
        session = UserSession(
            token=token,
            user_id=user.id,
            expires_at=datetime.now() + timedelta(hours=24),
            ip_address="127.0.0.1",  # Placeholder
            user_agent="Unknown"  # Placeholder
        )
        
        self._sessions[token] = session
        
        return session
    
    async def get_session(self, token: str) -> Optional[UserSession]:
        """Get valid session by token."""
        session = self._sessions.get(token)
        if not session:
            return None
        
        if not session.is_valid():
            del self._sessions[token]
            return None
        
        # Extend session
        session.last_active_at = datetime.now()
        return session
    
    async def logout(self, token: str):
        """Invalidate a session."""
        if token in self._sessions:
            del self._sessions[token]
    
    async def check_permission(self, user_id: str, permission: Permission) -> bool:
        """Check if user has permission."""
        user = self._users.get(user_id)
        if not user or not user.is_active:
            return False
        
        user_permissions = ROLE_PERMISSIONS.get(user.role, set())
        return permission in user_permissions
    
    async def assign_lead(self, request: AssignLeadRequest, assigner_id: str) -> LeadAssignment:
        """
        Assign a lead to a user.
        
        Args:
            request: Assignment request
            assigner_id: User making assignment
        
        Returns:
            Created LeadAssignment
        """
        assignment = LeadAssignment(
            lead_id=request.lead_id,
            assigned_to=request.assigned_to,
            assigned_by=assigner_id,
            role=request.role,
            reason=request.reason
        )
        
        self._assignments.append(assignment)
        
        # In production: update lead record
        
        action_logger.log_action(
            lead_id=str(request.lead_id),
            module_name="users",
            action="assign_lead",
            result="success",
            details={
                "assigned_to": request.assigned_to,
                "role": request.role
            }
        )
        
        return assignment
    
    async def get_lead_assignments(self, lead_id: UUID) -> List[LeadAssignment]:
        """Get assignments for a lead."""
        return [a for a in self._assignments if a.lead_id == lead_id and a.is_active]
    
    async def get_user_assignments(self, user_id: str) -> List[LeadAssignment]:
        """Get assignments for a user."""
        return [a for a in self._assignments if a.assigned_to == user_id and a.is_active]
    
    async def delegate_approval(self, request: DelegateApprovalRequest,
                                 delegator_id: str) -> ApprovalDelegation:
        """
        Delegate approval authority.
        
        Args:
            request: Delegation request
            delegator_id: User delegating authority
        
        Returns:
            Created ApprovalDelegation
        """
        delegation = ApprovalDelegation(
            delegator_id=delegator_id,
            delegatee_id=request.delegatee_id,
            starts_at=request.starts_at or datetime.now(),
            ends_at=request.ends_at,
            reason=request.reason
        )
        
        self._delegations.append(delegation)
        
        action_logger.log_action(
            lead_id=None,
            module_name="users",
            action="delegate_approval",
            result="success",
            details={
                "delegatee": request.delegatee_id,
                "until": request.ends_at.isoformat() if request.ends_at else "indefinite"
            }
        )
        
        return delegation
    
    async def check_approval_authority(self, user_id: str) -> bool:
        """Check if user has approval authority (direct or delegated)."""
        # Check direct permission
        if await self.check_permission(user_id, Permission.APPROVE_LEADS):
            return True
        
        # Check active delegations
        now = datetime.now()
        active_delegation = next(
            (d for d in self._delegations 
             if d.delegatee_id == user_id 
             and d.is_active(now)
             and self.check_permission(d.delegator_id, Permission.APPROVE_LEADS)), # Check if delegator has permission
            None
        )
        
        return bool(active_delegation)
