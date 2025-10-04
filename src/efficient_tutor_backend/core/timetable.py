'''

'''
import enum
from datetime import datetime
from typing import Optional, Any
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field

from ..common.logger import log
from ..database.db_handler2 import DatabaseHandler
from .users import ApiUser, UserRole
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

class ApiScheduledTuitionForGuardian(BaseModel):
    """The API model for a scheduled tuition as seen by a parent or student."""
    source: ScheduledTuition
    viewer_id: UUID

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
    def charge(self) -> str:
        for charge in self.source.tuition.charges:
            if charge.parent.id == self.viewer_id or charge.student.id == self.viewer_id:
                return f"{charge.cost:.2f}"
        return "0.00"

class ApiScheduledTuitionForTeacher(BaseModel):
    """The API model for a scheduled tuition as seen by a teacher."""
    source: ScheduledTuition

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
    def total_cost(self) -> str:
        total = sum(charge.cost for charge in self.source.tuition.charges)
        return f"{total:.2f}"

    @computed_field
    @property
    def charges(self) -> list[dict]: # Using dict for simplicity
        """Provides a detailed list of charges for the teacher."""
        charge_list = []
        for c in self.source.tuition.charges:
            student_api_user = ApiUser.model_validate(c.student)
            charge_list.append({
                "student": student_api_user.model_dump(),
                "cost": f"{c.cost:.2f}"
            })
        return charge_list

# --- Service Class ---
class TimeTable:
    """
    Service class for viewing the generated timetable.
    It fetches the latest valid timetable run and processes the solution data.
    """
    def __init__(self):
        self.db = DatabaseHandler()
        self.tuitions_service = Tuitions()

    def get_all(self, viewer_id: UUID) -> list[ScheduledTuition]:
        """
        Fetches the latest successful timetable, filters for tuition events,
        and returns a list of fully hydrated ScheduledTuition objects.
        """
        log.info(f"Fetching latest scheduled tuitions for viewer {viewer_id}...")

        # 1. Fetch only the tuition objects relevant to the viewer.
        all_tuitions_dict = {t.id: t for t in self.tuitions_service.get_all(viewer_id=viewer_id)}
        if not all_tuitions_dict:
            log.warning(f"No tuitions exist for viewer {viewer_id}. Cannot schedule anything.")
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

            log.info(f"Successfully constructed {len(scheduled_tuitions)} scheduled tuition events.")
            return scheduled_tuitions
        
        except (TypeError, KeyError, ValueError) as e:
            log.error(f"Failed to parse timetable solution_data. Error: {e}", exc_info=True)
            return []

    def get_all_for_api(self, viewer_id: UUID) -> list[dict[str, Any]]:
        """
        RENAMED & REFACTORED: Public dispatcher that returns a lean list of scheduled
        tuitions formatted correctly for the viewer's role.
        """
        role = self.db.identify_user_role(viewer_id)
        rich_scheduled_tuitions = self.get_all(viewer_id) # Get the filtered rich objects

        if role == UserRole.teacher.name:
            return self._format_scheduled_for_teacher_api(rich_scheduled_tuitions)
        elif role in (UserRole.parent.name, UserRole.student.name):
            return self._format_scheduled_for_guardian_api(rich_scheduled_tuitions, viewer_id)
        else:
            raise UnauthorizedRoleError(f"User with role '{role}' is not authorized to view the timetable.")

    def _format_scheduled_for_teacher_api(self, scheduled_tuitions: list[ScheduledTuition]) -> list[dict[str, Any]]:
        """Formats scheduled tuitions for a teacher's view."""
        api_models = [ApiScheduledTuitionForTeacher(source=st) for st in scheduled_tuitions]
        return [model.model_dump(exclude={'source'}) for model in api_models]

    def _format_scheduled_for_guardian_api(self, scheduled_tuitions: list[ScheduledTuition], viewer_id: UUID) -> list[dict[str, Any]]:
        """Formats scheduled tuitions for a parent's or student's view."""
        api_models = [ApiScheduledTuitionForGuardian(source=st, viewer_id=viewer_id) for st in scheduled_tuitions]
        return [model.model_dump(exclude={'source', 'viewer_id'}) for model in api_models]
