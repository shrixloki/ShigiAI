"""
Agent Runner - Background execution with separate discovery and outreach modes.

Discovery and Outreach are SEPARATE operations:
- Discovery: Finds businesses, extracts data, creates PENDING leads
- Outreach: Sends emails ONLY to APPROVED leads

NO EMAILS ARE SENT WITHOUT HUMAN APPROVAL.
"""

import threading
import time
from datetime import datetime
from typing import Optional, Tuple

from config.settings import settings
from services.agent_state import agent_state_manager, AgentState
from modules.logger import action_logger


class AgentRunner:
    """
    Manages agent execution in background threads.
    Supports separate discovery and outreach modes.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused by default
        
        self.heartbeat_interval = 5
        self.pause_check_interval = 1
        self._initialized = True
        
        # Discovery parameters
        self._discovery_query = None
        self._discovery_location = None
        self._discovery_max_results = 50
    
    # --- Discovery Control ---
    
    def start_discovery(
        self,
        query: str,
        location: str,
        max_results: int = 50,
        controlled_by: str = "user"
    ) -> Tuple[bool, str]:
        """
        Start discovery mode. Finds businesses from maps.
        Only valid from idle state.
        """
        with self._lock:
            current_state = agent_state_manager.get_state()["state"]
            
            if current_state != AgentState.IDLE.value:
                return False, f"Cannot start discovery: agent is {current_state}"
            
            # Store discovery parameters
            self._discovery_query = query
            self._discovery_location = location
            self._discovery_max_results = max_results
            
            # Transition to discovering
            success, msg = agent_state_manager.transition(
                AgentState.DISCOVERING,
                controlled_by=controlled_by,
                reason=f"Discovery started: {query} in {location}",
                discovery_query=query,
                discovery_location=location
            )
            
            if not success:
                return False, msg
            
            # Reset events
            self._stop_event.clear()
            self._pause_event.set()
            
            # Start discovery thread
            self._thread = threading.Thread(target=self._run_discovery, daemon=True)
            self._thread.start()
            
            action_logger.info(f"Discovery started by {controlled_by}: {query} in {location}")
            return True, "Discovery started"
    
    def stop_discovery(self, controlled_by: str = "user") -> Tuple[bool, str]:
        """Stop discovery gracefully."""
        current_state = agent_state_manager.get_state()["state"]
        
        if current_state != AgentState.DISCOVERING.value:
            return False, f"Cannot stop discovery: agent is {current_state}"
        
        success, msg = agent_state_manager.transition(
            AgentState.STOPPING,
            controlled_by=controlled_by,
            reason="Discovery stop requested"
        )
        
        if success:
            self._stop_event.set()
            action_logger.info(f"Discovery stop requested by {controlled_by}")
        
        return success, msg
    
    # --- Outreach Control ---
    
    def start_outreach(self, controlled_by: str = "user") -> Tuple[bool, str]:
        """
        Start outreach mode. Sends emails to APPROVED leads only.
        Only valid from idle state.
        """
        with self._lock:
            current_state = agent_state_manager.get_state()["state"]
            
            if current_state != AgentState.IDLE.value:
                return False, f"Cannot start outreach: agent is {current_state}"
            
            # Check if there are approved leads
            from services.db_service import DatabaseService
            db = DatabaseService()
            approved_leads = db.get_approved_leads_for_outreach_sync()
            
            if not approved_leads:
                return False, "No approved leads ready for outreach"
            
            # Transition to outreach_running
            success, msg = agent_state_manager.transition(
                AgentState.OUTREACH_RUNNING,
                controlled_by=controlled_by,
                reason="Outreach started",
                current_task="Initializing outreach"
            )
            
            if not success:
                return False, msg
            
            # Reset events
            self._stop_event.clear()
            self._pause_event.set()
            
            # Start outreach thread
            self._thread = threading.Thread(target=self._run_outreach, daemon=True)
            self._thread.start()
            
            action_logger.info(f"Outreach started by {controlled_by}")
            return True, f"Outreach started with {len(approved_leads)} approved leads"
    
    def stop_outreach(self, controlled_by: str = "user") -> Tuple[bool, str]:
        """Stop outreach gracefully."""
        current_state = agent_state_manager.get_state()["state"]
        
        if current_state != AgentState.OUTREACH_RUNNING.value:
            return False, f"Cannot stop outreach: agent is {current_state}"
        
        success, msg = agent_state_manager.transition(
            AgentState.STOPPING,
            controlled_by=controlled_by,
            reason="Outreach stop requested"
        )
        
        if success:
            self._stop_event.set()
            action_logger.info(f"Outreach stop requested by {controlled_by}")
        
        return success, msg
    
    # --- Common Controls ---
    
    def pause(self, controlled_by: str = "user") -> Tuple[bool, str]:
        """Pause the agent. Valid from discovering or outreach_running."""
        current_state = agent_state_manager.get_state()["state"]
        
        if current_state not in (AgentState.DISCOVERING.value, AgentState.OUTREACH_RUNNING.value):
            return False, f"Cannot pause: agent is {current_state}"
        
        success, msg = agent_state_manager.transition(
            AgentState.PAUSED,
            controlled_by=controlled_by,
            reason="Agent paused"
        )
        
        if success:
            self._pause_event.clear()
            action_logger.info(f"Agent paused by {controlled_by}")
        
        return success, msg
    
    def resume(self, controlled_by: str = "user") -> Tuple[bool, str]:
        """Resume the agent from paused state."""
        current_state = agent_state_manager.get_state()["state"]
        
        if current_state != AgentState.PAUSED.value:
            return False, f"Cannot resume: agent is {current_state}"
        
        # Determine what to resume to based on what was running
        state_data = agent_state_manager.get_state()
        if state_data.get("discovery_query"):
            new_state = AgentState.DISCOVERING
        else:
            new_state = AgentState.OUTREACH_RUNNING
        
        success, msg = agent_state_manager.transition(
            new_state,
            controlled_by=controlled_by,
            reason="Agent resumed"
        )
        
        if success:
            self._pause_event.set()
            action_logger.info(f"Agent resumed by {controlled_by}")
        
        return success, msg
    
    def stop(self, controlled_by: str = "user") -> Tuple[bool, str]:
        """Stop the agent from any running state."""
        current_state = agent_state_manager.get_state()["state"]
        
        if current_state not in (
            AgentState.DISCOVERING.value,
            AgentState.OUTREACH_RUNNING.value,
            AgentState.PAUSED.value
        ):
            return False, f"Cannot stop: agent is {current_state}"
        
        success, msg = agent_state_manager.transition(
            AgentState.STOPPING,
            controlled_by=controlled_by,
            reason="Stop requested"
        )
        
        if success:
            self._stop_event.set()
            self._pause_event.set()  # Unpause so it can exit
            action_logger.info(f"Agent stop requested by {controlled_by}")
        
        return success, msg
    
    def reset_from_error(self, controlled_by: str = "user") -> Tuple[bool, str]:
        """Reset agent from error state to idle."""
        current_state = agent_state_manager.get_state()["state"]
        
        if current_state != AgentState.ERROR.value:
            return False, f"Cannot reset: agent is {current_state}, not error"
        
        success, msg = agent_state_manager.transition(
            AgentState.IDLE,
            controlled_by=controlled_by,
            reason="Manual recovery from error"
        )
        
        if success:
            action_logger.info(f"Agent reset from error by {controlled_by}")
        
        return success, msg
    
    # --- Internal Methods ---
    
    def _should_stop(self) -> bool:
        """Check if stop has been requested."""
        if self._stop_event.is_set():
            return True
        state = agent_state_manager.get_state()["state"]
        return state == AgentState.STOPPING.value
    
    def _check_pause(self):
        """Block while paused, return True if should stop."""
        while not self._pause_event.is_set():
            if self._stop_event.is_set():
                return True
            time.sleep(self.pause_check_interval)
        return False
    
    def _run_discovery(self):
        """Discovery execution loop."""
        import asyncio
        
        try:
            from modules.hunter import HunterModule
            from modules.website_analyzer import WebsiteAnalyzerModule
            
            hunter = HunterModule()
            analyzer = WebsiteAnalyzerModule()
            
            agent_state_manager.update_heartbeat("Starting map discovery")
            
            # Run async discovery in sync thread
            result = asyncio.run(hunter.discover_from_maps(
                query=self._discovery_query,
                location=self._discovery_location,
                max_results=self._discovery_max_results,
                stop_check=self._should_stop
            ))
            
            if self._should_stop():
                self._finish_gracefully("Discovery stopped by user")
                return
            
            action_logger.info(f"Discovery complete: {result}")
            
            # Analyze websites for discovered leads
            agent_state_manager.update_heartbeat("Analyzing websites")
            
            analyze_result = asyncio.run(analyzer.analyze_all_pending(stop_check=self._should_stop))
            action_logger.info(f"Website analysis complete: {analyze_result}")
            
            self._finish_gracefully("Discovery completed successfully")
            
        except Exception as e:
            error_msg = f"Discovery crashed: {str(e)}"
            action_logger.error(error_msg)
            agent_state_manager.set_error(error_msg)
    
    def _run_outreach(self):
        """Outreach execution loop - sends emails to APPROVED leads only."""
        try:
            from modules import (
                ReplyDetectorModule,
                MessengerModule,
                FollowUpModule
            )
            from services.db_service import DatabaseService
            
            db = DatabaseService()
            
            while not self._should_stop():
                if self._check_pause():
                    break
                
                agent_state_manager.update_heartbeat("Checking for replies")
                
                # Step 1: Check for replies
                try:
                    detector = ReplyDetectorModule()
                    detector.check_all_replies()
                except Exception as e:
                    action_logger.error(f"Reply detection error: {e}")
                
                if self._should_stop():
                    break
                
                # Step 2: Send initial emails to APPROVED leads only
                agent_state_manager.update_heartbeat("Sending initial emails")
                
                try:
                    messenger = MessengerModule()
                    result = messenger.send_all_pending()
                    
                    if result.get("rate_limited"):
                        action_logger.info("Daily rate limit reached, stopping outreach")
                        break
                except Exception as e:
                    action_logger.error(f"Messenger error: {e}")
                
                if self._should_stop():
                    break
                
                # Step 3: Send follow-ups
                agent_state_manager.update_heartbeat("Sending follow-ups")
                
                try:
                    followup = FollowUpModule()
                    followup.send_all_followups()
                except Exception as e:
                    action_logger.error(f"Follow-up error: {e}")
                
                # Check if there's more work to do
                approved_pending = db.get_approved_leads_for_outreach_sync()
                followup_eligible = db.get_leads_for_followup_sync(settings.FOLLOWUP_DELAY_DAYS)
                
                if not approved_pending and not followup_eligible:
                    action_logger.info("No more leads to process, outreach complete")
                    break
                
                # Wait before next cycle
                agent_state_manager.update_heartbeat("Waiting for next cycle")
                for _ in range(60):
                    if self._should_stop():
                        break
                    time.sleep(1)
            
            self._finish_gracefully("Outreach completed")
            
        except Exception as e:
            error_msg = f"Outreach crashed: {str(e)}"
            action_logger.error(error_msg)
            agent_state_manager.set_error(error_msg)
    
    def _finish_gracefully(self, reason: str):
        """Transition to idle state gracefully."""
        agent_state_manager.transition(
            AgentState.IDLE,
            controlled_by="system",
            reason=reason
        )
        action_logger.info(reason)


# Singleton instance
agent_runner = AgentRunner()
