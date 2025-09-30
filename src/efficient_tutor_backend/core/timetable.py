'''

'''
import enum
from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field

from ..common.logger import log
from ..database.db_handler2 import DatabaseHandler
from .tuitions import Tuition, Tuitions  # Import the Tuition model and service


# --- Dynamic Enums ---
def _create_run_status_enum():
    """Encapsulates DB access to prevent running on simple import."""
    db = DatabaseHandler()
    labels = db.get_enum_labels('run_status_enum')
    return enum.Enum('RunStatus', {label: label for label in labels})

RunStatus = _create_run_status_enum()


# --- Pydantic Models ---
class ScheduledTuition(BaseModel):
    """
    A fully hydrated and validated representation of a single tuition
    event scheduled in the timetable.
    """
    tuition: Tuition
    start_time: datetime
    end_time: datetime

    model_config = ConfigDict(from_attributes=True)

    def __repr__(self) -> str:
        """
        Provides an unambiguous, developer-friendly representation.
        It reuses the __repr__ from the nested Tuition object for clarity.
        """
        # The !r format specifier calls repr() on the object.
        return f"ScheduledTuition(start_time={self.start_time!r}, tuition={self.tuition!r})"

    def __str__(self) -> str:
        """
        Provides a clean, human-readable summary of the scheduled event.
        """
        # Format the date and time for readability, e.g., "Sep 30 @ 13:02–14:32"
        time_format = "%b %d @ %H:%M"
        start_formatted = self.start_time.strftime(time_format)
        end_formatted = self.end_time.strftime("%H:%M")

        # Reuse the existing __str__ from the Tuition object
        tuition_summary = str(self.tuition)

        return f"{start_formatted}–{end_formatted}: {tuition_summary}"


class ApiScheduledTuition(BaseModel):
    """
    A Pydantic model that defines the exact JSON structure for a scheduled
    tuition to be sent to the frontend via the API.
    """
    # The source ScheduledTuition object, kept private for internal use
    source: ScheduledTuition

    def __repr__(self) -> str:
        """
        Provides a developer-friendly representation showing the API model's
        most important computed properties.
        """
        return f"ApiScheduledTuition(id='{self.id}', scheduled_start_time='{self.scheduled_start_time}')"

    def __str__(self) -> str:
        """
        Provides a human-readable summary by delegating to the source object's
        __str__ method.
        """
        return str(self.source)

    @computed_field
    @property
    def id(self) -> str:
        return str(self.source.tuition.id)

    @computed_field
    @property
    def subject(self) -> str:
        return self.source.tuition.subject.value

    @computed_field
    @property
    def lesson_index(self) -> int:
        return self.source.tuition.lesson_index

    @computed_field
    @property
    def scheduled_start_time(self) -> str:
        return self.source.start_time.isoformat()

    @computed_field
    @property
    def scheduled_end_time(self) -> str:
        return self.source.end_time.isoformat()

    @computed_field
    @property
    def student_ids(self) -> str:
        # CHANGED: Formats the IDs into the required PostgreSQL array string format.
        ids_list = [str(charge.student.id) for charge in self.source.tuition.charges]
        return f"{{{','.join(ids_list)}}}"

    @computed_field
    @property
    def student_names(self) -> list[str]:
        names = []
        for charge in self.source.tuition.charges:
            full_name = f"{charge.student.first_name or ''} {charge.student.last_name or ''}".strip()
            names.append(full_name or "Unknown Student")
        return names

    @computed_field
    @property
    def cost(self) -> str:
        if not self.source.tuition.charges:
            return "0.00"
        total_cost = sum(charge.cost for charge in self.source.tuition.charges)
        return f"{total_cost:.2f}"

# --- Service Class ---
class TimeTable:
    """
    Service class for viewing the generated timetable.
    It fetches the latest valid timetable run and processes the solution data.
    """
    def __init__(self):
        self.db = DatabaseHandler()
        self.tuitions_service = Tuitions()

    def get_latest_scheduled_tuitions(self) -> list[ScheduledTuition]:
        """
        Fetches the latest successful timetable, filters for tuition events,
        and returns a list of fully hydrated ScheduledTuition objects.
        """
        log.info("Fetching latest scheduled tuitions...")
        
        # 1. Fetch all existing tuition objects for efficient lookup (eager loading)
        all_tuitions_dict = {t.id: t for t in self.tuitions_service.get_all()}
        if not all_tuitions_dict:
            log.warning("No tuitions exist in the system. Cannot schedule anything.")
            return []

        # 2. Get the raw solution data from the latest timetable run
        solution_data = self.db.get_latest_timetable_solution()
        if not solution_data:
            return []

        scheduled_tuitions = []
        try:
            # 3. Filter, validate, and hydrate the tuition events
            for event in solution_data:
                # We only care about tuition events that have an ID
                if event.get('category') == 'Tuition' and 'id' in event:
                    tuition_id_str = event['id']
                    tuition_id = UUID(tuition_id_str)
                    
                    # Look up the full Tuition object in our pre-fetched dictionary
                    tuition_obj = all_tuitions_dict.get(tuition_id)

                    if tuition_obj:
                        scheduled_tuitions.append(
                            ScheduledTuition(
                                tuition=tuition_obj,
                                start_time=event['start_time'],
                                end_time=event['end_time']
                            )
                        )
                    else:
                        log.warning(f"Timetable references a tuition ID ({tuition_id_str}) that no longer exists. Skipping.")

            log.info(f"Successfully constructed {len(scheduled_tuitions)} scheduled tuition events.")
            return scheduled_tuitions
        
        except (TypeError, KeyError, ValueError) as e:
            log.error(f"Failed to parse timetable solution_data. Error: {e}", exc_info=True)
            return []

    def get_latest_for_api(self) -> list[dict[str, Any]]:
        """
        Fetches the latest scheduled tuitions and transforms them into the specific
        JSON-serializable dictionary format required by the API frontend.
        """
        log.info("Fetching and preparing latest timetable for API.")
        
        # 1. Get the list of rich, fully-hydrated ScheduledTuition objects.
        scheduled_tuitions = self.get_latest_scheduled_tuitions()
        
        # 2. Transform each rich object into the lean API model.
        api_models = [ApiScheduledTuition(source=st) for st in scheduled_tuitions]
        
        # 3. Convert the Pydantic models to dictionaries for JSON serialization.
        return [model.model_dump(exclude={'source'}) for model in api_models]

