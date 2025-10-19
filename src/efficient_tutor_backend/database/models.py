'''

'''
import uuid
import enum
from sqlalchemy import (
    Column, String, Boolean, UUID, ForeignKey, Text, Enum as SQLAlchemyEnum,
    Numeric, DateTime, JSON, Integer
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

# Base class for our ORM models
Base = declarative_base()

# --- Enums (to be replaced by dynamic loader) ---
# For now, we define them here. In the next step, we'll replace this.
#TODO: db should be the only source of truth
class UserRole(enum.Enum):
    admin = "admin"
    parent = "parent"
    student = "student"
    teacher = "teacher"

class StudentStatus(enum.Enum):
    NONE = "NONE"
    Alpha = "Alpha"
    Omega = "Omega"
    Sigma = "Sigma"
    HIM = "HIM"

class LogStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    VOID = "VOID"

class TuitionLogCreateType(enum.Enum):
    SCHEDULED = "SCHEDULED"
    CUSTOM = "CUSTOM"

# --- Main User & Role Tables ---

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_first_sign_in = Column(Boolean, default=True)
    role = Column(SQLAlchemyEnum(UserRole, name="user_role"), nullable=False)
    timezone = Column(Text, nullable=False, default='UTC')
    first_name = Column(Text)
    last_name = Column(Text)

class Parent(Base):
    __tablename__ = "parents"
    id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    currency = Column(Text, nullable=False, default='EGP')

class Student(Base):
    __tablename__ = "students"
    id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("parents.id", ondelete="CASCADE"), nullable=False)
    student_data = Column(JSON)
    cost = Column(Numeric(10, 2))
    status = Column(SQLAlchemyEnum(StudentStatus, name="student_status_enum"))
    min_duration_mins = Column(Integer)
    max_duration_mins = Column(Integer)
    grade = Column(Integer)
    generated_password = Column(Text)

class Teacher(Base):
    __tablename__ = "teachers"
    id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

# --- Tuition & Financial Tables ---

class Tuition(Base):
    __tablename__ = "tuitions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id", ondelete="SET NULL"))
    subject = Column(String, nullable=False) # Assuming subject_enum will be handled dynamically
    lesson_index = Column(Integer)
    min_duration_minutes = Column(Integer)
    max_duration_minutes = Column(Integer)
    meeting_link = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class TuitionTemplateCharge(Base):
    __tablename__ = "tuition_template_charges"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tuition_id = Column(UUID(as_uuid=True), ForeignKey("tuitions.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("parents.id", ondelete="CASCADE"), nullable=False)
    cost = Column(Numeric(10, 2), nullable=False)

class TuitionLog(Base):
    __tablename__ = "tuition_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tuition_id = Column(UUID(as_uuid=True), ForeignKey("tuitions.id", ondelete="SET NULL"))
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id", ondelete="SET NULL"))
    subject = Column(String, nullable=False)
    lesson_index = Column(Integer)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(SQLAlchemyEnum(LogStatus, name="log_status_enum"), nullable=False, default=LogStatus.ACTIVE)
    corrected_from_log_id = Column(UUID(as_uuid=True), ForeignKey("tuition_logs.id"))
    create_type = Column(SQLAlchemyEnum(TuitionLogCreateType, name="tuition_log_create_type_enum"), nullable=False)

class TuitionLogCharge(Base):
    __tablename__ = "tuition_log_charges"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tuition_log_id = Column(UUID(as_uuid=True), ForeignKey("tuition_logs.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("parents.id", ondelete="CASCADE"), nullable=False)
    cost = Column(Numeric(10, 2), nullable=False)

class PaymentLog(Base):
    __tablename__ = "payment_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("parents.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id", ondelete="SET NULL"), nullable=False)
    amount_paid = Column(Numeric(10, 2), nullable=False)
    payment_date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    notes = Column(Text)
    status = Column(SQLAlchemyEnum(LogStatus, name="log_status_enum"), nullable=False, default=LogStatus.ACTIVE)
    corrected_from_log_id = Column(UUID(as_uuid=True), ForeignKey("payment_logs.id"))
