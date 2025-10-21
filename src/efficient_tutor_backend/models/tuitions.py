'''

'''
class ApiTuitionCharge(BaseModel):
    """A lean representation of a student charge for the teacher's view."""
    student: ApiUser
    cost: Decimal

    model_config = ConfigDict(from_attributes=True)

class ApiTuitionForGuardian(BaseModel):
    """The API model for a tuition as seen by a parent or student."""
    # Internal fields for computation
    source: Tuition
    viewer_id: UUID

    @computed_field
    @property
    def id(self) -> str:
        return str(self.source.id)

    @computed_field
    @property
    def subject(self) -> str:
        return self.source.subject.value
        
    @computed_field
    @property
    def attendee_names(self) -> list[str]:
        """Shows all attendees for context."""
        names = []
        for charge in self.source.charges:
            full_name = f"{charge.student.first_name or ''} {charge.student.last_name or ''}".strip()
            names.append(full_name or "Unknown Student")
        return names

    @computed_field
    @property
    def charge(self) -> str:
        """Finds the specific cost for the viewer (parent or student)."""
        for charge in self.source.charges:
            if charge.parent.id == self.viewer_id or charge.student.id == self.viewer_id:
                return f"{charge.cost:.2f}"
        return "0.00" # Fallback

class ApiTuitionForTeacher(BaseModel):
    """The API model for a tuition as seen by a teacher."""
    source: Tuition # Keep this simple, we'll use a helper for transformation

    @computed_field
    @property
    def id(self) -> str:
        return str(self.source.id)

    @computed_field
    @property
    def subject(self) -> str:
        return self.source.subject.value

    @computed_field
    @property
    def attendee_names(self) -> list[str]:
        """Shows all attendees for context."""
        names = []
        for charge in self.source.charges:
            full_name = f"{charge.student.first_name or ''} {charge.student.last_name or ''}".strip()
            names.append(full_name or "Unknown Student")
        return names

    @computed_field
    @property
    def total_cost(self) -> str:
        """Calculates the total value of the tuition."""
        total = sum(charge.cost for charge in self.source.charges)
        return f"{total:.2f}"

    @computed_field
    @property
    def charges(self) -> list[ApiTuitionCharge]:
        """Provides a detailed list of charges for the teacher."""
        return [ApiTuitionCharge(student=ApiUser.model_validate(c.student), cost=c.cost) for c in self.source.charges]


