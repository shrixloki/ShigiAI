"""
Scout Module - Lead ingestion from CSV or manual input.

All imported leads start with review_status='pending'.
NO EMAILS ARE SENT BY THIS MODULE.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from modules.logger import action_logger
from services.db_service import DatabaseService


class ScoutModule:
    """
    Imports and prepares leads from CSV or manual input.
    All leads start as PENDING - requires approval before outreach.
    """
    
    REQUIRED_FIELDS = ["business_name", "email"]
    OPTIONAL_FIELDS = ["category", "location", "website_url", "maps_url"]
    
    def __init__(self):
        self.db = DatabaseService()
    
    def import_from_csv(self, csv_path: str) -> dict:
        """
        Import leads from a CSV file.
        All imported leads get review_status='pending'.
        
        Returns:
            {imported: int, skipped: int, errors: list}
        """
        path = Path(csv_path)
        if not path.exists():
            action_logger.error(f"CSV file not found: {csv_path}")
            return {"imported": 0, "skipped": 0, "errors": [f"File not found: {csv_path}"]}
        
        imported = 0
        skipped = 0
        errors = []
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                
                for row_num, row in enumerate(reader, start=2):
                    result = self._process_lead(row, row_num)
                    
                    if result == "imported":
                        imported += 1
                    elif result == "skipped":
                        skipped += 1
                    else:
                        errors.append(result)
        
        except Exception as e:
            errors.append(f"CSV read error: {str(e)}")
        
        action_logger.log_action(
            lead_id=None,
            module_name="scout",
            action="import_csv",
            result="success" if imported > 0 else "warning",
            details={
                "file": csv_path,
                "imported": imported,
                "skipped": skipped,
                "errors": len(errors)
            }
        )
        
        return {"imported": imported, "skipped": skipped, "errors": errors}
    
    def _process_lead(self, row: dict, row_num: int) -> str:
        """
        Process a single lead row.
        Returns: "imported", "skipped", or error message
        """
        # Normalize keys to lowercase
        row = {k.lower().strip(): v.strip() for k, v in row.items()}
        
        # Validate required fields
        for field in self.REQUIRED_FIELDS:
            if not row.get(field):
                return f"Row {row_num}: Missing required field '{field}'"
        
        email = row["email"].lower()
        
        # Validate email format (basic check)
        if "@" not in email or "." not in email:
            return f"Row {row_num}: Invalid email format '{email}'"
        
        # Check for duplicates
        if self.db.lead_exists_by_email(email):
            action_logger.log_action(
                lead_id=email,
                module_name="scout",
                action="import",
                result="skipped",
                details={"reason": "duplicate email"}
            )
            return "skipped"
        
        # Prepare lead data - ALL LEADS START AS PENDING
        lead_data = {
            "business_name": row["business_name"],
            "email": email,
            "category": row.get("category", ""),
            "location": row.get("location", ""),
            "website_url": row.get("website_url", row.get("website", "")),
            "maps_url": row.get("maps_url", ""),
            "discovery_source": "csv",
            "discovery_confidence": "medium",
            "tag": "unknown",
            "review_status": "pending",  # CRITICAL: Always pending
            "outreach_status": "not_sent",
            "discovered_at": datetime.now().isoformat(),
            "notes": ""
        }
        
        # Add to database
        try:
            lead_id = self.db.add_lead(lead_data)
            action_logger.log_action(
                lead_id=lead_id,
                module_name="scout",
                action="import",
                result="success",
                details={"email": email, "business": row["business_name"]}
            )
            return "imported"
        except Exception as e:
            return f"Row {row_num}: Failed to add lead - {str(e)}"
    
    def add_single_lead(
        self,
        business_name: str,
        email: str,
        category: Optional[str] = None,
        location: Optional[str] = None,
        website_url: Optional[str] = None,
        maps_url: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Add a single lead manually.
        Lead starts with review_status='pending'.
        
        Returns:
            (success, message)
        """
        email = email.lower().strip()
        
        if self.db.lead_exists_by_email(email):
            return False, "Lead with this email already exists"
        
        lead_data = {
            "business_name": business_name.strip(),
            "email": email,
            "category": category or "",
            "location": location or "",
            "website_url": website_url or "",
            "maps_url": maps_url or "",
            "discovery_source": "manual",
            "discovery_confidence": "high",
            "tag": "unknown",
            "review_status": "pending",  # CRITICAL: Always pending
            "outreach_status": "not_sent",
            "discovered_at": datetime.now().isoformat()
        }
        
        try:
            lead_id = self.db.add_lead(lead_data)
            action_logger.log_action(
                lead_id=lead_id,
                module_name="scout",
                action="manual_add",
                result="success",
                details={"email": email}
            )
            return True, f"Lead added with ID: {lead_id} (pending review)"
        except Exception as e:
            return False, str(e)
