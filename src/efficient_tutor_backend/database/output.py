from typing import List, Optional

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKeyConstraint, Index, Integer, Numeric, PrimaryKeyConstraint, String, Text, Time, UniqueConstraint, Uuid, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import datetime
import decimal
import uuid

class Base(DeclarativeBase):
    pass


class Users(Base):
    __tablename__ = 'users'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='users_pkey'),
        UniqueConstraint('email', name='users_email_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(String(255))
    password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(Enum('admin', 'parent', 'student', 'teacher', name='user_role'), server_default=text("'parent'::user_role"))
    timezone: Mapped[str] = mapped_column(Text, server_default=text("'Africa/Cairo'::text"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text('true'))
    is_first_sign_in: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('true'))
    first_name: Mapped[Optional[str]] = mapped_column(Text)
    last_name: Mapped[Optional[str]] = mapped_column(Text)


class Parents(Users):
    __tablename__ = 'parents'
    __table_args__ = (
        ForeignKeyConstraint(['id'], ['users.id'], ondelete='CASCADE', name='parents_id_fkey'),
        PrimaryKeyConstraint('id', name='parents_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    currency: Mapped[str] = mapped_column(Text, server_default=text("'EGP'::text"))

    students: Mapped[List['Students']] = relationship('Students', back_populates='parent')


class Students(Users):
    __tablename__ = 'students'
    __table_args__ = (
        CheckConstraint('min_duration_mins >= 0 AND max_duration_mins >= 0', name='positive_durations'),
        ForeignKeyConstraint(['id'], ['users.id'], ondelete='CASCADE', name='students_id_fkey'),
        ForeignKeyConstraint(['parent_id'], ['parents.id'], ondelete='CASCADE', name='students_parent_id_fkey'),
        PrimaryKeyConstraint('id', name='students_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    cost: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), server_default=text('6.00'))
    status: Mapped[str] = mapped_column(Enum('NONE', 'Alpha', 'Omega', 'Sigma', 'HIM', name='student_status_enum'), server_default=text("'NONE'::student_status_enum"))
    min_duration_mins: Mapped[int] = mapped_column(Integer, server_default=text('60'))
    max_duration_mins: Mapped[int] = mapped_column(Integer, server_default=text('90'))
    parent_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    grade: Mapped[Optional[int]] = mapped_column(Integer)
    generated_password: Mapped[Optional[str]] = mapped_column(Text)

    parent: Mapped['Parents'] = relationship('Parents', back_populates='students')
    student_availability_intervals: Mapped[List['StudentAvailabilityIntervals']] = relationship('StudentAvailabilityIntervals', back_populates='student')


class StudentAvailabilityIntervals(Base):
    __tablename__ = 'student_availability_intervals'
    __table_args__ = (
        CheckConstraint('day_of_week >= 1 AND day_of_week <= 7', name='student_availability_intervals_day_of_week_check'),
        ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE', name='student_availability_intervals_student_id_fkey'),
        PrimaryKeyConstraint('id', name='student_availability_intervals_pkey'),
        Index('idx_student_availability_student_id', 'student_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    day_of_week: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[datetime.time] = mapped_column(Time)
    end_time: Mapped[datetime.time] = mapped_column(Time)
    availability_type: Mapped[str] = mapped_column(Enum('sleep', 'school', 'sports', 'others', name='availability_type_enum'))

    student: Mapped['Students'] = relationship('Students', back_populates='student_availability_intervals')
