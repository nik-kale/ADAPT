"""
Time-Window Based Event Grouping

Provides algorithms for grouping events into incidents based on temporal proximity
and other affinity metrics (service, severity, etc.).
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from enum import Enum

from core.signal_normalizer import NormalizedSignal


class GroupingStrategy(str, Enum):
    """Grouping strategies for events"""
    TIME_WINDOW = "time_window"  # Group by time proximity
    SERVICE_AFFINITY = "service_affinity"  # Group by service + time
    SEVERITY_AFFINITY = "severity_affinity"  # Group by severity + time
    SLIDING_WINDOW = "sliding_window"  # Sliding window with overlap


@dataclass
class EventGroup:
    """
    A group of related events representing a potential incident.
    
    Attributes:
        id: Unique identifier for the group
        events: List of events in this group
        start_time: Earliest event timestamp
        end_time: Latest event timestamp
        services: Set of services involved
        severity: Highest severity in group
        tags: Common tags across events
        metadata: Additional group metadata
    """
    id: str
    events: List[NormalizedSignal] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    services: Set[str] = field(default_factory=set)
    severity: str = "medium"
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_event(self, event: NormalizedSignal) -> None:
        """
        Add an event to this group and update metadata.
        
        Args:
            event: Event to add
        """
        self.events.append(event)
        self.services.add(event.source)
        
        # Update time window
        if self.start_time is None or event.timestamp < self.start_time:
            self.start_time = event.timestamp
        if self.end_time is None or event.timestamp > self.end_time:
            self.end_time = event.timestamp
        
        # Update severity (keep highest)
        severity_order = ['low', 'medium', 'high', 'critical']
        if event.severity in severity_order:
            current_idx = severity_order.index(self.severity) if self.severity in severity_order else 1
            event_idx = severity_order.index(event.severity)
            if event_idx > current_idx:
                self.severity = event.severity
    
    def duration_minutes(self) -> float:
        """Get duration of event group in minutes"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() / 60
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event group to dictionary"""
        return {
            'id': self.id,
            'event_count': len(self.events),
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_minutes': round(self.duration_minutes(), 2),
            'services': list(self.services),
            'severity': self.severity,
            'tags': self.tags,
            'metadata': self.metadata,
        }


class EventGrouper:
    """
    Groups events into incidents based on configurable strategies.
    
    Features:
    - Time-window based grouping
    - Service affinity grouping
    - Sliding window with overlap
    - Configurable time windows
    """
    
    def __init__(
        self,
        time_window_minutes: int = 15,
        strategy: GroupingStrategy = GroupingStrategy.TIME_WINDOW,
        service_affinity: bool = False,
        min_events_per_group: int = 1
    ):
        """
        Initialize event grouper.
        
        Args:
            time_window_minutes: Maximum time gap between events in same group
            strategy: Grouping strategy to use
            service_affinity: Group by service in addition to time
            min_events_per_group: Minimum events required to form a group
        """
        self.time_window_minutes = time_window_minutes
        self.strategy = strategy
        self.service_affinity = service_affinity
        self.min_events_per_group = min_events_per_group
    
    def group_events(self, events: List[NormalizedSignal]) -> List[EventGroup]:
        """
        Group events into incidents.
        
        Args:
            events: List of events to group
            
        Returns:
            List of event groups
        """
        if not events:
            return []
        
        # Sort events by timestamp
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        
        if self.strategy == GroupingStrategy.TIME_WINDOW:
            return self._group_by_time_window(sorted_events)
        elif self.strategy == GroupingStrategy.SERVICE_AFFINITY:
            return self._group_by_service_affinity(sorted_events)
        elif self.strategy == GroupingStrategy.SLIDING_WINDOW:
            return self._group_by_sliding_window(sorted_events)
        else:
            return self._group_by_time_window(sorted_events)
    
    def _group_by_time_window(self, events: List[NormalizedSignal]) -> List[EventGroup]:
        """
        Group events based on time window proximity.
        
        Events within time_window_minutes of each other belong to same group.
        
        Args:
            events: Sorted list of events
            
        Returns:
            List of event groups
        """
        groups: List[EventGroup] = []
        current_group: Optional[EventGroup] = None
        time_window = timedelta(minutes=self.time_window_minutes)
        
        for event in events:
            if current_group is None:
                # Start new group
                current_group = EventGroup(id=f"group_{len(groups)}")
                current_group.add_event(event)
            else:
                # Check if event fits in current group
                time_diff = event.timestamp - current_group.end_time
                
                if time_diff <= time_window:
                    # Add to current group
                    current_group.add_event(event)
                else:
                    # Close current group and start new one
                    if len(current_group.events) >= self.min_events_per_group:
                        groups.append(current_group)
                    
                    current_group = EventGroup(id=f"group_{len(groups)}")
                    current_group.add_event(event)
        
        # Add last group
        if current_group and len(current_group.events) >= self.min_events_per_group:
            groups.append(current_group)
        
        return groups
    
    def _group_by_service_affinity(self, events: List[NormalizedSignal]) -> List[EventGroup]:
        """
        Group events by both time window and service.
        
        Events must be within time window AND from same service to group together.
        
        Args:
            events: Sorted list of events
            
        Returns:
            List of event groups
        """
        # Group events by service first
        service_events: Dict[str, List[NormalizedSignal]] = {}
        for event in events:
            service = event.source
            if service not in service_events:
                service_events[service] = []
            service_events[service].append(event)
        
        # Apply time-window grouping within each service
        all_groups: List[EventGroup] = []
        for service, service_event_list in service_events.items():
            service_groups = self._group_by_time_window(service_event_list)
            for group in service_groups:
                group.id = f"group_{service}_{len(all_groups)}"
                group.metadata['service_affinity'] = service
                all_groups.append(group)
        
        # Sort groups by start time
        all_groups.sort(key=lambda g: g.start_time or datetime.min)
        
        return all_groups
    
    def _group_by_sliding_window(self, events: List[NormalizedSignal]) -> List[EventGroup]:
        """
        Group events using sliding window with potential overlap.
        
        Each event starts a potential new group, collecting all events
        within the time window.
        
        Args:
            events: Sorted list of events
            
        Returns:
            List of event groups (may have overlapping events)
        """
        groups: List[EventGroup] = []
        time_window = timedelta(minutes=self.time_window_minutes)
        
        for i, event in enumerate(events):
            # Create group starting at this event
            group = EventGroup(id=f"group_{i}")
            group.add_event(event)
            
            # Add all events within time window
            for future_event in events[i+1:]:
                if future_event.timestamp - event.timestamp <= time_window:
                    group.add_event(future_event)
                else:
                    break  # Events are sorted, so we can stop
            
            # Only add groups that meet minimum size
            if len(group.events) >= self.min_events_per_group:
                groups.append(group)
        
        return groups
    
    def merge_overlapping_groups(self, groups: List[EventGroup]) -> List[EventGroup]:
        """
        Merge groups that have overlapping time windows.
        
        Args:
            groups: List of event groups
            
        Returns:
            List of merged groups
        """
        if not groups:
            return []
        
        # Sort groups by start time
        sorted_groups = sorted(groups, key=lambda g: g.start_time or datetime.min)
        
        merged: List[EventGroup] = []
        current = sorted_groups[0]
        
        for next_group in sorted_groups[1:]:
            # Check for overlap
            if next_group.start_time and current.end_time:
                if next_group.start_time <= current.end_time:
                    # Merge groups
                    for event in next_group.events:
                        if event not in current.events:
                            current.add_event(event)
                else:
                    # No overlap, save current and move to next
                    merged.append(current)
                    current = next_group
            else:
                merged.append(current)
                current = next_group
        
        # Add last group
        merged.append(current)
        
        return merged


def group_events_by_time_window(
    events: List[NormalizedSignal],
    time_window_minutes: int = 15,
    service_affinity: bool = False
) -> List[EventGroup]:
    """
    Convenience function to group events by time window.
    
    Args:
        events: List of events to group
        time_window_minutes: Maximum time gap between events
        service_affinity: Whether to group by service as well
        
    Returns:
        List of event groups
    """
    strategy = (
        GroupingStrategy.SERVICE_AFFINITY if service_affinity
        else GroupingStrategy.TIME_WINDOW
    )
    
    grouper = EventGrouper(
        time_window_minutes=time_window_minutes,
        strategy=strategy
    )
    
    return grouper.group_events(events)

