from typing import List, Optional

from sqlalchemy import ARRAY, BigInteger, Boolean, CheckConstraint, Column, DateTime, Double, Enum, ForeignKeyConstraint, Identity, Index, Integer, Numeric, PrimaryKeyConstraint, SmallInteger, String, Table, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB, OID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import datetime
import decimal
import uuid

class Base(DeclarativeBase):
    pass


class ActivityOverlapRules(Base):
    __tablename__ = 'activity_overlap_rules'
    __table_args__ = (
        PrimaryKeyConstraint('host_category', 'interrupter_category', name='activity_overlap_rules_pkey'),
    )

    host_category: Mapped[str] = mapped_column(Enum('Gym', 'Sleep', 'Work', 'Meal', 'Tuition', 'Prayer', 'CalendarEvent', name='session_category_enum'), primary_key=True)
    interrupter_category: Mapped[str] = mapped_column(Enum('Gym', 'Sleep', 'Work', 'Meal', 'Tuition', 'Prayer', 'CalendarEvent', name='session_category_enum'), primary_key=True)


class FixedActivities(Base):
    __tablename__ = 'fixed_activities'
    __table_args__ = (
        CheckConstraint("\nCASE\n    WHEN fixed_activity_category = 'Gym'::fixed_activity_category_enum THEN 1\n    ELSE 0\nEND +\nCASE\n    WHEN fixed_activity_category = 'Sleep'::fixed_activity_category_enum THEN 1\n    ELSE 0\nEND +\nCASE\n    WHEN fixed_activity_category = 'Work'::fixed_activity_category_enum THEN 1\n    ELSE 0\nEND +\nCASE\n    WHEN fixed_activity_category = 'Meal'::fixed_activity_category_enum THEN 1\n    ELSE 0\nEND) = 1 AND (\nCASE\n    WHEN gym_type IS NOT NULL THEN 1\n    ELSE 0\nEND +\nCASE\n    WHEN sleep_type IS NOT NULL THEN 1\n    ELSE 0\nEND +\nCASE\n    WHEN work_type IS NOT NULL THEN 1\n    ELSE 0\nEND +\nCASE\n    WHEN meal_type IS NOT NULL THEN 1\n    ELSE 0\nEND) = 1 AND (fixed_activity_category = 'Gym'::fixed_activity_category_enum AND gym_type IS NOT NULL OR fixed_activity_category = 'Sleep'::fixed_activity_category_enum AND sleep_type IS NOT NULL OR fixed_activity_category = 'Work'::fixed_activity_category_enum AND work_type IS NOT NULL OR fixed_activity_category = 'Meal'::fixed_activity_category_enum AND meal_type IS NOT NULL", name='one_type_per_fixed_activity'),
        PrimaryKeyConstraint('id', name='fixed_activities_pkey')
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fixed_activity_category: Mapped[str] = mapped_column(Enum('Gym', 'Sleep', 'Work', 'Meal', name='fixed_activity_category_enum'))
    sessions_per_week: Mapped[int] = mapped_column(Integer, server_default=text('1'))
    min_duration_mins: Mapped[int] = mapped_column(Integer)
    max_duration_mins: Mapped[int] = mapped_column(Integer)
    gym_type: Mapped[Optional[str]] = mapped_column(Enum('PUSH', 'PULL', 'LEG', name='gym_type_enum'))
    sleep_type: Mapped[Optional[str]] = mapped_column(Enum('NIGHT', 'NAP', name='sleep_type_enum'))
    work_type: Mapped[Optional[str]] = mapped_column(Enum('MAIN_JOB', 'FREELANCE', 'MAIN_JOB_FREELANCE', 'TUITION', name='work_type_enum'))
    meal_type: Mapped[Optional[str]] = mapped_column(Enum('MEALPREP', 'BREAKFAST', 'SNACK', 'LUNCH', 'DINNER', name='meal_type_enum'))
    allowed_intervals: Mapped[Optional[dict]] = mapped_column(JSONB)


t_pg_stat_statements = Table(
    'pg_stat_statements', Base.metadata,
    Column('userid', OID),
    Column('dbid', OID),
    Column('toplevel', Boolean),
    Column('queryid', BigInteger),
    Column('query', Text),
    Column('plans', BigInteger),
    Column('total_plan_time', Double(53)),
    Column('min_plan_time', Double(53)),
    Column('max_plan_time', Double(53)),
    Column('mean_plan_time', Double(53)),
    Column('stddev_plan_time', Double(53)),
    Column('calls', BigInteger),
    Column('total_exec_time', Double(53)),
    Column('min_exec_time', Double(53)),
    Column('max_exec_time', Double(53)),
    Column('mean_exec_time', Double(53)),
    Column('stddev_exec_time', Double(53)),
    Column('rows', BigInteger),
    Column('shared_blks_hit', BigInteger),
    Column('shared_blks_read', BigInteger),
    Column('shared_blks_dirtied', BigInteger),
    Column('shared_blks_written', BigInteger),
    Column('local_blks_hit', BigInteger),
    Column('local_blks_read', BigInteger),
    Column('local_blks_dirtied', BigInteger),
    Column('local_blks_written', BigInteger),
    Column('temp_blks_read', BigInteger),
    Column('temp_blks_written', BigInteger),
    Column('shared_blk_read_time', Double(53)),
    Column('shared_blk_write_time', Double(53)),
    Column('local_blk_read_time', Double(53)),
    Column('local_blk_write_time', Double(53)),
    Column('temp_blk_read_time', Double(53)),
    Column('temp_blk_write_time', Double(53)),
    Column('wal_records', BigInteger),
    Column('wal_fpi', BigInteger),
    Column('wal_bytes', Numeric),
    Column('jit_functions', BigInteger),
    Column('jit_generation_time', Double(53)),
    Column('jit_inlining_count', BigInteger),
    Column('jit_inlining_time', Double(53)),
    Column('jit_optimization_count', BigInteger),
    Column('jit_optimization_time', Double(53)),
    Column('jit_emission_count', BigInteger),
    Column('jit_emission_time', Double(53)),
    Column('jit_deform_count', BigInteger),
    Column('jit_deform_time', Double(53)),
    Column('stats_since', DateTime(True)),
    Column('minmax_stats_since', DateTime(True))
)


t_pg_stat_statements_info = Table(
    'pg_stat_statements_info', Base.metadata,
    Column('dealloc', BigInteger),
    Column('stats_reset', DateTime(True))
)


class PrayerSettings(Base):
    __tablename__ = 'prayer_settings'
    __table_args__ = (
        CheckConstraint('id = 1', name='single_row_check'),
        CheckConstraint("latitude >= '-90'::integer::numeric AND latitude <= 90::numeric AND longitude >= '-180'::integer::numeric AND longitude <= 180::numeric", name='valid_location'),
        PrimaryKeyConstraint('id', name='prayer_settings_pkey')
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, server_default=text('1'))
    latitude: Mapped[decimal.Decimal] = mapped_column(Numeric(9, 6))
    longitude: Mapped[decimal.Decimal] = mapped_column(Numeric(9, 6))
    api_method: Mapped[int] = mapped_column(Integer)
    eqama_times_mins: Mapped[dict] = mapped_column(JSONB)
    duration_mins: Mapped[dict] = mapped_column(JSONB)
    last_updated: Mapped[datetime.datetime] = mapped_column(DateTime(True), server_default=text('now()'))


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
    solution_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    calendar_events: Mapped[List['CalendarEvents']] = relationship('CalendarEvents', back_populates='timetable_run')


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
    is_first_sign_in: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('true'))
    first_name: Mapped[Optional[str]] = mapped_column(Text)
    last_name: Mapped[Optional[str]] = mapped_column(Text)

    payment_logs: Mapped[List['PaymentLogs']] = relationship('PaymentLogs', back_populates='parent_user')
    students: Mapped[List['Students']] = relationship('Students', foreign_keys='[Students.user_id]', back_populates='user')
    tuition_logs: Mapped[List['TuitionLogs']] = relationship('TuitionLogs', back_populates='parent_user')


class CalendarEvents(Base):
    __tablename__ = 'calendar_events'
    __table_args__ = (
        ForeignKeyConstraint(['timetable_run_id'], ['timetable_runs.id'], name='calendar_events_timetable_run_id_fkey'),
        PrimaryKeyConstraint('id', name='calendar_events_pkey'),
        UniqueConstraint('timetable_run_id', 'event_key', name='calendar_events_timetable_run_id_event_key_key')
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True, start=1, increment=1, minvalue=1, maxvalue=9223372036854775807, cycle=False, cache=1), primary_key=True)
    timetable_run_id: Mapped[int] = mapped_column(BigInteger)
    event_key: Mapped[str] = mapped_column(Text)
    google_event_id: Mapped[str] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))

    timetable_run: Mapped['TimetableRuns'] = relationship('TimetableRuns', back_populates='calendar_events')


class Parents(Users):
    __tablename__ = 'parents'
    __table_args__ = (
        ForeignKeyConstraint(['id'], ['users.id'], ondelete='CASCADE', name='parents_id_fkey'),
        PrimaryKeyConstraint('id', name='parents_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    currency: Mapped[str] = mapped_column(Text, server_default=text("'EGP'::text"))

    students: Mapped[List['Students']] = relationship('Students', back_populates='parent')
    tuition_template_charges: Mapped[List['TuitionTemplateCharges']] = relationship('TuitionTemplateCharges', back_populates='parent')
    tuition_log_charges: Mapped[List['TuitionLogCharges']] = relationship('TuitionLogCharges', back_populates='parent')


class Teachers(Users):
    __tablename__ = 'teachers'
    __table_args__ = (
        ForeignKeyConstraint(['id'], ['users.id'], ondelete='CASCADE', name='teachers_id_fkey'),
        PrimaryKeyConstraint('id', name='teachers_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)

    payment_logs: Mapped[List['PaymentLogs']] = relationship('PaymentLogs', back_populates='teacher')
    tuitions: Mapped[List['Tuitions']] = relationship('Tuitions', back_populates='teacher')
    tuition_logs: Mapped[List['TuitionLogs']] = relationship('TuitionLogs', back_populates='teacher')


class PaymentLogs(Base):
    __tablename__ = 'payment_logs'
    __table_args__ = (
        ForeignKeyConstraint(['corrected_from_log_id'], ['payment_logs.id'], name='payment_logs_corrected_from_log_id_fkey'),
        ForeignKeyConstraint(['parent_user_id'], ['users.id'], ondelete='CASCADE', name='payment_logs_parent_user_id_fkey'),
        ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='SET NULL', name='payment_logs_teacher_id_fkey'),
        PrimaryKeyConstraint('id', name='payment_logs_pkey'),
        Index('idx_payment_logs_parent', 'parent_user_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    parent_user_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    payment_date: Mapped[datetime.datetime] = mapped_column(DateTime(True), server_default=text('now()'))
    amount_paid: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(Enum('ACTIVE', 'VOID', name='log_status_enum'), server_default=text("'ACTIVE'::log_status_enum"))
    teacher_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    corrected_from_log_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    corrected_from_log: Mapped[Optional['PaymentLogs']] = relationship('PaymentLogs', remote_side=[id], back_populates='corrected_from_log_reverse')
    corrected_from_log_reverse: Mapped[List['PaymentLogs']] = relationship('PaymentLogs', remote_side=[corrected_from_log_id], back_populates='corrected_from_log')
    parent_user: Mapped['Users'] = relationship('Users', back_populates='payment_logs')
    teacher: Mapped['Teachers'] = relationship('Teachers', back_populates='payment_logs')


class Students(Users):
    __tablename__ = 'students'
    __table_args__ = (
        CheckConstraint('min_duration_mins >= 0 AND max_duration_mins >= 0', name='positive_durations'),
        ForeignKeyConstraint(['id'], ['users.id'], ondelete='CASCADE', name='students_id_fkey'),
        ForeignKeyConstraint(['parent_id'], ['parents.id'], ondelete='CASCADE', name='students_parent_id_fkey'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE', name='students_user_id_fkey'),
        PrimaryKeyConstraint('id', name='students_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    student_data: Mapped[dict] = mapped_column(JSONB)
    cost: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), server_default=text('6.00'))
    status: Mapped[str] = mapped_column(Enum('NONE', 'Alpha', 'Omega', 'Sigma', 'HIM', name='student_status_enum'), server_default=text("'NONE'::student_status_enum"))
    min_duration_mins: Mapped[int] = mapped_column(Integer, server_default=text('60'))
    max_duration_mins: Mapped[int] = mapped_column(Integer, server_default=text('90'))
    parent_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_name: Mapped[Optional[str]] = mapped_column(String(255))
    grade: Mapped[Optional[int]] = mapped_column(Integer)
    generated_password: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[dict]] = mapped_column(JSONB)

    parent: Mapped['Parents'] = relationship('Parents', back_populates='students')
    user: Mapped['Users'] = relationship('Users', foreign_keys=[user_id], back_populates='students')
    tuition_template_charges: Mapped[List['TuitionTemplateCharges']] = relationship('TuitionTemplateCharges', back_populates='student')
    tuition_log_charges: Mapped[List['TuitionLogCharges']] = relationship('TuitionLogCharges', back_populates='student')


class Tuitions(Base):
    __tablename__ = 'tuitions'
    __table_args__ = (
        ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='SET NULL', name='tuitions_teacher_id_fkey'),
        PrimaryKeyConstraint('id', name='tuitions_pkey'),
        UniqueConstraint('student_ids', 'subject', 'lesson_index', name='tuitions_student_ids_subject_lesson_index_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    student_ids: Mapped[list] = mapped_column(ARRAY(Uuid()))
    subject: Mapped[str] = mapped_column(Enum('Math', 'Physics', 'Chemistry', 'Biology', 'IT', 'Geography', name='subject_enum'))
    lesson_index: Mapped[int] = mapped_column(Integer)
    cost: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2))
    min_duration_minutes: Mapped[int] = mapped_column(Integer)
    max_duration_minutes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    meeting_link: Mapped[Optional[dict]] = mapped_column(JSONB)
    teacher_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    teacher: Mapped[Optional['Teachers']] = relationship('Teachers', back_populates='tuitions')
    tuition_logs: Mapped[List['TuitionLogs']] = relationship('TuitionLogs', back_populates='tuition')
    tuition_template_charges: Mapped[List['TuitionTemplateCharges']] = relationship('TuitionTemplateCharges', back_populates='tuition')


class TuitionLogs(Base):
    __tablename__ = 'tuition_logs'
    __table_args__ = (
        ForeignKeyConstraint(['corrected_from_log_id'], ['tuition_logs.id'], name='tuition_logs_corrected_from_log_id_fkey'),
        ForeignKeyConstraint(['parent_user_id'], ['users.id'], ondelete='CASCADE', name='tuition_logs_parent_user_id_fkey'),
        ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='SET NULL', name='tuition_logs_teacher_id_fkey'),
        ForeignKeyConstraint(['tuition_id'], ['tuitions.id'], ondelete='SET NULL', name='tuition_logs_tuition_id_fkey'),
        PrimaryKeyConstraint('id', name='tuition_logs_pkey'),
        Index('idx_tuition_logs_parent', 'parent_user_id'),
        Index('idx_tuition_logs_status', 'status')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    parent_user_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    subject: Mapped[str] = mapped_column(Enum('Math', 'Physics', 'Chemistry', 'Biology', 'IT', 'Geography', name='subject_enum'))
    attendee_names: Mapped[list] = mapped_column(ARRAY(Text()))
    cost: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2))
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime(True))
    end_time: Mapped[datetime.datetime] = mapped_column(DateTime(True))
    status: Mapped[str] = mapped_column(Enum('ACTIVE', 'VOID', name='log_status_enum'), server_default=text("'ACTIVE'::log_status_enum"))
    create_type: Mapped[str] = mapped_column(Enum('SCHEDULED', 'CUSTOM', name='tuition_log_create_type_enum'), server_default=text("'CUSTOM'::tuition_log_create_type_enum"))
    tuition_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    lesson_index: Mapped[Optional[int]] = mapped_column(Integer)
    corrected_from_log_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    attendee_ids: Mapped[Optional[list]] = mapped_column(ARRAY(Uuid()))
    teacher_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    corrected_from_log: Mapped[Optional['TuitionLogs']] = relationship('TuitionLogs', remote_side=[id], back_populates='corrected_from_log_reverse')
    corrected_from_log_reverse: Mapped[List['TuitionLogs']] = relationship('TuitionLogs', remote_side=[corrected_from_log_id], back_populates='corrected_from_log')
    parent_user: Mapped['Users'] = relationship('Users', back_populates='tuition_logs')
    teacher: Mapped[Optional['Teachers']] = relationship('Teachers', back_populates='tuition_logs')
    tuition: Mapped[Optional['Tuitions']] = relationship('Tuitions', back_populates='tuition_logs')
    tuition_log_charges: Mapped[List['TuitionLogCharges']] = relationship('TuitionLogCharges', back_populates='tuition_log')


class TuitionTemplateCharges(Base):
    __tablename__ = 'tuition_template_charges'
    __table_args__ = (
        ForeignKeyConstraint(['parent_id'], ['parents.id'], ondelete='CASCADE', name='tuition_template_charges_parent_id_fkey'),
        ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE', name='tuition_template_charges_student_id_fkey'),
        ForeignKeyConstraint(['tuition_id'], ['tuitions.id'], ondelete='CASCADE', name='tuition_template_charges_tuition_id_fkey'),
        PrimaryKeyConstraint('id', name='tuition_template_charges_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    tuition_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    parent_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    cost: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2))

    parent: Mapped['Parents'] = relationship('Parents', back_populates='tuition_template_charges')
    student: Mapped['Students'] = relationship('Students', back_populates='tuition_template_charges')
    tuition: Mapped['Tuitions'] = relationship('Tuitions', back_populates='tuition_template_charges')


class TuitionLogCharges(Base):
    __tablename__ = 'tuition_log_charges'
    __table_args__ = (
        ForeignKeyConstraint(['parent_id'], ['parents.id'], ondelete='CASCADE', name='tuition_log_charges_parent_id_fkey'),
        ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE', name='tuition_log_charges_student_id_fkey'),
        ForeignKeyConstraint(['tuition_log_id'], ['tuition_logs.id'], ondelete='CASCADE', name='tuition_log_charges_tuition_log_id_fkey'),
        PrimaryKeyConstraint('id', name='tuition_log_charges_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    tuition_log_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    parent_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    cost: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2))

    parent: Mapped['Parents'] = relationship('Parents', back_populates='tuition_log_charges')
    student: Mapped['Students'] = relationship('Students', back_populates='tuition_log_charges')
    tuition_log: Mapped['TuitionLogs'] = relationship('TuitionLogs', back_populates='tuition_log_charges')
