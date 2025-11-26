'''

'''
import pytest
from uuid import UUID, uuid4
from datetime import datetime, time
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError

from pydantic import ValidationError

from src.efficient_tutor_backend.database import models as db_models
from src.efficient_tutor_backend.database.db_enums import (
        MeetingLinkTypeEnum, 
        SubjectEnum, 
        StudentStatusEnum, 
        AvailabilityTypeEnum,
        EducationalSystemEnum
        )
from src.efficient_tutor_backend.models import user as user_models
from src.efficient_tutor_backend.models import tuition as tuition_models 
from src.efficient_tutor_backend.models import meeting_links as meeting_link_models 
from src.efficient_tutor_backend.services.tuition_service import TuitionService
from src.efficient_tutor_backend.services.user_service import UserService, StudentService # Import UserService for creating students
# --- Import Test Constants ---
from tests.constants import TEST_TEACHER_ID, TEST_STUDENT_ID, TEST_PARENT_ID, TEST_UNRELATED_TEACHER_ID

from pprint import pp as pprint


@pytest.mark.anyio
class TestTuitionServiceRead:

    ### Tests for get_tuition_by_id ###

    async def test_get_tuition_by_id(
        self,
        tuition_service: TuitionService,
        test_tuition_orm: db_models.Tuitions
    ):
        """Tests fetching a single tuition template by its ID."""
        # Use the fixture to get a known tuition
        tuition = await tuition_service._get_tuition_by_id_internal(test_tuition_orm.id)

        assert isinstance(tuition, db_models.Tuitions)
        print(f"\n--- Found Tuition by ID ({test_tuition_orm.id}) ---")
        pprint(tuition.__dict__)
        pprint(tuition.tuition_template_charges[0].__dict__)
        pprint(tuition.meeting_link.__dict__)

        assert tuition is not None
        assert tuition.id == test_tuition_orm.id

    async def test_get_tuition_by_id_not_found(
        self,
        tuition_service: TuitionService
    ):
        """Tests that None is returned for a non-existent tuition ID."""
        print(f"\n--- Testing _get_tuition_by_id_internal for non-existing tuition ---")
        with pytest.raises(HTTPException) as e:
            await tuition_service._get_tuition_by_id_internal(UUID(int=0)) # Random UUID

        assert e.value.status_code == 404
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_get_tuition_by_id_for_api(
        self,
        tuition_service: TuitionService,
        test_teacher_orm: db_models.Users,
        test_parent_orm: db_models.Users,
        test_student_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions
    ):
        """Tests fetching a single tuition template by its ID."""
        # Use the fixture to get a known tuition
        tuition_for_teacher = await tuition_service.get_tuition_by_id_for_api(test_tuition_orm.id, test_teacher_orm)
        assert isinstance(tuition_for_teacher, tuition_models.TuitionReadForTeacher)
        assert tuition_for_teacher.id == test_tuition_orm.id

        tuition_for_parent = await tuition_service.get_tuition_by_id_for_api(test_tuition_orm.id, test_parent_orm)
        assert isinstance(tuition_for_parent, tuition_models.TuitionReadForParent)
        assert tuition_for_parent.id == test_tuition_orm.id

        tuition_for_student = await tuition_service.get_tuition_by_id_for_api(test_tuition_orm.id, test_student_orm)
        assert isinstance(tuition_for_student, tuition_models.TuitionReadForStudent)
        assert tuition_for_student.id == test_tuition_orm.id

        print(f"\n--- Found Tuition by ID ({test_tuition_orm.id}) ---")
        pprint(tuition_for_teacher.__dict__)

    async def test_get_tuition_by_id_for_api_not_related(
        self,
        tuition_service: TuitionService,
        test_unrelated_teacher_orm: db_models.Users,
        test_unrelated_parent_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions
    ):
        """Tests fetching a single tuition template by its ID."""
        # Use the fixture to get a known tuition
        with pytest.raises(HTTPException) as e:
            await tuition_service.get_tuition_by_id_for_api(test_tuition_orm.id, test_unrelated_teacher_orm)
        assert e.value.status_code == 403


        with pytest.raises(HTTPException) as e:
            await tuition_service.get_tuition_by_id_for_api(test_tuition_orm.id, test_unrelated_parent_orm)
        assert e.value.status_code == 403
        
        print(f"--- Correctly raised HTTPException: {e.value.status_code} {e.value.detail} ---")

    ### Tests for get_all_tuitions ###

    async def test_get_all_orm(
        self,
        tuition_service: TuitionService,
        test_teacher_orm: db_models.Users
    ):
        """
        Tests that a TEACHER can successfully fetch all tuitions.
        The service should return all tuitions associated with this teacher.
        """
        print(f"\n--- Testing get_all_tuitions as TEACHER ({test_teacher_orm.first_name}) ---")
        
        tuitions = await tuition_service.get_all_tuitions_orm(current_user=test_teacher_orm)
        
        # --- Assertions ---
        assert isinstance(tuitions, list)
        assert isinstance(tuitions[0], db_models.Tuitions)
        
        # --- Logging ---
        print(f"--- Found {len(tuitions)} Total Tuitions for Teacher '{test_teacher_orm.first_name} {test_teacher_orm.last_name}'---")
        if tuitions:
            assert isinstance(tuitions[0], db_models.Tuitions)
            print(f"Example Tuition Subject: {tuitions[0].subject}")
            print("--- Example Tuition Object (raw) ---")
            pprint(tuitions[0].__dict__)
        else:
            print("--- No tuitions found for this teacher in the test data. ---")
        # --- End Logging ---

    async def test_get_all_for_api_as_teacher(
        self,
        tuition_service: TuitionService,
        test_teacher_orm: db_models.Users
    ):
        """
        Tests that a TEACHER can successfully fetch all tuitions.
        The service should return all tuitions associated with this teacher.
        """
        print(f"\n--- Testing get_all_tuitions as TEACHER ({test_teacher_orm.first_name}) ---")
        
        tuitions = await tuition_service.get_all_tuitions_for_api(current_user=test_teacher_orm)
        
        # --- Assertions ---
        assert isinstance(tuitions, list)
        assert isinstance(tuitions[0], tuition_models.TuitionReadForTeacher)
        
        # --- Logging ---
        print(f"--- Found {len(tuitions)} Total Tuitions for Teacher '{test_teacher_orm.first_name} {test_teacher_orm.last_name}'---")
        if tuitions:
            print(f"Example Tuition Subject: {tuitions[0].subject}")
            print("--- Example Tuition Object (raw) ---")
            pprint(tuitions[0].__dict__)
        else:
            print("--- No tuitions found for this teacher in the test data. ---")
        # --- End Logging ---

    async def test_get_all_for_api_as_parent(
        self,
        tuition_service: TuitionService,
        test_parent_orm: db_models.Users
    ):
        """
        Tests that a PARENT can successfully fetch their tuitions.
        The service should return only tuitions relevant to this parent.
        """
        print(f"\n--- Testing get_all_tuitions as PARENT ({test_parent_orm.first_name}) ---")
        
        tuitions = await tuition_service.get_all_tuitions_for_api(current_user=test_parent_orm)
        
        # --- Assertions ---
        assert isinstance(tuitions, list)
        assert isinstance(tuitions[0], tuition_models.TuitionReadForParent)
        
        # --- Logging ---
        print(f"--- Found {len(tuitions)} Tuitions for Parent '{test_parent_orm.first_name} {test_parent_orm.last_name}' ---")
        if tuitions:
            print(f"Example Tuition Subject: {tuitions[0].subject}")
            print("--- Example Tuition Object (raw) ---")
            pprint(tuitions[0].__dict__)
        else:
            print("--- No tuitions found for this parent in the test data. ---")
        # --- End Logging ---

    async def test_get_all_for_api_as_student(
        self,
        tuition_service: TuitionService,
        test_student_orm: db_models.Users
    ):
        """
        Tests that a STUDENT can successfully fetch their tuitions.
        The service should return only tuitions relevant to this student.
        """
        print(f"\n--- Testing get_all_tuitions as STUDENT ({test_student_orm.first_name}) ---")

        tuitions = await tuition_service.get_all_tuitions_for_api(current_user=test_student_orm)

        # --- Assertions ---
        assert isinstance(tuitions, list)
        assert isinstance(tuitions[0], tuition_models.TuitionReadForStudent)
        
        # --- Logging ---
        print(f"--- Found {len(tuitions)} Tuitions for Student '{test_student_orm.first_name} {test_student_orm.last_name}' ---")
        if tuitions:
            print(f"Example Tuition Subject: {tuitions[0].subject}")
            print("--- Example Tuition Object (raw) ---")
            pprint(tuitions[0].__dict__)

# --- Helper Function to create students with subjects ---
async def _create_student_with_subjects(
    student_service: StudentService,
    db_session: AsyncSession,
    parent_orm: db_models.Parents,
    teacher_orm: db_models.Teachers,
    student_email: str,
    subjects_data: list[user_models.StudentSubjectWrite],
    min_duration: int = 60,
    max_duration: int = 90,
    cost: Decimal = Decimal("10.00")
) -> db_models.Students:
    """Helper to create a student with associated subjects and availability."""
    student_create_data = user_models.StudentCreate(
        email=student_email,
        password="testpassword",
        first_name=f"{student_email.split('@')[0]}",
        last_name="Test",
        parent_id=parent_orm.id,
        cost=cost,
        status=StudentStatusEnum.ALPHA,
        min_duration_mins=min_duration,
        max_duration_mins=max_duration,
        student_subjects=subjects_data,
        student_availability_intervals=[
            user_models.StudentAvailabilityIntervalWrite(
                day_of_week=1, 
                start_time=time(9, 0), 
                end_time=time(10, 0), 
                availability_type=AvailabilityTypeEnum.SCHOOL
            )
        ]
    )
    student_read_model = await student_service.create_student(student_create_data, parent_orm)
    await db_session.flush() # Ensure student and subjects are in session

    # Fetch the ORM object with necessary relationships eagerly loaded
    stmt = select(db_models.Students).options(
        selectinload(db_models.Students.student_subjects).selectinload(db_models.StudentSubjects.shared_with_student)
    ).filter(db_models.Students.id == student_read_model.id)
    student_orm = (await db_session.execute(stmt)).scalars().first()
    
    if not student_orm:
        raise Exception(f"Failed to retrieve ORM student for ID: {student_read_model.id}")

    return student_orm

@pytest.mark.anyio
class TestTuitionServiceRegenerate:

    ### Tests for regenerate_all_tuitions ###

    async def test_regenerate_all_tuitions_no_student_subjects(
        self,
        tuition_service: TuitionService,
        db_session: AsyncSession
    ):
        """
        Tests that if no student subjects exist, regeneration truncates tuitions
        and returns True without creating new ones.
        """
        print("\n--- Testing regenerate_all_tuitions with no student subjects ---")

        # Ensure no student subjects exist
        await db_session.execute(delete(db_models.StudentSubjects))
        await db_session.execute(delete(db_models.Tuitions))
        await db_session.execute(delete(db_models.TuitionTemplateCharges))
        await db_session.flush()

        # Run regeneration
        result = await tuition_service.regenerate_all_tuitions()

        # Assertions
        assert result is True
        tuitions_after = (await db_session.execute(select(db_models.Tuitions))).scalars().all()
        assert len(tuitions_after) == 0
        charges_after = (await db_session.execute(select(db_models.TuitionTemplateCharges))).scalars().all()
        assert len(charges_after) == 0
        
        print("--- Successfully handled no student subjects: no tuitions created. ---")

    async def test_regenerate_all_tuitions_single_student_single_subject(
        self,
        tuition_service: TuitionService,
        student_service: StudentService,
        db_session: AsyncSession,
        test_parent_orm: db_models.Parents,
        test_teacher_orm: db_models.Teachers
    ):
        """
        Tests regeneration with a single student, single subject, and single teacher.
        Expects one tuition and one charge.
        """
        print("\n--- Testing regenerate_all_tuitions with single student, single subject ---")

        # Clear existing tuitions to ensure a clean state for this test
        await db_session.execute(delete(db_models.Tuitions))
        await db_session.execute(delete(db_models.TuitionTemplateCharges))
        await db_session.execute(delete(db_models.StudentSubjects))
        await db_session.flush()

        # 1. Create a student with one subject
        student_email = "student1@example.com"
        subject_data = user_models.StudentSubjectWrite(
            subject=SubjectEnum.MATH,
            educational_system=EducationalSystemEnum.SAT,
            lessons_per_week=1,
            teacher_id=test_teacher_orm.id,
            grade=10,
            shared_with_student_ids=[]
        )
        student1 = await _create_student_with_subjects(
            student_service, db_session, test_parent_orm, test_teacher_orm, student_email, [subject_data]
        )
        await db_session.flush() # /ommit student creation

        # 2. Run regeneration
        result = await tuition_service.regenerate_all_tuitions()
        assert result is True

        # 3. Assertions
        tuitions = (await db_session.execute(select(db_models.Tuitions))).scalars().all()
        charges = (await db_session.execute(select(db_models.TuitionTemplateCharges))).scalars().all()

        assert len(tuitions) == 1
        assert len(charges) == 1

        tuition = tuitions[0]
        print(f"--- Example of the one tuition created ----")
        pprint(tuition.__dict__)
        print(f"--- Example of the one tuition_charge_data created ----")
        charge = charges[0]
        pprint(charge.__dict__)

        assert tuition.subject == SubjectEnum.MATH.value
        assert tuition.educational_system == EducationalSystemEnum.SAT.value
        assert tuition.teacher_id == test_teacher_orm.id
        assert tuition.lesson_index == 1
        assert tuition.min_duration_minutes == student1.min_duration_mins
        assert tuition.max_duration_minutes == student1.max_duration_mins

        assert charge.tuition_id == tuition.id
        assert charge.student_id == student1.id
        assert charge.parent_id == student1.parent_id
        assert charge.cost == student1.cost
        
        print(f"--- Successfully created 1 tuition and 1 charge for student {student1.email} ---")

    async def test_regenerate_all_tuitions_multiple_students_same_subject_same_teacher_shared(
        self,
        tuition_service: TuitionService,
        student_service: StudentService,
        db_session: AsyncSession,
        test_parent_orm: db_models.Parents,
        test_teacher_orm: db_models.Teachers
    ):
        """
        Tests regeneration with multiple students sharing the same subject with the same teacher.
        Expects one tuition and multiple charges.
        """
        print("\n--- Testing regenerate_all_tuitions with multiple students, shared subject ---")

        # Clear existing tuitions
        await db_session.execute(delete(db_models.Tuitions))
        await db_session.execute(delete(db_models.TuitionTemplateCharges))
        await db_session.execute(delete(db_models.StudentSubjects))
        await db_session.flush()

        # 1. Create two students
        student1_email = "student_shared1@example.com"
        student2_email = "student_shared2@example.com"

        # Create student1 first, then use its ID for student2's shared_with_student_ids
        student1 = await _create_student_with_subjects(
            student_service, db_session, test_parent_orm, test_teacher_orm, student1_email, [
                user_models.StudentSubjectWrite(
                    subject=SubjectEnum.PHYSICS,
                    educational_system=EducationalSystemEnum.SAT,
                    lessons_per_week=1,
                    teacher_id=test_teacher_orm.id,
                    grade=10,
                    shared_with_student_ids=[] # Will be updated by student2
                )
            ]
        )
        # Refresh student1 to ensure its student_subjects are loaded
        await db_session.refresh(student1, ['student_subjects'])
        
        # Now create student2, sharing with student1
        student2 = await _create_student_with_subjects(
            student_service, db_session, test_parent_orm, test_teacher_orm, student2_email, [
                user_models.StudentSubjectWrite(
                    subject=SubjectEnum.PHYSICS,
                    educational_system=EducationalSystemEnum.SAT,
                    lessons_per_week=1,
                    teacher_id=test_teacher_orm.id,
                    grade=10,
                    shared_with_student_ids=[student1.id] # Student2 shares with Student1
                )
            ]
        )
        # Update student1's subject to also share with student2
        # This requires fetching student1's subject and updating its shared_with_student relationship
        student1_physics_subject = next(
            (ss for ss in student1.student_subjects if ss.subject == SubjectEnum.PHYSICS.value), None
        )
        assert student1_physics_subject is not None
        student1_physics_subject.shared_with_student.append(student2)
        db_session.add(student1_physics_subject)
        await db_session.flush()

        # 2. Run regeneration
        result = await tuition_service.regenerate_all_tuitions()
        assert result is True

        # 3. Assertions
        tuitions = (await db_session.execute(select(db_models.Tuitions))).scalars().all()
        charges = (await db_session.execute(select(db_models.TuitionTemplateCharges))).scalars().all()

        assert len(tuitions) == 1
        assert len(charges) == 2

        tuition = tuitions[0]
        charge_student1 = next((c for c in charges if c.student_id == student1.id), None)
        charge_student2 = next((c for c in charges if c.student_id == student2.id), None)

        assert tuition.subject == SubjectEnum.PHYSICS.value
        assert tuition.educational_system == EducationalSystemEnum.SAT.value
        assert tuition.teacher_id == test_teacher_orm.id
        assert tuition.lesson_index == 1

        assert charge_student1 is not None
        assert charge_student1.tuition_id == tuition.id
        assert charge_student1.student_id == student1.id
        assert charge_student1.cost == student1.cost

        assert charge_student2 is not None
        assert charge_student2.tuition_id == tuition.id
        assert charge_student2.student_id == student2.id
        assert charge_student2.cost == student2.cost
        
        print(f"--- Successfully created 1 tuition and 2 charges for shared students ---")

    async def test_regenerate_all_tuitions_multiple_students_different_subjects_teachers(
        self,
        tuition_service: TuitionService,
        student_service: StudentService,
        db_session: AsyncSession,
        test_parent_orm: db_models.Parents,
        test_teacher_orm: db_models.Teachers, # Teacher 1
        test_unrelated_teacher_orm: db_models.Teachers # Teacher 2
    ):
        """
        Tests regeneration with multiple students, subjects, and teachers,
        including shared and unshared subjects.
        """
        print("\n--- Testing regenerate_all_tuitions with complex student/subject/teacher setup ---")

        # Clear existing tuitions
        await db_session.execute(delete(db_models.Tuitions))
        await db_session.execute(delete(db_models.TuitionTemplateCharges))
        await db_session.execute(delete(db_models.StudentSubjects))
        await db_session.flush()

        # 1. Create students and subjects
        # Student A: Math (Teacher 1), Physics (Teacher 1, shared with B)
        student_a = await _create_student_with_subjects(
            student_service, 
            db_session, 
            test_parent_orm, 
            test_teacher_orm, 
            "student_a@example.com", 
            [
                user_models.StudentSubjectWrite(
                    subject=SubjectEnum.MATH, 
                    educational_system=EducationalSystemEnum.SAT,
                    lessons_per_week=1, 
                    teacher_id=test_teacher_orm.id, 
                    grade=10,
                    shared_with_student_ids=[]),
                user_models.StudentSubjectWrite(
                    subject=SubjectEnum.PHYSICS, 
                    educational_system=EducationalSystemEnum.SAT,
                    lessons_per_week=1, 
                    teacher_id=test_teacher_orm.id, 
                    grade=10,
                    shared_with_student_ids=[]),
            ], 
            cost=Decimal("10.00")
        )
        await db_session.refresh(student_a, ['student_subjects'])

        # Student B: Physics (Teacher 1, shared with A), Chemistry (Teacher 2)
        student_b = await _create_student_with_subjects(
            student_service, 
            db_session, 
            test_parent_orm, 
            test_teacher_orm, 
            "student_b@example.com", 
            [
                user_models.StudentSubjectWrite(
                    subject=SubjectEnum.PHYSICS, 
                    educational_system=EducationalSystemEnum.SAT,
                    lessons_per_week=1, 
                    teacher_id=test_teacher_orm.id, 
                    grade=10,
                    shared_with_student_ids=[student_a.id]),
                user_models.StudentSubjectWrite(
                    subject=SubjectEnum.CHEMISTRY, 
                    educational_system=EducationalSystemEnum.SAT,
                    lessons_per_week=1, 
                    teacher_id=test_unrelated_teacher_orm.id, 
                    grade=10,
                    shared_with_student_ids=[]),
            ], 
            cost=Decimal("12.00")
        )
        await db_session.refresh(student_b, ['student_subjects'])

        # Update student A's Physics subject to share with B
        student_a_physics_subject = next(ss for ss in student_a.student_subjects if ss.subject == SubjectEnum.PHYSICS.value)
        student_a_physics_subject.shared_with_student.append(student_b)
        db_session.add(student_a_physics_subject)
        await db_session.flush()
        await db_session.flush()

        # Student C: Math (Teacher 1, unique)
        student_c = await _create_student_with_subjects(
            student_service, 
            db_session, 
            test_parent_orm, 
            test_teacher_orm, 
            "student_c@example.com", 
            [
                user_models.StudentSubjectWrite(
                    subject=SubjectEnum.MATH, 
                    educational_system=EducationalSystemEnum.SAT,
                    lessons_per_week=1, 
                    teacher_id=test_teacher_orm.id, 
                    grade=10,
                    shared_with_student_ids=[]),
            ], 
            cost=Decimal("15.00")
        )
        await db_session.flush()

        # 2. Run regeneration
        result = await tuition_service.regenerate_all_tuitions()
        assert result is True

        # 3. Assertions
        tuitions = (await db_session.execute(select(db_models.Tuitions))).scalars().all()
        charges = (await db_session.execute(select(db_models.TuitionTemplateCharges))).scalars().all()

        # Expected Tuitions:
        # 1. Math (Teacher 1, Student A) - SAT
        # 2. Physics (Teacher 1, Student A & B) - SAT
        # 3. Chemistry (Teacher 2, Student B) - SAT
        # 4. Math (Teacher 1, Student C) - SAT
        assert len(tuitions) == 4
        assert len(charges) == 5 # Student A (Math), Student A (Physics), Student B (Physics), Student B (Chemistry), Student C (Math)

        # Verify Tuitions
        tuition_math_a = next((
            t for t in tuitions if t.subject == SubjectEnum.MATH.value and 
            t.teacher_id == test_teacher_orm.id and 
            t.id == tuition_service._generate_deterministic_id(
                SubjectEnum.MATH.value, EducationalSystemEnum.SAT.value, 10, 1, 
                test_teacher_orm.id, sorted([student_a.id])
            )
        ), None)

        tuition_physics_ab = next((
            t for t in tuitions if t.subject == SubjectEnum.PHYSICS.value and 
            t.teacher_id == test_teacher_orm.id and 
            t.id == tuition_service._generate_deterministic_id(
                SubjectEnum.PHYSICS.value, EducationalSystemEnum.SAT.value, 10, 1, 
                test_teacher_orm.id, sorted([student_a.id, student_b.id])
            )
        ), None)

        tuition_chemistry_b = next((
            t for t in tuitions if t.subject == SubjectEnum.CHEMISTRY.value and 
            t.teacher_id == test_unrelated_teacher_orm.id and 
            t.id == tuition_service._generate_deterministic_id(
                SubjectEnum.CHEMISTRY.value, EducationalSystemEnum.SAT.value, 10, 1, 
                test_unrelated_teacher_orm.id, sorted([student_b.id])
            )
        ), None)

        tuition_math_c = next((
            t for t in tuitions if t.subject == SubjectEnum.MATH.value and 
            t.teacher_id == test_teacher_orm.id and 
            t.id == tuition_service._generate_deterministic_id(
                SubjectEnum.MATH.value, EducationalSystemEnum.SAT.value, 10, 1, 
                test_teacher_orm.id, sorted([student_c.id])
            )
        ), None)

        assert tuition_math_a is not None
        assert tuition_physics_ab is not None
        assert tuition_chemistry_b is not None
        assert tuition_math_c is not None

        # Verify Charges
        charges_math_a = [c for c in charges if c.tuition_id == tuition_math_a.id]
        charges_physics_ab = [c for c in charges if c.tuition_id == tuition_physics_ab.id]
        charges_chemistry_b = [c for c in charges if c.tuition_id == tuition_chemistry_b.id]
        charges_math_c = [c for c in charges if c.tuition_id == tuition_math_c.id]

        assert len(charges_math_a) == 1 and charges_math_a[0].student_id == student_a.id
        assert len(charges_physics_ab) == 2
        assert {c.student_id for c in charges_physics_ab} == {student_a.id, student_b.id}
        assert len(charges_chemistry_b) == 1 and charges_chemistry_b[0].student_id == student_b.id
        assert len(charges_math_c) == 1 and charges_math_c[0].student_id == student_c.id

        print(f"--- Successfully regenerated tuitions for complex scenario ---")

    async def test_regenerate_all_tuitions_preserves_meeting_links(
        self,
        tuition_service: TuitionService,
        student_service: StudentService,
        db_session: AsyncSession,
        test_parent_orm: db_models.Parents,
        test_teacher_orm: db_models.Teachers
    ):
        """
        Tests that existing meeting links are preserved during regeneration.
        """
        print("\n--- Testing regenerate_all_tuitions preserves meeting links ---")

        # Clear existing tuitions
        await db_session.execute(delete(db_models.Tuitions))
        await db_session.execute(delete(db_models.TuitionTemplateCharges))
        await db_session.execute(delete(db_models.StudentSubjects))
        await db_session.execute(delete(db_models.MeetingLinks))
        await db_session.flush()

        # 1. Create a student and subject that will form a tuition
        student_email = "student_link@example.com"
        subject_data = user_models.StudentSubjectWrite(
            subject=SubjectEnum.IT,
            educational_system=EducationalSystemEnum.SAT,
            lessons_per_week=1,
            teacher_id=test_teacher_orm.id,
            grade=10,
            shared_with_student_ids=[]
        )
        student = await _create_student_with_subjects(
            student_service, 
            db_session, 
            test_parent_orm, 
            test_teacher_orm, 
            student_email, 
            [subject_data]
        )
        await db_session.flush()

        # 2. Manually create a tuition and a meeting link for it
        # We need to generate the deterministic ID first to create the tuition
        tuition_id = tuition_service._generate_deterministic_id(
            subject=SubjectEnum.IT.value,
            educational_system=EducationalSystemEnum.SAT.value,
            lesson_index=1,
            grade=10,
            teacher_id=test_teacher_orm.id,
            student_ids=sorted([student.id])
        )
        
        # Create the tuition directly
        initial_tuition = db_models.Tuitions(
            id=tuition_id,
            teacher_id=test_teacher_orm.id,
            subject=SubjectEnum.IT.value,
            educational_system=EducationalSystemEnum.SAT.value,
            grade=10,
            lesson_index=1,
            min_duration_minutes=student.min_duration_mins,
            max_duration_minutes=student.max_duration_mins,
        )
        db_session.add(initial_tuition)
        await db_session.flush()

        # Create a meeting link for this tuition
        meeting_link_data = meeting_link_models.MeetingLinkCreate(
            meeting_link_type=MeetingLinkTypeEnum.GOOGLE_MEET,
            meeting_link="https://meet.google.com/preserved-link",
            meeting_id="preserved-id",
            meeting_password="preserved-pass"
        )
        preserved_link = db_models.MeetingLinks(
            tuition_id=tuition_id,
            meeting_link_type=meeting_link_data.meeting_link_type.value,
            meeting_link=str(meeting_link_data.meeting_link),
            meeting_id=meeting_link_data.meeting_id,
            meeting_password=meeting_link_data.meeting_password
        )
        db_session.add(preserved_link)
        await db_session.flush()

        # 3. Run regeneration
        result = await tuition_service.regenerate_all_tuitions()
        assert result is True

        # 4. Assertions
        tuitions = (await db_session.execute(select(db_models.Tuitions))).scalars().all()
        meeting_links = (await db_session.execute(select(db_models.MeetingLinks))).scalars().all()

        assert len(tuitions) == 1
        assert len(meeting_links) == 1

        regenerated_tuition = tuitions[0]
        regenerated_link = meeting_links[0]

        assert regenerated_tuition.id == tuition_id
        assert regenerated_link.tuition_id == tuition_id
        assert regenerated_link.meeting_link == "https://meet.google.com/preserved-link"
        assert regenerated_link.meeting_id == "preserved-id"
        assert regenerated_link.meeting_password == "preserved-pass"
        
        print(f"--- Successfully preserved meeting link for tuition {tuition_id} ---")

    async def test_regenerate_all_tuitions_preserves_tuition_template_charges(
        self,
        tuition_service: TuitionService,
        student_service: StudentService,
        db_session: AsyncSession,
        test_parent_orm: db_models.Parents,
        test_teacher_orm: db_models.Teachers
    ):
        """
        Tests that existing tuition template charges (specifically their cost)
        are preserved during regeneration.
        """
        print("\n--- Testing regenerate_all_tuitions preserves tuition template charges ---")

        # Clear existing tuitions
        await db_session.execute(delete(db_models.Tuitions))
        await db_session.execute(delete(db_models.TuitionTemplateCharges))
        await db_session.execute(delete(db_models.StudentSubjects))
        await db_session.flush()

        # 1. Create a student and subject that will form a tuition
        student_email = "student_charge@example.com"
        subject_data = user_models.StudentSubjectWrite(
            subject=SubjectEnum.GEOGRAPHY,
            educational_system=EducationalSystemEnum.SAT,
            lessons_per_week=1,
            teacher_id=test_teacher_orm.id,
            grade=10,
            shared_with_student_ids=[]
        )
        student = await _create_student_with_subjects(
            student_service, db_session, test_parent_orm, test_teacher_orm, student_email, [subject_data],
            cost=Decimal("50.00") # Initial student cost
        )
        await db_session.flush()

        # 2. Manually create a tuition and a tuition template charge with a custom cost
        tuition_id = tuition_service._generate_deterministic_id(
            subject=SubjectEnum.GEOGRAPHY.value,
            educational_system=EducationalSystemEnum.SAT.value,
            grade=10,
            lesson_index=1,
            teacher_id=test_teacher_orm.id,
            student_ids=sorted([student.id])
        )
        
        initial_tuition = db_models.Tuitions(
            id=tuition_id,
            teacher_id=test_teacher_orm.id,
            subject=SubjectEnum.GEOGRAPHY.value,
            educational_system=EducationalSystemEnum.SAT.value,
            grade=10,
            lesson_index=1,
            min_duration_minutes=student.min_duration_mins,
            max_duration_minutes=student.max_duration_mins,
        )
        db_session.add(initial_tuition)
        await db_session.flush()

        preserved_cost = Decimal("75.00") # Custom cost to be preserved
        preserved_charge = db_models.TuitionTemplateCharges(
            tuition_id=tuition_id,
            student_id=student.id,
            parent_id=student.parent_id,
            cost=preserved_cost
        )
        db_session.add(preserved_charge)
        await db_session.flush()

        # 3. Run regeneration
        result = await tuition_service.regenerate_all_tuitions()
        assert result is True

        # 4. Assertions
        tuitions = (await db_session.execute(select(db_models.Tuitions))).scalars().all()
        charges = (await db_session.execute(select(db_models.TuitionTemplateCharges))).scalars().all()

        assert len(tuitions) == 1
        assert len(charges) == 1

        regenerated_tuition = tuitions[0]
        regenerated_charge = charges[0]

        assert regenerated_tuition.id == tuition_id
        assert regenerated_charge.tuition_id == tuition_id
        assert regenerated_charge.student_id == student.id
        assert regenerated_charge.cost == preserved_cost # Assert that the custom cost was preserved
        
        print(f"--- Successfully preserved tuition template charge cost for tuition {tuition_id} ---")

    async def test_regenerate_all_tuitions_student_subject_missing_teacher_id_raises_error(
        self,
        student_service: StudentService,
        db_session: AsyncSession,
        test_parent_orm: db_models.Parents,
        test_teacher_orm: db_models.Teachers
    ):
        """
        Tests that setting a StudentSubject's teacher_id to None raises an IntegrityError
        due to the NOT NULL constraint in the database.
        """
        print("\n--- Testing that setting teacher_id to None raises IntegrityError ---")

        # 1. Create a student with a valid subject
        student_email = "student_integrity_error@example.com"
        student = await _create_student_with_subjects(
            student_service, db_session, test_parent_orm, test_teacher_orm, student_email, [
                user_models.StudentSubjectWrite(
                    subject=SubjectEnum.BIOLOGY,
                    educational_system=EducationalSystemEnum.SAT,
                    lessons_per_week=1,
                    teacher_id=test_teacher_orm.id,
                    grade=10,
                    shared_with_student_ids=[]
                )
            ]
        )
        await db_session.flush()

        # 2. Attempt to set the teacher_id to None and expect a database error
        student_subject = (await db_session.execute(
            select(db_models.StudentSubjects).filter_by(student_id=student.id)
        )).scalars().first()
        assert student_subject is not None
        
        student_subject.teacher_id = None
        db_session.add(student_subject)

        # 3. Assert that flushing this change raises an IntegrityError
        with pytest.raises(IntegrityError):
            await db_session.flush()
        
        print("--- Successfully caught IntegrityError when teacher_id was set to None. ---")

    async def test_regenerate_all_tuitions_creates_multiple_tuitions_for_lessons_per_week_gt_1(
        self,
        tuition_service: TuitionService,
        student_service: StudentService,
        db_session: AsyncSession,
        test_parent_orm: db_models.Parents,
        test_teacher_orm: db_models.Teachers
    ):
        """
        Tests that a StudentSubject with lessons_per_week > 1 creates a
        corresponding number of tuition templates.
        """
        print("\n--- Testing regenerate with lessons_per_week > 1 creates multiple tuitions ---")

        # ARRANGE
        await db_session.execute(delete(db_models.Tuitions))
        await db_session.execute(delete(db_models.StudentSubjects))
        await db_session.flush()

        lessons_count = 3
        subject_data = user_models.StudentSubjectWrite(
            subject=SubjectEnum.MATH,
            educational_system=EducationalSystemEnum.SAT,
            lessons_per_week=lessons_count, # Key part of this test
            teacher_id=test_teacher_orm.id,
            grade=10,
            shared_with_student_ids=[]
        )
        await _create_student_with_subjects(
            student_service, db_session, test_parent_orm, test_teacher_orm, "student_lpw@example.com", [subject_data]
        )
        await db_session.flush()

        # ACT
        await tuition_service.regenerate_all_tuitions()

        # ASSERT
        tuitions = (await db_session.execute(select(db_models.Tuitions))).scalars().all()
        
        # Assert that 3 tuitions were created
        assert len(tuitions) == lessons_count
        
        # Assert that they all have the same subject but different lesson indices
        lesson_indices = {t.lesson_index for t in tuitions}
        assert all(t.subject == SubjectEnum.MATH.value for t in tuitions)
        assert lesson_indices == {1, 2, 3}
        
        print(f"--- Successfully asserted that {lessons_count} tuitions were created with correct indices. ---")

    async def test_regenerate_all_tuitions_shared_group_with_inconsistent_durations(
        self,
        tuition_service: TuitionService,
        student_service: StudentService,
        db_session: AsyncSession,
        test_parent_orm: db_models.Parents,
        test_teacher_orm: db_models.Teachers
    ):
        """
        Tests the case where students in a shared group have different
        min/max duration settings. It asserts that the resulting tuition
        takes the highest min_duration and highest max_duration among them.
        """
        print("\n--- Testing regenerate with inconsistent durations in a shared group ---")

        await db_session.execute(delete(db_models.Tuitions))
        await db_session.execute(delete(db_models.StudentSubjects))
        await db_session.flush()

        # 1. Create two students with different duration settings
        # Student A: min=60, max=90
        student_a = await _create_student_with_subjects(
            student_service, db_session, test_parent_orm, test_teacher_orm, "student_a_dur@example.com", [],
            min_duration=60, max_duration=90
        )
        # Student B: min=75, max=120
        student_b = await _create_student_with_subjects(
            student_service, db_session, test_parent_orm, test_teacher_orm, "student_b_dur@example.com", [],
            min_duration=75, max_duration=120
        )
        
        # 2. Create the shared subject link between them
        subject_data_a = user_models.StudentSubjectWrite(
            subject=SubjectEnum.CHEMISTRY, 
            educational_system=EducationalSystemEnum.SAT, 
            lessons_per_week=1, 
            teacher_id=test_teacher_orm.id, 
            grade=10,
            shared_with_student_ids=[student_b.id] # Student A shares with B
        )
        student_a_subject = db_models.StudentSubjects(
            student_id=student_a.id, 
            teacher_id=subject_data_a.teacher_id,
            subject=subject_data_a.subject.value, 
            educational_system=subject_data_a.educational_system.value,
            grade=subject_data_a.grade,
            lessons_per_week=subject_data_a.lessons_per_week
        )
        db_session.add(student_a_subject)
        await db_session.flush() # Flush to get student_a_subject.id

        subject_data_b = user_models.StudentSubjectWrite(
            subject=SubjectEnum.CHEMISTRY, 
            educational_system=EducationalSystemEnum.SAT, 
            lessons_per_week=1, 
            teacher_id=test_teacher_orm.id, 
            grade=10,
            shared_with_student_ids=[student_a.id] # Student B shares with A
        )
        student_b_subject = db_models.StudentSubjects(
            student_id=student_b.id, 
            teacher_id=subject_data_b.teacher_id,
            subject=subject_data_b.subject.value, 
            educational_system=subject_data_b.educational_system.value,
            grade=subject_data_b.grade,
            lessons_per_week=subject_data_b.lessons_per_week
        )
        db_session.add(student_b_subject)
        await db_session.flush()

        # Link them bi-directionally in the shared_with_student relationship
        await db_session.execute(db_models.t_student_subject_sharings.insert().values(
            student_subject_id=student_a_subject.id, shared_with_student_id=student_b.id
        ))
        await db_session.execute(db_models.t_student_subject_sharings.insert().values(
            student_subject_id=student_b_subject.id, shared_with_student_id=student_a.id
        ))
        await db_session.flush()

        # 3. Run regeneration
        await tuition_service.regenerate_all_tuitions()
        
        # 4. Assertions
        tuitions = (await db_session.execute(select(db_models.Tuitions))).scalars().all()
        assert len(tuitions) == 1
        
        created_tuition = tuitions[0]
        
        # The expected values are the maximums from Student A (60, 90) and Student B (75, 120)
        expected_min_duration = max(student_a.min_duration_mins, student_b.min_duration_mins)
        expected_max_duration = max(student_a.max_duration_mins, student_b.max_duration_mins)

        assert created_tuition.min_duration_minutes == expected_min_duration
        assert created_tuition.max_duration_minutes == expected_max_duration

        print(f"--- Successfully asserted that tuition durations are max of grouped students: Min={expected_min_duration}, Max={expected_max_duration}. ---")

    ### Tests for _generate_deterministic_id ###
    
    def test_generate_deterministic_id(
        self,
        tuition_service_sync: TuitionService # Request the service to get the method
    ):
        """
        Tests the internal ID generation logic.
        Note: This is a regular 'def' test, not 'async def'.
        """
        # For clarity, assign it to the name the rest of the
        # test expects, or just use tuition_service_sync directly.
        tuition_service = tuition_service_sync

        # Define two lists of student IDs, sorted to ensure order doesn't matter
        student_ids_1 = sorted([TEST_STUDENT_ID, TEST_PARENT_ID]) # Just using 2 IDs
        student_ids_2 = sorted([TEST_STUDENT_ID]) # A different list
        
        # --- Case 1: Same inputs should produce the same UUID ---
        uuid_1 = tuition_service._generate_deterministic_id(
            subject="Math",
            educational_system="SAT",
            grade=10,
            lesson_index=1,
            teacher_id=TEST_TEACHER_ID,
            student_ids=student_ids_1
        )
        
        uuid_2 = tuition_service._generate_deterministic_id(
            subject="Math",
            educational_system="SAT",
            grade=10,
            lesson_index=1,
            teacher_id=TEST_TEACHER_ID,
            student_ids=student_ids_1
        )
        
        assert isinstance(uuid_1, UUID)
        assert uuid_1 == uuid_2, "Same inputs did not produce the same UUID"
        
        # --- Case 2: Different student list should produce a different UUID ---
        uuid_3 = tuition_service._generate_deterministic_id(
            subject="Math",
            educational_system="SAT",
            grade=10,
            lesson_index=1,
            teacher_id=TEST_TEACHER_ID,
            student_ids=student_ids_2 # <-- Different list
        )
        
        assert uuid_1 != uuid_3, "Different student list produced the same UUID"
        
        # --- Case 3: Different subject should produce a different UUID ---
        uuid_4 = tuition_service._generate_deterministic_id(
            subject="Physics", # <-- Different subject
            educational_system="SAT",
            grade=10,
            lesson_index=1,
            teacher_id=TEST_TEACHER_ID,
            student_ids=student_ids_1
        )
        
        assert uuid_1 != uuid_4, "Different subject produced the same UUID"

        # --- Case 4: Different educational system should produce a different UUID ---
        uuid_5 = tuition_service._generate_deterministic_id(
            subject="Math",
            educational_system="IGCSE", # <-- Different system
            grade=10,
            lesson_index=1,
            teacher_id=TEST_TEACHER_ID,
            student_ids=student_ids_1
        )
        assert uuid_1 != uuid_5, "Different educational system produced the same UUID"


# --- Helper Function (to create a link for update/delete tests) ---
# We make this a helper function to avoid duplicating create logic
async def create_test_link(
    db_session: AsyncSession,
    tuition_service: TuitionService,
    tuition_id: UUID,
    current_user: db_models.Users
) -> db_models.Tuitions:
    """Helper to create and flush a meeting link for a tuition."""
    create_data = meeting_link_models.MeetingLinkCreate(
        meeting_link_type=MeetingLinkTypeEnum.GOOGLE_MEET,
        meeting_link="https://meet.google.com/test-link"
    )
    await tuition_service.create_meeting_link_for_api(
        tuition_id, create_data, current_user
    )
    await db_session.flush() # flush this pre-condition
    
    # Re-fetch the tuition with the link eagerly loaded
    stmt = select(db_models.Tuitions).options(
        selectinload(db_models.Tuitions.meeting_link)
    ).filter(db_models.Tuitions.id == tuition_id)
    
    tuition = (await db_session.scalars(stmt)).first()
    assert tuition.meeting_link is not None
    return tuition


@pytest.mark.anyio
class TestMeetingLinkService:
    """
    Tests the meeting link C/U/D methods (assumed to be on TuitionService).
    """

    ### Tests for create_meeting_link_for_api ###

    async def test_create_meeting_link_as_owner(
        self,
        db_session: AsyncSession,
        tuition_service: TuitionService,
        test_teacher_orm: db_models.Users,
        test_tuition_orm_no_link: db_models.Tuitions  # <-- USE THE NEW FIXTURE
    ):
        """Tests that the OWNER (Teacher) can create a meeting link."""
        tuition_id = test_tuition_orm_no_link.id  # <-- Use the clean tuition
        print(f"\n--- Testing create_meeting_link as OWNER TEACHER ---")
        
        create_data = meeting_link_models.MeetingLinkCreate(
            meeting_link_type=MeetingLinkTypeEnum.ZOOM,
            meeting_link="https://zoom.us/j/12345",
            meeting_id="12345",
            meeting_password="pass"
        )
        
        # Act
        link_dict = await tuition_service.create_meeting_link_for_api(
            tuition_id, create_data, test_teacher_orm
        )
        
        await db_session.flush() 
        
        # Verify response
        assert isinstance(link_dict, meeting_link_models.MeetingLinkRead)
        assert link_dict.tuition_id == tuition_id
        assert link_dict.meeting_id == "12345"
        
        # Verify DB object
        await db_session.refresh(test_tuition_orm_no_link, ['meeting_link'])
        assert test_tuition_orm_no_link.meeting_link is not None
        assert test_tuition_orm_no_link.meeting_link.meeting_password == "pass"
        
        print("--- Successfully created meeting link (API dict) ---")
        pprint(link_dict.__dict__)

    async def test_create_meeting_link_as_unrelated_teacher(
        self,
        tuition_service: TuitionService,
        test_unrelated_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions
    ):
        """Tests that an UNRELATED Teacher is FORBIDDEN from creating a link."""
        print(f"\n--- Testing create_meeting_link as UNRELATED TEACHER ---")
        
        create_data = meeting_link_models.MeetingLinkCreate(
            meeting_link_type=MeetingLinkTypeEnum.ZOOM,
            meeting_link="https://zoom.us/j/12345"
        )
        
        with pytest.raises(HTTPException) as e:
            await tuition_service.create_meeting_link_for_api(
                test_tuition_orm.id, create_data, test_unrelated_teacher_orm
            )
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    async def test_create_meeting_link_as_parent(
        self,
        tuition_service: TuitionService,
        test_parent_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions
    ):
        """Tests that a PARENT is FORBIDDEN from creating a link."""
        print(f"\n--- Testing create_meeting_link as PARENT ---")
        
        create_data = meeting_link_models.MeetingLinkCreate(
            meeting_link_type=MeetingLinkTypeEnum.ZOOM,
            meeting_link="https://zoom.us/j/12345"
        )
        
        with pytest.raises(HTTPException) as e:
            await tuition_service.create_meeting_link_for_api(
                test_tuition_orm.id, create_data, test_parent_orm
            )
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    ### Tests for update_meeting_link_for_api ###

    async def test_update_meeting_link_as_owner(
        self,
        db_session: AsyncSession,
        tuition_service: TuitionService,
        test_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions  # <-- This fixture *already has* a link
    ):
        """Tests that the OWNER (Teacher) can update their meeting link."""
        
        # --- THE FIX ---
        # 1. No helper function is needed. Just use the fixture.
        #    The `test_tuition_orm` fixture already has a link.
        tuition = test_tuition_orm
        # -----------------

        print(f"\n--- Testing update_meeting_link as OWNER TEACHER ---")
        print(f"--- Pre-condition: Using tuition {tuition.id} which has link: {tuition.meeting_link.meeting_link} ---")

        # --- Act ---
        update_data = meeting_link_models.MeetingLinkUpdate(
            meeting_link="https://meet.google.com/new-updated-link",
            meeting_link_type=MeetingLinkTypeEnum.GOOGLE_MEET # Pass the enum object
        )
        
        updated_link_dict = await tuition_service.update_meeting_link_for_api(
            tuition.id, update_data, test_teacher_orm
        )
        await db_session.flush() # Send update to DB
        
        # --- Verify Response ---
        assert isinstance(updated_link_dict, meeting_link_models.MeetingLinkRead)
        assert str(updated_link_dict.meeting_link) == "https://meet.google.com/new-updated-link"
        assert updated_link_dict.meeting_link_type == MeetingLinkTypeEnum.GOOGLE_MEET
        
        # --- Verify DB Object ---
        # We refresh the *existing* meeting_link object
        await db_session.refresh(tuition.meeting_link) 
        assert tuition.meeting_link.meeting_link == "https://meet.google.com/new-updated-link"
        assert tuition.meeting_link.meeting_link_type == MeetingLinkTypeEnum.GOOGLE_MEET.value
        
        print("--- Successfully updated meeting link (API dict) ---")
        pprint(updated_link_dict)

    async def test_update_meeting_link_as_unrelated_teacher(
        self,
        db_session: AsyncSession, # Retained for consistency
        tuition_service: TuitionService,
        test_unrelated_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions # This fixture has the link
    ):
        """Tests that an UNRELATED Teacher is FORBIDDEN from updating a link."""
        
        # Use the fixture directly, it already has the link
        tuition = test_tuition_orm
        
        print(f"\n--- Testing update_meeting_link as UNRELATED TEACHER ---")
        print(f"--- Using Tuition ID: {tuition.id} ---")
        print(f"--- Unrelated Teacher ID: {test_unrelated_teacher_orm.id} ---")

        # --- Act & Assert ---
        update_data = meeting_link_models.MeetingLinkUpdate(
            meeting_link="https://meet.google.com/forbidden-link"
        )
        
        with pytest.raises(HTTPException) as e:
            await tuition_service.update_meeting_link_for_api(
                tuition.id, update_data, test_unrelated_teacher_orm
            )
        
        assert e.value.status_code == 403
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")

    ### Tests for delete_meeting_link ###

    async def test_delete_meeting_link_as_owner(
        self,
        db_session: AsyncSession,
        tuition_service: TuitionService,
        test_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions # <-- This fixture has the link
    ):
        """Tests that the OWNER (Teacher) can delete their meeting link."""
        
        # --- Setup: Use the fixture directly ---
        tuition = test_tuition_orm
        tuition_id = tuition.id
        
        print(f"\n--- Testing delete_meeting_link as OWNER TEACHER ---")
        
        # Verify the link exists before we try to delete it
        assert tuition.meeting_link is not None
        print(f"--- Pre-condition: Link exists for tuition {tuition.id} ---")

        # --- Act ---
        await tuition_service.delete_meeting_link(tuition_id, test_teacher_orm)
        await db_session.flush() # Send DELETE to DB
        
        # --- Verify DB Object ---
        # We refresh the *parent* tuition. Its 'meeting_link' relationship
        # will now be None because the link row is gone.
        await db_session.refresh(tuition, ['meeting_link'])
        assert tuition.meeting_link is None
        
        print(f"--- Successfully deleted link. tuition.meeting_link is now None. ---")
        # The test's final rollback will restore this deleted link.

    async def test_delete_meeting_link_as_unrelated_teacher(
        self,
        db_session: AsyncSession,
        tuition_service: TuitionService,
        test_unrelated_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions # <-- This fixture has the link
    ):
        """Tests that an UNRELATED Teacher is FORBIDDEN from deleting a link."""
        
        tuition = test_tuition_orm
        print(f"\n--- Testing delete_meeting_link as UNRELATED TEACHER ---")
        
        # Verify the link exists to start
        assert tuition.meeting_link is not None

        # --- Act & Assert ---
        with pytest.raises(HTTPException) as e:
            await tuition_service.delete_meeting_link(
                tuition.id, test_unrelated_teacher_orm
            )
        
        assert e.value.status_code == 403
        
        # --- Verify link was NOT deleted ---
        # We refresh just to be 100% sure the DB state hasn't changed
        await db_session.refresh(tuition, ['meeting_link'])
        assert tuition.meeting_link is not None
        
        print(f"--- Correctly raised HTTPException: {e.value.status_code} ---")


@pytest.mark.anyio
class TestTuitionServiceUpdate:
    """Tests for the update_tuition_by_id method in TuitionService."""

    async def test_update_tuition_happy_path(
        self,
        tuition_service: TuitionService,
        db_session: AsyncSession,
        test_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions
    ):
        """
        Tests that a teacher can successfully update durations and charges.
        """
        print("\n--- Testing update_tuition_by_id: Happy Path ---")
        tuition_id = test_tuition_orm.id
        
        # Get original charges to construct the update
        original_charges = test_tuition_orm.tuition_template_charges
        assert len(original_charges) > 0, "Test tuition must have charges to update."
        
        student_id_to_update = original_charges[0].student_id
        new_cost = Decimal("99.99")

        update_data = tuition_models.TuitionUpdate(
            min_duration_minutes=75,
            max_duration_minutes=100,
            charges=[
                tuition_models.TuitionChargeUpdate(student_id=student_id_to_update, cost=new_cost)
            ]
        )

        # Act
        updated_tuition = await tuition_service.update_tuition_by_id(
            tuition_id, update_data, test_teacher_orm
        )
        await db_session.flush()

        # Assert response
        assert isinstance(updated_tuition, tuition_models.TuitionReadForTeacher)
        assert updated_tuition.min_duration_minutes == 75
        assert updated_tuition.max_duration_minutes == 100
        updated_charge_in_response = next(
            (c for c in updated_tuition.charges if c.student.id == student_id_to_update), None
        )
        assert updated_charge_in_response is not None
        assert Decimal(updated_charge_in_response.cost) == new_cost

        # Assert database state
        await db_session.refresh(test_tuition_orm)
        assert test_tuition_orm.min_duration_minutes == 75
        assert test_tuition_orm.max_duration_minutes == 100
        
        updated_charge_in_db = next(
            (c for c in test_tuition_orm.tuition_template_charges if c.student_id == student_id_to_update), None
        )
        assert updated_charge_in_db is not None
        assert updated_charge_in_db.cost == new_cost
        print("--- Successfully updated tuition durations and charges. ---")

    async def test_update_tuition_unauthorized_teacher(
        self,
        tuition_service: TuitionService,
        test_unrelated_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions
    ):
        """
        Tests that a teacher who does not own the tuition gets a 403 error.
        """
        print("\n--- Testing update_tuition_by_id: Unauthorized Teacher ---")
        update_data = tuition_models.TuitionUpdate(min_duration_minutes=100)

        with pytest.raises(HTTPException) as exc_info:
            await tuition_service.update_tuition_by_id(
                test_tuition_orm.id, update_data, test_unrelated_teacher_orm
            )
        
        assert exc_info.value.status_code == 403
        print("--- Correctly raised 403 for unauthorized teacher. ---")

    async def test_update_tuition_as_parent(
        self,
        tuition_service: TuitionService,
        test_parent_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions
    ):
        """
        Tests that a parent gets a 403 error when trying to update.
        """
        print("\n--- Testing update_tuition_by_id: As Parent ---")
        update_data = tuition_models.TuitionUpdate(min_duration_minutes=100)

        with pytest.raises(HTTPException) as exc_info:
            await tuition_service.update_tuition_by_id(
                test_tuition_orm.id, update_data, test_parent_orm
            )
        
        assert exc_info.value.status_code == 403
        print("--- Correctly raised 403 for parent. ---")

    async def test_update_tuition_not_found(
        self,
        tuition_service: TuitionService,
        test_teacher_orm: db_models.Users
    ):
        """
        Tests that updating a non-existent tuition raises a 404 error.
        """
        print("\n--- Testing update_tuition_by_id: Not Found ---")
        non_existent_uuid = uuid4()
        update_data = tuition_models.TuitionUpdate(min_duration_minutes=100)

        with pytest.raises(HTTPException) as exc_info:
            await tuition_service.update_tuition_by_id(
                non_existent_uuid, update_data, test_teacher_orm
            )
        
        assert exc_info.value.status_code == 404
        print("--- Correctly raised 404 for non-existent tuition. ---")

    async def test_update_tuition_invalid_duration(
        self,
        tuition_service: TuitionService,
        test_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions
    ):
        """
        Tests that setting max_duration < min_duration raises a 400 error.
        """
        print("\n--- Testing update_tuition_by_id: Invalid Duration ---")
        with pytest.raises(ValidationError) as exc_info:
            tuition_models.TuitionUpdate(
                min_duration_minutes=100,
                max_duration_minutes=50
            )
        
        assert "max_duration_minutes cannot be less than min_duration_minutes" in str(exc_info.value)
        print("--- Correctly raised ValidationError for invalid duration. ---")

    async def test_update_tuition_invalid_student_id_in_charges(
        self,
        tuition_service: TuitionService,
        test_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions
    ):
        """
        Tests that updating a charge for a student not in the tuition raises a 400 error.
        """
        print("\n--- Testing update_tuition_by_id: Invalid Student ID in Charges ---")
        non_existent_student_id = uuid4()
        update_data = tuition_models.TuitionUpdate(
            charges=[
                tuition_models.TuitionChargeUpdate(student_id=non_existent_student_id, cost=Decimal("100.00"))
            ]
        )

        with pytest.raises(HTTPException) as exc_info:
            await tuition_service.update_tuition_by_id(
                test_tuition_orm.id, update_data, test_teacher_orm
            )
        
        assert exc_info.value.status_code == 400
        assert "One or more student IDs are not part of this tuition" in exc_info.value.detail
        print("--- Correctly raised 400 for invalid student ID in charges. ---")

    async def test_update_tuition_empty_payload(
        self,
        tuition_service: TuitionService,
        test_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions
    ):
        """
        Tests that sending an empty update payload raises a 400 error.
        """
        print("\n--- Testing update_tuition_by_id: Empty Payload ---")
        update_data = tuition_models.TuitionUpdate() # Empty update

        with pytest.raises(HTTPException) as exc_info:
            await tuition_service.update_tuition_by_id(
                test_tuition_orm.id, update_data, test_teacher_orm
            )
        
        assert exc_info.value.status_code == 400
        assert "No update data provided" in exc_info.value.detail
        print("--- Correctly raised 400 for empty payload. ---")

    async def test_update_tuition_partial_durations(
        self,
        tuition_service: TuitionService,
        db_session: AsyncSession,
        test_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions
    ):
        """
        Tests that updating only min_duration_minutes works correctly.
        """
        print("\n--- Testing update_tuition_by_id: Partial Durations ---")
        original_max = test_tuition_orm.max_duration_minutes
        update_data = tuition_models.TuitionUpdate(min_duration_minutes=30)

        await tuition_service.update_tuition_by_id(
            test_tuition_orm.id, update_data, test_teacher_orm
        )
        await db_session.flush()

        await db_session.refresh(test_tuition_orm)
        assert test_tuition_orm.min_duration_minutes == 30
        assert test_tuition_orm.max_duration_minutes == original_max # Should not change
        print("--- Successfully performed partial update on durations. ---")

    async def test_update_tuition_partial_charges(
        self,
        tuition_service: TuitionService,
        db_session: AsyncSession,
        test_teacher_orm: db_models.Users,
        test_tuition_orm: db_models.Tuitions
    ):
        """
        Tests that updating only charges works correctly.
        """
        print("\n--- Testing update_tuition_by_id: Partial Charges ---")
        original_min = test_tuition_orm.min_duration_minutes
        original_max = test_tuition_orm.max_duration_minutes
        
        student_id_to_update = test_tuition_orm.tuition_template_charges[0].student_id
        new_cost = Decimal("123.45")

        update_data = tuition_models.TuitionUpdate(
            charges=[
                tuition_models.TuitionChargeUpdate(student_id=student_id_to_update, cost=new_cost)
            ]
        )

        await tuition_service.update_tuition_by_id(
            test_tuition_orm.id, update_data, test_teacher_orm
        )
        await db_session.flush()

        await db_session.refresh(test_tuition_orm)
        assert test_tuition_orm.min_duration_minutes == original_min # Should not change
        assert test_tuition_orm.max_duration_minutes == original_max # Should not change
        
        updated_charge_in_db = next(
            (c for c in test_tuition_orm.tuition_template_charges if c.student_id == student_id_to_update), None
        )
        assert updated_charge_in_db is not None
        assert updated_charge_in_db.cost == new_cost
        print("--- Successfully performed partial update on charges. ---")

