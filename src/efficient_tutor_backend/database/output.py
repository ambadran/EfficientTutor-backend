
from typing import List, Optional

from sqlalchemy import ARRAY, BigInteger, Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, String, Text, Time, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import datetime
import uuid

class Base(DeclarativeBase):
    pass


class TimetableRuns(Base):
    __tablename__ = 'timetable_runs'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='timetable_runs_pkey'),
        Index('idx_runs_input_hash', 'input_version_hash')
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_started_at: Mapped[datetime.datetime] = mapped_column(DateTime(True))
    status: Mapped[str] = mapped_column(Enum('SUCCESS', 'FAILED', 'MANUAL', name='run_status_enum'))
    input_version_hash: Mapped[str] = mapped_column(Text)
    run_duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    trigger_source: Mapped[Optional[str]] = mapped_column(Text)
    legacy_solution_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    timetable_run_user_solutions: Mapped[List['TimetableRunUserSolutions']] = relationship('TimetableRunUserSolutions', back_populates='timetable_run')


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

    availability_intervals: Mapped[List['AvailabilityIntervals']] = relationship('AvailabilityIntervals', back_populates='user')
    timetable_run_user_solutions: Mapped[List['TimetableRunUserSolutions']] = relationship('TimetableRunUserSolutions', back_populates='user')


class AvailabilityIntervals(Base):
    __tablename__ = 'availability_intervals'
    __table_args__ = (
        CheckConstraint('day_of_week >= 1 AND day_of_week <= 7', name='availability_intervals_day_of_week_check'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE', name='availability_intervals_user_id_fkey'),
        PrimaryKeyConstraint('id', name='availability_intervals_pkey'),
        Index('idx_availability_intervals_user_id', 'user_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    day_of_week: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[datetime.time] = mapped_column(Time)
    end_time: Mapped[datetime.time] = mapped_column(Time)
    availability_type: Mapped[str] = mapped_column(Enum('sleep', 'school', 'sports', 'others', 'work', 'personal', name='availability_type_enum'))

    user: Mapped['Users'] = relationship('Users', back_populates='availability_intervals')
    timetable_solution_slots: Mapped[List['TimetableSolutionSlots']] = relationship('TimetableSolutionSlots', back_populates='availability_interval')


class Teachers(Users):
    __tablename__ = 'teachers'
    __table_args__ = (
        ForeignKeyConstraint(['id'], ['users.id'], ondelete='CASCADE', name='teachers_id_fkey'),
        PrimaryKeyConstraint('id', name='teachers_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    currency: Mapped[str] = mapped_column(Text, server_default=text("'EGP'::text"))
    birth_date: Mapped[Optional[datetime.date]] = mapped_column(Date)

    teacher_specialties: Mapped[List['TeacherSpecialties']] = relationship('TeacherSpecialties', back_populates='teacher')
    tuitions: Mapped[List['Tuitions']] = relationship('Tuitions', back_populates='teacher')


class TimetableRunUserSolutions(Base):
    __tablename__ = 'timetable_run_user_solutions'
    __table_args__ = (
        ForeignKeyConstraint(['timetable_run_id'], ['timetable_runs.id'], ondelete='CASCADE', name='timetable_run_user_solutions_timetable_run_id_fkey'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE', name='timetable_run_user_solutions_user_id_fkey'),
        PrimaryKeyConstraint('id', name='timetable_run_user_solutions_pkey'),
        UniqueConstraint('timetable_run_id', 'user_id', name='timetable_run_user_solutions_timetable_run_id_user_id_key'),
        Index('idx_timetable_run_user_solutions_run_id', 'timetable_run_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    timetable_run_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid)

    timetable_run: Mapped['TimetableRuns'] = relationship('TimetableRuns', back_populates='timetable_run_user_solutions')
    user: Mapped['Users'] = relationship('Users', back_populates='timetable_run_user_solutions')
    timetable_solution_slots: Mapped[List['TimetableSolutionSlots']] = relationship('TimetableSolutionSlots', back_populates='solution')


class TeacherSpecialties(Base):
    __tablename__ = 'teacher_specialties'
    __table_args__ = (
        ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE', name='teacher_specialties_teacher_id_fkey'),
        PrimaryKeyConstraint('id', name='teacher_specialties_pkey'),
        UniqueConstraint('teacher_id', 'subject', 'educational_system', 'grade', name='teacher_specialties_teacher_id_subject_system_grade_key'),
        Index('idx_teacher_specialties_teacher_id', 'teacher_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    teacher_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    subject: Mapped[str] = mapped_column(Enum('Math', 'Physics', 'Chemistry', 'Biology', 'IT', 'Geography', name='subject_enum'))
    educational_system: Mapped[str] = mapped_column(Enum('IGCSE', 'SAT', 'National-EG', 'National-KW', name='educational_system_enum'))
    grade: Mapped[int] = mapped_column(Integer)

    teacher: Mapped['Teachers'] = relationship('Teachers', back_populates='teacher_specialties')
    tuitions: Mapped[List['Tuitions']] = relationship('Tuitions', back_populates='teacher_specialties')


class Tuitions(Base):
    __tablename__ = 'tuitions'
    __table_args__ = (
        ForeignKeyConstraint(['teacher_id', 'subject', 'educational_system', 'grade'], ['teacher_specialties.teacher_id', 'teacher_specialties.subject', 'teacher_specialties.educational_system', 'teacher_specialties.grade'], ondelete='RESTRICT', onupdate='CASCADE', name='fk_tuitions_to_teacher_specialties'),
        ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='SET NULL', name='tuitions_teacher_id_fkey'),
        PrimaryKeyConstraint('id', name='tuitions_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    subject: Mapped[str] = mapped_column(Enum('Math', 'Physics', 'Chemistry', 'Biology', 'IT', 'Geography', name='subject_enum'))
    lesson_index: Mapped[int] = mapped_column(Integer)
    min_duration_minutes: Mapped[int] = mapped_column(Integer)
    max_duration_minutes: Mapped[int] = mapped_column(Integer)
    educational_system: Mapped[str] = mapped_column(Enum('IGCSE', 'SAT', 'National-EG', 'National-KW', name='educational_system_enum'))
    grade: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    teacher_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    teacher_specialties: Mapped[Optional['TeacherSpecialties']] = relationship('TeacherSpecialties', back_populates='tuitions')
    teacher: Mapped[Optional['Teachers']] = relationship('Teachers', back_populates='tuitions')
    timetable_solution_slots: Mapped[List['TimetableSolutionSlots']] = relationship('TimetableSolutionSlots', back_populates='tuition')


class TimetableSolutionSlots(Base):
    __tablename__ = 'timetable_solution_slots'
    __table_args__ = (
        CheckConstraint('day_of_week >= 1 AND day_of_week <= 7', name='timetable_solution_slots_day_of_week_check'),
        CheckConstraint('tuition_id IS NOT NULL AND availability_interval_id IS NULL OR tuition_id IS NULL AND availability_interval_id IS NOT NULL', name='check_slot_source_xor'),
        ForeignKeyConstraint(['availability_interval_id'], ['availability_intervals.id'], ondelete='CASCADE', name='timetable_solution_slots_availability_interval_id_fkey'),
        ForeignKeyConstraint(['solution_id'], ['timetable_run_user_solutions.id'], ondelete='CASCADE', name='timetable_solution_slots_solution_id_fkey'),
        ForeignKeyConstraint(['tuition_id'], ['tuitions.id'], ondelete='CASCADE', name='timetable_solution_slots_tuition_id_fkey'),
        PrimaryKeyConstraint('id', name='timetable_solution_slots_pkey'),
        Index('idx_timetable_solution_slots_solution_id', 'solution_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    solution_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(Text)
    day_of_week: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[datetime.time] = mapped_column(Time)
    end_time: Mapped[datetime.time] = mapped_column(Time)
    participant_ids: Mapped[list] = mapped_column(ARRAY(Uuid()), server_default=text("'{}'::uuid[]"))
    tuition_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    availability_interval_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    availability_interval: Mapped[Optional['AvailabilityIntervals']] = relationship('AvailabilityIntervals', back_populates='timetable_solution_slots')
    solution: Mapped['TimetableRunUserSolutions'] = relationship('TimetableRunUserSolutions', back_populates='timetable_solution_slots')
    tuition: Mapped[Optional['Tuitions']] = relationship('Tuitions', back_populates='timetable_solution_slots')
