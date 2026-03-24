"""Abstract base classes for data providers."""
from abc import ABC, abstractmethod
from datetime import date

import pandas as pd

from analysis.providers.models import ThresholdEstimate


class ActivityProvider(ABC):
    """Provides activity and split data from a platform."""

    name: str

    @abstractmethod
    def load_activities(
        self, data_dir: str, since: date | None = None
    ) -> pd.DataFrame:
        """Return DataFrame with canonical Activity columns."""
        ...

    @abstractmethod
    def load_splits(
        self, data_dir: str, activity_ids: list[str] | None = None
    ) -> pd.DataFrame:
        """Return DataFrame with canonical Split columns."""
        ...


class HealthProvider(ABC):
    """Provides daily health / recovery data."""

    name: str

    @abstractmethod
    def load_health(
        self, data_dir: str, since: date | None = None
    ) -> pd.DataFrame:
        """Return DataFrame with canonical HealthDay columns."""
        ...


class PlanProvider(ABC):
    """Provides planned workout data."""

    name: str

    @abstractmethod
    def load_plan(
        self, data_dir: str, since: date | None = None
    ) -> pd.DataFrame:
        """Return DataFrame with canonical PlannedWorkout columns."""
        ...


class ThresholdProvider(ABC):
    """Provides auto-detected threshold values from a platform."""

    name: str

    @abstractmethod
    def detect_thresholds(self, data_dir: str) -> ThresholdEstimate:
        """Return latest auto-detected thresholds."""
        ...
