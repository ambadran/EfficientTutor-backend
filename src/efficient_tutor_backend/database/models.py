from typing import Optional

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, Time, DateTime, Double, Enum, ForeignKeyConstraint, Identity, Index, Integer, Numeric, PrimaryKeyConstraint, SmallInteger, String, Table, Text, UniqueConstraint, Uuid, text, Date
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

    calendar_events: Mapped[list['CalendarEvents']] = relationship('CalendarEvents', back_populates='timetable_run')


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

    students: Mapped[list['Students']] = relationship(
        'Students', 
        back_populates='parent',
        foreign_keys='[Students.parent_id]'  # MANUAL: Add this
    )

    payment_logs: Mapped[list['PaymentLogs']] = relationship(
        'PaymentLogs',
        back_populates='parent',
        foreign_keys='[PaymentLogs.parent_id]'
    )

    tuition_template_charges: Mapped[list['TuitionTemplateCharges']] = relationship(
        'TuitionTemplateCharges', 
        back_populates='parent',
        foreign_keys='[TuitionTemplateCharges.parent_id]'  # MANUAL: Add this
    )
    tuition_log_charges: Mapped[list['TuitionLogCharges']] = relationship(
        'TuitionLogCharges', 
        back_populates='parent',
        foreign_keys='[TuitionLogCharges.parent_id]'  # MANUAL: Add this
    )

class Teachers(Users):
    __tablename__ = 'teachers'
    __table_args__ = (
        ForeignKeyConstraint(['id'], ['users.id'], ondelete='CASCADE', name='teachers_id_fkey'),
        PrimaryKeyConstraint('id', name='teachers_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    currency: Mapped[str] = mapped_column(Text, server_default=text("'EGP'::text"))
    birth_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    payment_logs: Mapped[list['PaymentLogs']] = relationship(
        'PaymentLogs', 
        back_populates='teacher',
        foreign_keys='[PaymentLogs.teacher_id]'  # MANUAL: Add this
    )
    tuitions: Mapped[list['Tuitions']] = relationship('Tuitions', back_populates='teacher')
    tuition_logs: Mapped[list['TuitionLogs']] = relationship(
        'TuitionLogs', 
        back_populates='teacher',
        foreign_keys='[TuitionLogs.teacher_id]'  # MANUAL: Add this
    )
    notes: Mapped[list['Notes']] = relationship(
        'Notes',
        back_populates='teacher',
        foreign_keys='[Notes.teacher_id]'
    )
    student_subjects: Mapped[list['StudentSubjects']] = relationship('StudentSubjects', back_populates='teacher')
    teacher_specialties: Mapped[list['TeacherSpecialties']] = relationship('TeacherSpecialties', back_populates='teacher', cascade='all, delete-orphan')



class Admins(Users):
    __tablename__ = 'admins'
    __table_args__ = (
        ForeignKeyConstraint(['id'], ['users.id'], ondelete='CASCADE', name='admins_id_fkey'),
        PrimaryKeyConstraint('id', name='admins_pkey'),
        Index('one_master_admin_idx', unique=True)
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    privileges: Mapped[str] = mapped_column(Enum('ReadOnly', 'Normal', 'Master', name='admin_privilege_type'), server_default=text("'Normal'::admin_privilege_type"))


class PaymentLogs(Base):
    __tablename__ = 'payment_logs'
    __table_args__ = (
        ForeignKeyConstraint(['corrected_from_log_id'], ['payment_logs.id'], name='payment_logs_corrected_from_log_id_fkey'),
        ForeignKeyConstraint(['parent_id'], ['users.id'], ondelete='CASCADE', name='payment_logs_parent_user_id_fkey'),
        ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='SET NULL', name='payment_logs_teacher_id_fkey'),
        PrimaryKeyConstraint('id', name='payment_logs_pkey'),
        Index('idx_payment_logs_parent', 'parent_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    parent_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    payment_date: Mapped[datetime.datetime] = mapped_column(DateTime(True), server_default=text('now()'))
    amount_paid: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(Enum('ACTIVE', 'VOID', name='log_status_enum'), server_default=text("'ACTIVE'::log_status_enum"))
    teacher_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    corrected_from_log_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    corrected_from_log: Mapped[Optional['PaymentLogs']] = relationship('PaymentLogs', remote_side=[id], back_populates='corrected_from_log_reverse')
    corrected_from_log_reverse: Mapped[list['PaymentLogs']] = relationship('PaymentLogs', remote_side=[corrected_from_log_id], back_populates='corrected_from_log')
    parent: Mapped['Parents'] = relationship(
        'Parents', 
        back_populates='payment_logs',
        foreign_keys='[PaymentLogs.parent_id]'  # MANUAL: Add this
    )
    teacher: Mapped['Teachers'] = relationship(
        'Teachers', 
        back_populates='payment_logs',
        foreign_keys='[PaymentLogs.teacher_id]'  # MANUAL: Add this
    )

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

    parent: Mapped['Parents'] = relationship(
        'Parents', 
        back_populates='students',
        foreign_keys='[Students.parent_id]'
    )

    notes: Mapped[list['Notes']] = relationship(
        'Notes', 
        back_populates='student',
        cascade='all, delete-orphan'
    )

    tuition_template_charges: Mapped[list['TuitionTemplateCharges']] = relationship(
        'TuitionTemplateCharges', 
        back_populates='student',
        foreign_keys='[TuitionTemplateCharges.student_id]',
        cascade='all, delete-orphan'
    )
    tuition_log_charges: Mapped[list['TuitionLogCharges']] = relationship(
        'TuitionLogCharges', 
        back_populates='student',
        foreign_keys='[TuitionLogCharges.student_id]',
        cascade='all, delete-orphan'
    )

    student_subject: Mapped[list['StudentSubjects']] = relationship(
        'StudentSubjects', 
        secondary='student_subject_sharings', 
        back_populates='shared_with_student'
    )

    student_subjects: Mapped[list['StudentSubjects']] = relationship(
        'StudentSubjects', 
        back_populates='student',
        cascade='all, delete-orphan'
    )

    student_availability_intervals: Mapped[list['StudentAvailabilityIntervals']] = relationship(
        'StudentAvailabilityIntervals', 
        back_populates='student',
        cascade='all, delete-orphan'
    )

class Tuitions(Base):
    __tablename__ = 'tuitions'
    __table_args__ = (
        ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='SET NULL', name='tuitions_teacher_id_fkey'),
        ForeignKeyConstraint(
            ['teacher_id', 'subject', 'educational_system'],
            ['teacher_specialties.teacher_id', 'teacher_specialties.subject', 'teacher_specialties.educational_system'],
            name='fk_tuitions_to_teacher_specialties',
            onupdate='CASCADE', ondelete='RESTRICT'
        ),
        PrimaryKeyConstraint('id', name='tuitions_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    subject: Mapped[str] = mapped_column(Enum('Math', 'Physics', 'Chemistry', 'Biology', 'IT', 'Geography', name='subject_enum'))
    educational_system: Mapped[str] = mapped_column(Enum('IGCSE', 'SAT', 'National-EG', 'National-KW', name='educational_system_enum'))
    lesson_index: Mapped[int] = mapped_column(Integer)
    min_duration_minutes: Mapped[int] = mapped_column(Integer)
    max_duration_minutes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    teacher_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    teacher: Mapped[Optional['Teachers']] = relationship('Teachers', back_populates='tuitions')
    teacher_specialty: Mapped['TeacherSpecialties'] = relationship('TeacherSpecialties', back_populates='tuitions', foreign_keys=[teacher_id, subject, educational_system])
    tuition_logs: Mapped[list['TuitionLogs']] = relationship('TuitionLogs', back_populates='tuition')
    tuition_template_charges: Mapped[list['TuitionTemplateCharges']] = relationship('TuitionTemplateCharges', back_populates='tuition')

    meeting_link: Mapped['MeetingLinks'] = relationship(
        'MeetingLinks',
        back_populates='tuition',
        cascade='all, delete-orphan' # Deleting a tuition deletes its link
    )


class TuitionLogs(Base):
    __tablename__ = 'tuition_logs'
    __table_args__ = (
        ForeignKeyConstraint(['corrected_from_log_id'], ['tuition_logs.id'], name='tuition_logs_corrected_from_log_id_fkey'),
        ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='SET NULL', name='tuition_logs_teacher_id_fkey'),
        ForeignKeyConstraint(['tuition_id'], ['tuitions.id'], ondelete='SET NULL', name='tuition_logs_tuition_id_fkey'),
        PrimaryKeyConstraint('id', name='tuition_logs_pkey'),
        Index('idx_tuition_logs_status', 'status')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    subject: Mapped[str] = mapped_column(Enum('Math', 'Physics', 'Chemistry', 'Biology', 'IT', 'Geography', name='subject_enum'))
    educational_system: Mapped[str] = mapped_column(Enum('IGCSE', 'SAT', 'National-EG', 'National-KW', name='educational_system_enum'))
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime(True))
    end_time: Mapped[datetime.datetime] = mapped_column(DateTime(True))
    status: Mapped[str] = mapped_column(Enum('ACTIVE', 'VOID', name='log_status_enum'), server_default=text("'ACTIVE'::log_status_enum"))
    create_type: Mapped[str] = mapped_column(Enum('SCHEDULED', 'CUSTOM', name='tuition_log_create_type_enum'), server_default=text("'CUSTOM'::tuition_log_create_type_enum"))
    tuition_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    lesson_index: Mapped[Optional[int]] = mapped_column(Integer)
    corrected_from_log_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    teacher_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    corrected_from_log: Mapped[Optional['TuitionLogs']] = relationship('TuitionLogs', remote_side=[id], back_populates='corrected_from_log_reverse')
    corrected_from_log_reverse: Mapped[list['TuitionLogs']] = relationship('TuitionLogs', remote_side=[corrected_from_log_id], back_populates='corrected_from_log')

    teacher: Mapped[Optional['Teachers']] = relationship(
        'Teachers', 
        back_populates='tuition_logs',
        foreign_keys='[TuitionLogs.teacher_id]'  # MANUAL: Add this
    )

    tuition: Mapped[Optional['Tuitions']] = relationship('Tuitions', back_populates='tuition_logs')
    tuition_log_charges: Mapped[list['TuitionLogCharges']] = relationship('TuitionLogCharges', back_populates='tuition_log')


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
    parent: Mapped['Parents'] = relationship(
        'Parents', 
        back_populates='tuition_template_charges',
        foreign_keys='[TuitionTemplateCharges.parent_id]'  # MANUAL: Add this
    )
    student: Mapped['Students'] = relationship(
        'Students', 
        back_populates='tuition_template_charges',
        foreign_keys='[TuitionTemplateCharges.student_id]'  # MANUAL: Add this
    )
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
    parent: Mapped['Parents'] = relationship(
        'Parents', 
        back_populates='tuition_log_charges',
        foreign_keys='[TuitionLogCharges.parent_id]'  # MANUAL: Add this
    )
    student: Mapped['Students'] = relationship(
        'Students', 
        back_populates='tuition_log_charges',
        foreign_keys='[TuitionLogCharges.student_id]'  # MANUAL: Add this
    )
    tuition_log: Mapped['TuitionLogs'] = relationship('TuitionLogs', back_populates='tuition_log_charges')


class Notes(Base):
    __tablename__ = 'notes'
    __table_args__ = (
        ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE', name='notes_student_id_fkey'),
        ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='SET NULL', name='notes_teacher_id_fkey'),
        PrimaryKeyConstraint('id', name='notes_pkey'),
        Index('idx_notes_student_id', 'student_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    teacher_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Enum('Math', 'Physics', 'Chemistry', 'Biology', 'IT', 'Geography', name='subject_enum'))
    note_type: Mapped[str] = mapped_column(Enum('STUDY_NOTES', 'HOMEWORK', 'PAST_PAPERS', name='notetypeenum'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), server_default=text('now()'))
    description: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(Text)
    student: Mapped['Students'] = relationship('Students', back_populates='notes')
    teacher: Mapped['Teachers'] = relationship('Teachers', back_populates='notes')

class MeetingLinks(Base):
    __tablename__ = 'meeting_links'
    __table_args__ = (
        ForeignKeyConstraint(['tuition_id'], ['tuitions.id'], ondelete='CASCADE', name='meeting_links_tuition_id_fkey'),
        PrimaryKeyConstraint('tuition_id', name='meeting_links_pkey')
    )

    tuition_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    meeting_link_type: Mapped[str] = mapped_column(Enum('GOOGLE_MEET', 'ZOOM', name='meetinglinktype'))
    meeting_link: Mapped[str] = mapped_column(Text)
    meeting_id: Mapped[Optional[str]] = mapped_column(Text)
    meeting_password: Mapped[Optional[str]] = mapped_column(Text)

    # --- ADD THIS 1-to-1 RELATIONSHIP BACK TO TUITIONS ---
    tuition: Mapped['Tuitions'] = relationship(
        'Tuitions', 
        back_populates='meeting_link'
    )


class StudentSubjects(Base):
    __tablename__ = 'student_subjects'
    __table_args__ = (
        ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE', name='student_subjects_student_id_fkey'),
        ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='SET NULL', name='student_subjects_teacher_id_fkey'),
        ForeignKeyConstraint(
            ['teacher_id', 'subject', 'educational_system'],
            ['teacher_specialties.teacher_id', 'teacher_specialties.subject', 'teacher_specialties.educational_system'],
            name='fk_student_subjects_to_teacher_specialties',
            onupdate='CASCADE', ondelete='RESTRICT'
        ),
        PrimaryKeyConstraint('id', name='student_subjects_pkey'),
        UniqueConstraint('student_id', 'subject', 'teacher_id', 'educational_system', name='student_subjects_student_id_subject_teacher_id_educat_key'),
        Index('idx_student_subjects_student_id', 'student_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    subject: Mapped[str] = mapped_column(Enum('Math', 'Physics', 'Chemistry', 'Biology', 'IT', 'Geography', name='subject_enum'))
    lessons_per_week: Mapped[int] = mapped_column(Integer, server_default=text('1'))
    teacher_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    educational_system: Mapped[str] = mapped_column(Enum('IGCSE', 'SAT', 'National-EG', 'National-KW', name='educational_system_enum'))

    shared_with_student: Mapped[list['Students']] = relationship('Students', secondary='student_subject_sharings', back_populates='student_subject')
    student: Mapped['Students'] = relationship('Students', back_populates='student_subjects')
    teacher: Mapped['Teachers'] = relationship('Teachers', back_populates='student_subjects')
    teacher_specialty: Mapped['TeacherSpecialties'] = relationship('TeacherSpecialties', back_populates='student_subjects', foreign_keys=[teacher_id, subject, educational_system])


t_student_subject_sharings = Table(
    'student_subject_sharings', Base.metadata,
    Column('student_subject_id', Uuid, primary_key=True, nullable=False),
    Column('shared_with_student_id', Uuid, primary_key=True, nullable=False),
    ForeignKeyConstraint(['shared_with_student_id'], ['students.id'], ondelete='CASCADE', name='student_subject_sharings_shared_with_student_id_fkey'),
    ForeignKeyConstraint(['student_subject_id'], ['student_subjects.id'], ondelete='CASCADE', name='student_subject_sharings_student_subject_id_fkey'),
    PrimaryKeyConstraint('student_subject_id', 'shared_with_student_id', name='student_subject_sharings_pkey'),
    Index('idx_student_subject_sharings_student_id', 'shared_with_student_id'),
    Index('idx_student_subject_sharings_subject_id', 'student_subject_id')
)

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


class TeacherSpecialties(Base):
    __tablename__ = 'teacher_specialties'
    __table_args__ = (
        ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE', name='teacher_specialties_teacher_id_fkey'),
        PrimaryKeyConstraint('id', name='teacher_specialties_pkey'),
        UniqueConstraint('teacher_id', 'subject', 'educational_system', name='teacher_specialties_teacher_id_subject_educational_system_key'),
        Index('idx_teacher_specialties_teacher_id', 'teacher_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    teacher_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    subject: Mapped[str] = mapped_column(Enum('Math', 'Physics', 'Chemistry', 'Biology', 'IT', 'Geography', name='subject_enum'))
    educational_system: Mapped[str] = mapped_column(Enum('IGCSE', 'SAT', 'National-EG', 'National-KW', name='educational_system_enum'))

    teacher: Mapped['Teachers'] = relationship('Teachers', back_populates='teacher_specialties')

    student_subjects: Mapped[list['StudentSubjects']] = relationship(
        'StudentSubjects',
        back_populates='teacher_specialty',
        foreign_keys='[StudentSubjects.teacher_id, StudentSubjects.subject, StudentSubjects.educational_system]'
    )

    tuitions: Mapped[list['Tuitions']] = relationship(
        'Tuitions',
        back_populates='teacher_specialty',
        foreign_keys='[Tuitions.teacher_id, Tuitions.subject, Tuitions.educational_system]'
    )


