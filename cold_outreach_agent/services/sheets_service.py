"""Google Sheets service for lead data management."""

import uuid
from datetime import datetime
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from config.settings import settings


# Required columns in the sheet
REQUIRED_COLUMNS = [
    "lead_id", "business_name", "category", "location", "website", 
    "email", "tag", "status", "follow_up_sent", "last_contacted", "notes"
]


class SheetsService:
    """Handles all Google Sheets operations."""
    
    def __init__(self):
        self._client: Optional[gspread.Client] = None
        self._sheet: Optional[gspread.Worksheet] = None
    
    def _connect(self):
        """Establish connection to Google Sheets."""
        if self._client is not None:
            return
        
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        creds = Credentials.from_service_account_file(
            settings.GOOGLE_CREDENTIALS_PATH,
            scopes=scopes
        )
        self._client = gspread.authorize(creds)
        spreadsheet = self._client.open_by_key(settings.GOOGLE_SHEETS_ID)
        self._sheet = spreadsheet.sheet1
    
    @property
    def sheet(self) -> gspread.Worksheet:
        """Get the worksheet, connecting if needed."""
        if self._sheet is None:
            self._connect()
        return self._sheet
    
    def get_all_leads(self) -> list[dict]:
        """Fetch all leads from the sheet."""
        records = self.sheet.get_all_records()
        return records
    
    def get_leads_by_status(self, status: str) -> list[dict]:
        """Get leads filtered by status."""
        all_leads = self.get_all_leads()
        return [lead for lead in all_leads if lead.get("status") == status]
    
    def get_leads_without_tag(self) -> list[dict]:
        """Get leads that haven't been classified yet."""
        all_leads = self.get_all_leads()
        return [lead for lead in all_leads if not lead.get("tag")]
    
    def get_leads_for_followup(self, delay_days: int) -> list[dict]:
        """Get leads eligible for follow-up."""
        all_leads = self.get_all_leads()
        eligible = []
        
        for lead in all_leads:
            if lead.get("status") != "sent_initial":
                continue
            if str(lead.get("follow_up_sent", "")).lower() == "true":
                continue
            
            last_contacted = lead.get("last_contacted")
            if not last_contacted:
                continue
            
            try:
                contact_date = datetime.fromisoformat(last_contacted)
                days_since = (datetime.now() - contact_date).days
                if days_since >= delay_days:
                    eligible.append(lead)
            except ValueError:
                continue
        
        return eligible
    
    def find_row_by_lead_id(self, lead_id: str) -> Optional[int]:
        """Find the row number for a lead_id (1-indexed, includes header)."""
        try:
            cell = self.sheet.find(lead_id, in_column=1)
            return cell.row if cell else None
        except gspread.exceptions.CellNotFound:
            return None
    
    def update_lead(self, lead_id: str, updates: dict) -> bool:
        """Update specific fields for a lead."""
        row = self.find_row_by_lead_id(lead_id)
        if not row:
            return False
        
        headers = self.sheet.row_values(1)
        
        for field, value in updates.items():
            if field in headers:
                col = headers.index(field) + 1
                self.sheet.update_cell(row, col, value)
        
        return True
    
    def add_lead(self, lead_data: dict) -> str:
        """Add a new lead to the sheet. Returns the lead_id."""
        headers = self.sheet.row_values(1)
        
        # Generate lead_id if not provided
        lead_id = lead_data.get("lead_id") or str(uuid.uuid4())[:8]
        lead_data["lead_id"] = lead_id
        
        # Set defaults
        lead_data.setdefault("status", "not_sent")
        lead_data.setdefault("follow_up_sent", "false")
        lead_data.setdefault("tag", "")
        lead_data.setdefault("last_contacted", "")
        lead_data.setdefault("notes", "")
        
        # Build row in correct column order
        row = [lead_data.get(col, "") for col in headers]
        self.sheet.append_row(row)
        
        return lead_id
    
    def lead_exists(self, email: str) -> bool:
        """Check if a lead with this email already exists."""
        try:
            cell = self.sheet.find(email, in_column=6)  # email is column 6
            return cell is not None
        except gspread.exceptions.CellNotFound:
            return False
    
    def get_emails_sent_today(self) -> int:
        """Count emails sent today for rate limiting."""
        today = datetime.now().strftime("%Y-%m-%d")
        all_leads = self.get_all_leads()
        
        count = 0
        for lead in all_leads:
            last_contacted = lead.get("last_contacted", "")
            if last_contacted.startswith(today):
                count += 1
        
        return count
