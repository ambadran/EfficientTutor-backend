'''

'''
import enum
from sqlalchemy.ext.asyncio import AsyncSession
from ..database.utils import get_enum_labels_async
from ..common.logger import log

# --- Base Enum Class ---
class ListableEnum(str, enum.Enum):
    """A custom Enum base class that can list all member names."""
    @classmethod
    def get_all_names(cls) -> list[str]:
        return [member.value for member in cls]

# --- Placeholder Enums (will be replaced at startup) ---
UserRole = ListableEnum('UserRole', {'default': 'default'})
StudentStatus = ListableEnum('StudentStatus', {'default': 'default'})
SubjectEnum = ListableEnum('SubjectEnum', {'default': 'default'})

# --- Startup Loading Function ---
async def load_dynamic_enums(db: AsyncSession):
    """
    Connects to the DB and dynamically creates Enum classes.
    This should be called once when the application starts.
    """
    global UserRole, StudentStatus, SubjectEnum
    try:
        log.info("Dynamically creating ENUM classes from database...")
        user_role_labels = await get_enum_labels_async(db, 'user_role')
        UserRole = ListableEnum('UserRole', {label: label for label in user_role_labels})

        student_status_labels = await get_enum_labels_async(db, 'student_status_enum')
        StudentStatus = ListableEnum('StudentStatus', {label: label for label in student_status_labels})

        subject_enum_labels = await get_enum_labels_async(db, 'subject_enum')
        SubjectEnum = ListableEnum('SubjectEnum', {label: label for label in subject_enum_labels})

        log.info("Successfully created dynamic ENUM classes.")
    except Exception as e:
        log.critical(f"FATAL: Could not initialize dynamic ENUMs. Application cannot start. Error: {e}", exc_info=True)
        raise

