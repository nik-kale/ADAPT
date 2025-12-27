"""
Tests for Time-Window Based Event Grouping
"""

import pytest
from datetime import datetime, timedelta
from typing import List

from core.event_grouping import (
    EventGrouper,
    EventGroup,
    GroupingStrategy,
    group_events_by_time_window
)
from core.signal_normalizer import NormalizedSignal, SignalType


def create_test_event(
    timestamp: datetime,
    source: str = "test-service",
    severity: str = "medium",
    title: str = "Test Event"
) -> NormalizedSignal:
    """Helper to create test events"""
    return NormalizedSignal(
        signal_type=SignalType.LOG,
        title=title,
        description="Test description",
        timestamp=timestamp,
        source=source,
        severity=severity
    )


class TestEventGroup:
    """Tests for EventGroup class"""

    def test_add_event_updates_metadata(self):
        """Test that adding events updates group metadata"""
        group = EventGroup(id="test")

        event1 = create_test_event(datetime(2024, 1, 1, 12, 0), source="service-a")
        event2 = create_test_event(datetime(2024, 1, 1, 12, 5), source="service-b")

        group.add_event(event1)
        group.add_event(event2)

        assert len(group.events) == 2
        assert "service-a" in group.services
        assert "service-b" in group.services
        assert group.start_time == datetime(2024, 1, 1, 12, 0)
        assert group.end_time == datetime(2024, 1, 1, 12, 5)

    def test_severity_escalation(self):
        """Test that group severity escalates to highest level"""
        group = EventGroup(id="test", severity="low")

        group.add_event(create_test_event(datetime.now(), severity="medium"))
        assert group.severity == "medium"

        group.add_event(create_test_event(datetime.now(), severity="critical"))
        assert group.severity == "critical"

        group.add_event(create_test_event(datetime.now(), severity="low"))
        assert group.severity == "critical"  # Should remain at highest

    def test_duration_calculation(self):
        """Test duration calculation in minutes"""
        group = EventGroup(id="test")

        group.add_event(create_test_event(datetime(2024, 1, 1, 12, 0)))
        group.add_event(create_test_event(datetime(2024, 1, 1, 12, 15)))

        assert group.duration_minutes() == 15.0

    def test_to_dict(self):
        """Test conversion to dictionary"""
        group = EventGroup(id="test")
        group.add_event(create_test_event(datetime(2024, 1, 1, 12, 0), source="service-a"))

        result = group.to_dict()

        assert result['id'] == "test"
        assert result['event_count'] == 1
        assert 'service-a' in result['services']
        assert 'start_time' in result
        assert 'end_time' in result


class TestEventGrouper:
    """Tests for EventGrouper class"""

    def test_empty_events(self):
        """Test grouping with no events"""
        grouper = EventGrouper()
        groups = grouper.group_events([])

        assert groups == []

    def test_single_event(self):
        """Test grouping with single event"""
        grouper = EventGrouper()
        events = [create_test_event(datetime.now())]

        groups = grouper.group_events(events)

        assert len(groups) == 1
        assert len(groups[0].events) == 1

    def test_time_window_grouping_within_window(self):
        """Test events within time window are grouped together"""
        grouper = EventGrouper(time_window_minutes=15)

        base_time = datetime(2024, 1, 1, 12, 0)
        events = [
            create_test_event(base_time),
            create_test_event(base_time + timedelta(minutes=5)),
            create_test_event(base_time + timedelta(minutes=10)),
        ]

        groups = grouper.group_events(events)

        assert len(groups) == 1
        assert len(groups[0].events) == 3

    def test_time_window_grouping_outside_window(self):
        """Test events outside time window create separate groups"""
        grouper = EventGrouper(time_window_minutes=15)

        base_time = datetime(2024, 1, 1, 12, 0)
        events = [
            create_test_event(base_time),
            create_test_event(base_time + timedelta(minutes=20)),  # Outside window
            create_test_event(base_time + timedelta(minutes=25)),
        ]

        groups = grouper.group_events(events)

        assert len(groups) == 2
        assert len(groups[0].events) == 1
        assert len(groups[1].events) == 2

    def test_service_affinity_grouping(self):
        """Test grouping by service affinity"""
        grouper = EventGrouper(
            time_window_minutes=15,
            strategy=GroupingStrategy.SERVICE_AFFINITY
        )

        base_time = datetime(2024, 1, 1, 12, 0)
        events = [
            create_test_event(base_time, source="service-a"),
            create_test_event(base_time + timedelta(minutes=5), source="service-b"),
            create_test_event(base_time + timedelta(minutes=10), source="service-a"),
        ]

        groups = grouper.group_events(events)

        # Should create 2 groups (one per service)
        assert len(groups) == 2

        # Check that each group has events from only one service
        for group in groups:
            assert len(group.services) == 1

    def test_min_events_per_group(self):
        """Test minimum events per group filter"""
        grouper = EventGrouper(
            time_window_minutes=15,
            min_events_per_group=2
        )

        base_time = datetime(2024, 1, 1, 12, 0)
        events = [
            create_test_event(base_time),
            create_test_event(base_time + timedelta(minutes=20)),  # Solo event
            create_test_event(base_time + timedelta(minutes=40)),
            create_test_event(base_time + timedelta(minutes=45)),
        ]

        groups = grouper.group_events(events)

        # Only groups with 2+ events should be included
        assert len(groups) == 1
        assert len(groups[0].events) == 2

    def test_sliding_window_strategy(self):
        """Test sliding window grouping creates overlapping groups"""
        grouper = EventGrouper(
            time_window_minutes=10,
            strategy=GroupingStrategy.SLIDING_WINDOW,
            min_events_per_group=2
        )

        base_time = datetime(2024, 1, 1, 12, 0)
        events = [
            create_test_event(base_time),
            create_test_event(base_time + timedelta(minutes=5)),
            create_test_event(base_time + timedelta(minutes=8)),
        ]

        groups = grouper.group_events(events)

        # Sliding window creates multiple groups
        assert len(groups) >= 1

        # Some events may appear in multiple groups
        total_event_occurrences = sum(len(g.events) for g in groups)
        assert total_event_occurrences >= len(events)

    def test_events_sorted_by_timestamp(self):
        """Test that events are sorted before grouping"""
        grouper = EventGrouper()

        base_time = datetime(2024, 1, 1, 12, 0)
        # Create events in random order
        events = [
            create_test_event(base_time + timedelta(minutes=10)),
            create_test_event(base_time),
            create_test_event(base_time + timedelta(minutes=5)),
        ]

        groups = grouper.group_events(events)

        # All events should be in one group (within 15 min window)
        assert len(groups) == 1
        assert len(groups[0].events) == 3

    def test_merge_overlapping_groups(self):
        """Test merging groups with overlapping time windows"""
        grouper = EventGrouper()

        base_time = datetime(2024, 1, 1, 12, 0)

        group1 = EventGroup(id="group1")
        group1.add_event(create_test_event(base_time))
        group1.add_event(create_test_event(base_time + timedelta(minutes=10)))

        group2 = EventGroup(id="group2")
        group2.add_event(create_test_event(base_time + timedelta(minutes=5)))
        group2.add_event(create_test_event(base_time + timedelta(minutes=15)))

        merged = grouper.merge_overlapping_groups([group1, group2])

        assert len(merged) == 1
        assert len(merged[0].events) >= 3  # Some events may be duplicated


class TestConvenienceFunctions:
    """Tests for convenience functions"""

    def test_group_events_by_time_window(self):
        """Test convenience function for basic grouping"""
        base_time = datetime(2024, 1, 1, 12, 0)
        events = [
            create_test_event(base_time),
            create_test_event(base_time + timedelta(minutes=5)),
        ]

        groups = group_events_by_time_window(events, time_window_minutes=10)

        assert len(groups) == 1
        assert len(groups[0].events) == 2

    def test_group_events_with_service_affinity(self):
        """Test convenience function with service affinity"""
        base_time = datetime(2024, 1, 1, 12, 0)
        events = [
            create_test_event(base_time, source="service-a"),
            create_test_event(base_time + timedelta(minutes=5), source="service-b"),
        ]

        groups = group_events_by_time_window(
            events,
            time_window_minutes=10,
            service_affinity=True
        )

        assert len(groups) == 2  # Separate groups per service


class TestEdgeCases:
    """Tests for edge cases and error handling"""

    def test_events_with_same_timestamp(self):
        """Test handling events with identical timestamps"""
        grouper = EventGrouper()

        same_time = datetime(2024, 1, 1, 12, 0)
        events = [
            create_test_event(same_time, title="Event 1"),
            create_test_event(same_time, title="Event 2"),
            create_test_event(same_time, title="Event 3"),
        ]

        groups = grouper.group_events(events)

        assert len(groups) == 1
        assert len(groups[0].events) == 3

    def test_very_large_time_window(self):
        """Test with very large time window"""
        grouper = EventGrouper(time_window_minutes=10000)  # ~7 days

        base_time = datetime(2024, 1, 1, 12, 0)
        events = [
            create_test_event(base_time),
            create_test_event(base_time + timedelta(days=1)),
            create_test_event(base_time + timedelta(days=2)),
        ]

        groups = grouper.group_events(events)

        # All events should be in one group
        assert len(groups) == 1
        assert len(groups[0].events) == 3

    def test_zero_time_window(self):
        """Test with zero time window (only exact matches)"""
        grouper = EventGrouper(time_window_minutes=0)

        same_time = datetime(2024, 1, 1, 12, 0)
        events = [
            create_test_event(same_time),
            create_test_event(same_time + timedelta(seconds=1)),
        ]

        groups = grouper.group_events(events)

        # Should create separate groups for different timestamps
        assert len(groups) == 2

