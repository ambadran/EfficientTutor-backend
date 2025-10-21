'''

'''
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


