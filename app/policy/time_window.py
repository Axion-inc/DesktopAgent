"""
Time Window Parser and Validation - Phase 7
Policy Engine component for parsing and validating time-based restrictions
"""

import re
import logging
from datetime import datetime, time
from typing import List
from dataclasses import dataclass

import pytz


logger = logging.getLogger(__name__)


@dataclass
class TimeWindow:
    """Represents a time window with day-of-week and time constraints"""
    days: List[str]
    start_time: str
    end_time: str
    timezone: str

    def is_allowed(self, current_time: datetime) -> bool:
        """Check if given datetime falls within this time window"""
        try:
            # Get timezone object
            tz = pytz.timezone(self.timezone)

            # Convert current time to policy timezone
            if current_time.tzinfo is None:
                # Interpret naive datetime as being in the policy timezone
                local_time = tz.localize(current_time)
            else:
                local_time = current_time.astimezone(tz)

            # Get day of week (MON, TUE, etc.)
            weekday_names = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
            current_day = weekday_names[local_time.weekday()]

            # Parse start and end times
            start_hour, start_min = map(int, self.start_time.split(':'))
            end_hour, end_min = map(int, self.end_time.split(':'))

            start_time_obj = time(start_hour, start_min)
            end_time_obj = time(end_hour, end_min)
            current_time_obj = local_time.time()

            # Handle overnight windows (e.g., 23:00-06:00)
            if start_time_obj > end_time_obj:
                # Overnight window: check if current day OR previous day is allowed
                previous_day_idx = (local_time.weekday() - 1) % 7
                previous_day = weekday_names[previous_day_idx]

                day_allowed = current_day in self.days or previous_day in self.days
                if not day_allowed:
                    return False

                # For overnight windows, current time must be >= start OR <= end
                return current_time_obj >= start_time_obj or current_time_obj <= end_time_obj
            else:
                # Normal window: check if current day is in allowed days
                if current_day not in self.days:
                    return False

                # Normal window: current time must be >= start AND <= end
                return start_time_obj <= current_time_obj <= end_time_obj

        except Exception as e:
            logger.error(f"Error validating time window: {e}")
            return False


class TimeWindowParser:
    """Parser for time window configuration strings"""

    # Day abbreviations mapping
    DAY_MAPPING = {
        'MON': 'MON', 'TUE': 'TUE', 'WED': 'WED', 'THU': 'THU',
        'FRI': 'FRI', 'SAT': 'SAT', 'SUN': 'SUN',
        'MONDAY': 'MON', 'TUESDAY': 'TUE', 'WEDNESDAY': 'WED',
        'THURSDAY': 'THU', 'FRIDAY': 'FRI', 'SATURDAY': 'SAT', 'SUNDAY': 'SUN'
    }

    def parse(self, window_str: str) -> TimeWindow:
        """
        Parse time window string into TimeWindow object

        Supported formats:
        - "MON-FRI 09:00-17:00 Asia/Tokyo"
        - "SAT-SUN 00:00-06:00 UTC"
        - "SUN 23:00-06:00 America/New_York"
        """
        if not window_str or window_str.strip() == 'never':
            raise ValueError("Invalid time window: cannot parse 'never' or empty string")

        # Pattern: DAYS TIME_RANGE TIMEZONE
        pattern = r'^([A-Z\-,\s]+)\s+(\d{2}:\d{2})-(\d{2}:\d{2})\s+([A-Za-z/_]+)$'
        match = re.match(pattern, window_str.strip())

        if not match:
            raise ValueError(f"Invalid time window format: {window_str}")

        days_str, start_time, end_time, timezone_str = match.groups()

        # Parse days
        days = self._parse_days(days_str.strip())

        # Validate timezone
        try:
            pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValueError(f"Unknown timezone: {timezone_str}")

        # Validate time format
        self._validate_time_format(start_time)
        self._validate_time_format(end_time)

        return TimeWindow(
            days=days,
            start_time=start_time,
            end_time=end_time,
            timezone=timezone_str
        )

    def _parse_days(self, days_str: str) -> List[str]:
        """Parse day specifications into list of day abbreviations"""
        days = []

        # Handle range format (MON-FRI)
        if '-' in days_str and ',' not in days_str:
            parts = days_str.split('-')
            if len(parts) == 2:
                start_day = parts[0].strip()
                end_day = parts[1].strip()
                days = self._expand_day_range(start_day, end_day)
            else:
                raise ValueError(f"Invalid day range format: {days_str}")

        # Handle comma-separated list (MON,WED,FRI)
        elif ',' in days_str:
            day_parts = days_str.split(',')
            for day_part in day_parts:
                day_part = day_part.strip()
                if '-' in day_part:
                    # Handle range within comma list
                    range_parts = day_part.split('-')
                    if len(range_parts) == 2:
                        range_days = self._expand_day_range(range_parts[0].strip(), range_parts[1].strip())
                        days.extend(range_days)
                    else:
                        raise ValueError(f"Invalid day range in list: {day_part}")
                else:
                    # Single day
                    days.append(self._normalize_day(day_part))

        # Handle single day (SUN)
        else:
            days = [self._normalize_day(days_str)]

        # Remove duplicates while preserving order
        seen = set()
        unique_days = []
        for day in days:
            if day not in seen:
                seen.add(day)
                unique_days.append(day)

        return unique_days

    def _expand_day_range(self, start_day: str, end_day: str) -> List[str]:
        """Expand day range (e.g., MON-FRI) to list of days"""
        day_order = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']

        start_norm = self._normalize_day(start_day)
        end_norm = self._normalize_day(end_day)

        try:
            start_idx = day_order.index(start_norm)
            end_idx = day_order.index(end_norm)
        except ValueError as e:
            raise ValueError(f"Invalid day in range {start_day}-{end_day}: {e}")

        # Handle wrap-around (e.g., SAT-MON)
        if start_idx <= end_idx:
            return day_order[start_idx:end_idx + 1]
        else:
            return day_order[start_idx:] + day_order[:end_idx + 1]

    def _normalize_day(self, day: str) -> str:
        """Normalize day name to standard abbreviation"""
        day_upper = day.upper().strip()

        if day_upper in self.DAY_MAPPING:
            return self.DAY_MAPPING[day_upper]

        raise ValueError(f"Unknown day name: {day}")

    def _validate_time_format(self, time_str: str) -> None:
        """Validate time format (HH:MM)"""
        pattern = r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$'
        if not re.match(pattern, time_str):
            raise ValueError(f"Invalid time format: {time_str}")

        # Additional validation
        hour, minute = map(int, time_str.split(':'))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"Invalid time values: {time_str}")
