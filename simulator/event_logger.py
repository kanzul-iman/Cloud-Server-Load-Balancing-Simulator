"""
Structured Event Logger for Cloud Chaos Lab.
Captures and formats deterministic, timestamped discrete simulation events
for real-time dashboard display and scientific auditing.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional
import json
import pandas as pd


class EventSeverity(str, Enum):
    """Severity classification for simulation events."""
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class LogEntry:
    """A single immutable event log record."""
    timestamp_sec: float
    sim_time_str: str
    event_type: str
    severity: EventSeverity
    source: str
    description: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Sim_Time_sec": round(self.timestamp_sec, 3),
            "Sim_Time_Formatted": self.sim_time_str,
            "Event_Type": self.event_type,
            "Severity": self.severity.value,
            "Source": self.source,
            "Description": self.description,
            **self.details
        }


class EventLogger:
    """Thread-safe and deterministic event logger for simulation runs."""

    def __init__(self):
        self._entries: List[LogEntry] = []

    def clear(self) -> None:
        """Reset the logger."""
        self._entries.clear()

    @staticmethod
    def format_sim_time(seconds: float) -> str:
        """Format simulated seconds into mm:ss.mmm."""
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins:02d}:{secs:06.3f}"

    def log(
        self,
        timestamp_sec: float,
        event_type: str,
        severity: EventSeverity,
        source: str,
        description: str,
        **kwargs
    ) -> LogEntry:
        """Record an event entry."""
        entry = LogEntry(
            timestamp_sec=timestamp_sec,
            sim_time_str=self.format_sim_time(timestamp_sec),
            event_type=event_type,
            severity=severity,
            source=source,
            description=description,
            details=kwargs
        )
        self._entries.append(entry)
        return entry

    def info(self, timestamp_sec: float, source: str, desc: str, **kwargs) -> LogEntry:
        return self.log(timestamp_sec, "INFO", EventSeverity.INFO, source, desc, **kwargs)

    def success(self, timestamp_sec: float, source: str, desc: str, **kwargs) -> LogEntry:
        return self.log(timestamp_sec, "SUCCESS", EventSeverity.SUCCESS, source, desc, **kwargs)

    def warning(self, timestamp_sec: float, source: str, desc: str, **kwargs) -> LogEntry:
        return self.log(timestamp_sec, "WARNING", EventSeverity.WARNING, source, desc, **kwargs)

    def critical(self, timestamp_sec: float, source: str, desc: str, **kwargs) -> LogEntry:
        return self.log(timestamp_sec, "CRITICAL", EventSeverity.CRITICAL, source, desc, **kwargs)

    def get_entries(self) -> List[LogEntry]:
        """Return all logged entries in chronological order."""
        return list(self._entries)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert log entries into a pandas DataFrame."""
        if not self._entries:
            return pd.DataFrame(columns=[
                "Sim_Time_sec", "Sim_Time_Formatted", "Event_Type", "Severity", "Source", "Description"
            ])
        data = [e.to_dict() for e in self._entries]
        return pd.DataFrame(data)

    def to_json(self, indent: int = 2) -> str:
        """Export logs as formatted JSON string."""
        data = [e.to_dict() for e in self._entries]
        return json.dumps(data, indent=indent)

    def to_csv(self) -> str:
        """Export logs as CSV string."""
        return self.to_dataframe().to_csv(index=False)
