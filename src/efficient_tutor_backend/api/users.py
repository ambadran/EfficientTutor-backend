'''
API endpoints for CRUD operations on User resources (Admins, Parents, Students, Teachers).
'''
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, status, Response, HTTPException

from ..database import models as db_models
from ..models import user as user_models
from ..services.security import verify_token_and_get_user
from ..services.user_service import AdminService, ParentService, StudentService, TeacherService, UserService
from ..services.tuition_service import TuitionService # Import TuitionService


# Helper function to convert ORM objects to Pydantic models
def to_pydantic_list(orm_list: list, model):
    return [model.model_validate(item) for item in orm_list]


class UserAPI:
    """Endpoints for general user actions."""
    def __init__(self):
        self.router = APIRouter(tags=["Users"])
        self._register_routes()

    def _register_routes(self):
        self.router.add_api_route("/users/me", self.read_users_me, methods=["GET"], response_model=user_models.UserRead)

    async def read_users_me(
        self,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)]
    ):
        """
        Returns the profile information for the currently authenticated user.
        """
        return current_user


class AdminsAPI:
    """CRUD endpoints for Admin users."""
    def __init__(self):
        self.router = APIRouter(
                prefix="/admins",
                tags=["Admins"])
        self._register_routes()

    def _register_routes(self):
        self.router.add_api_route(
                "/", 
                self.get_all,
                methods=["GET"], 
                response_model=list[user_models.AdminRead])
        self.router.add_api_route(
                "/{admin_id}",
                self.get_by_id, 
                methods=["GET"], 
                response_model=user_models.AdminRead)
        self.router.add_api_route(
                "/{admin_id}", 
                self.update,
                methods=["PATCH"], 
                response_model=user_models.AdminRead)
        self.router.add_api_route(
                "/{admin_id}", 
                self.delete,
                methods=["DELETE"], 
                status_code=status.HTTP_204_NO_CONTENT)

    async def get_all(self, current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)], admin_service: Annotated[AdminService, Depends(AdminService)]):
        admins = await admin_service.get_all(current_user)
        return to_pydantic_list(admins, user_models.AdminRead)

    async def get_by_id(self, admin_id: UUID, user_service: Annotated[UserService, Depends(UserService)]):
        admin = await user_service.get_user_by_id(admin_id)
        if not admin or not isinstance(admin, db_models.Admins):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")
        return user_models.AdminRead.model_validate(admin)

    async def update(self, admin_id: UUID, update_data: user_models.AdminUpdate, current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)], admin_service: Annotated[AdminService, Depends(AdminService)]):
        return await admin_service.update_admin(admin_id, update_data, current_user)

    async def delete(self, admin_id: UUID, current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)], admin_service: Annotated[AdminService, Depends(AdminService)]):
        await admin_service.delete_admin(admin_id, current_user)
        return Response(status_code=status.HTTP_204_NO_CONTENT)


class ParentsAPI:
    """CRUD endpoints for Parent users."""
    def __init__(self):
        self.router = APIRouter(
                prefix="/parents", 
                tags=["Parents"])
        self._register_routes()

    def _register_routes(self):
        self.router.add_api_route(
                "/", 
                self.get_all,
                methods=["GET"], 
                response_model=list[user_models.ParentRead])
        self.router.add_api_route(
                "/{parent_id}", 
                self.get_by_id,
                methods=["GET"], 
                response_model=user_models.ParentRead)
        self.router.add_api_route(
                "/{parent_id}", 
                self.update,
                methods=["PATCH"], 
                response_model=user_models.ParentRead)
        self.router.add_api_route(
                "/{parent_id}", 
                self.delete, 
                methods=["DELETE"], 
                status_code=status.HTTP_204_NO_CONTENT)

    async def get_all(self, current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)], parent_service: Annotated[ParentService, Depends(ParentService)]):
        parents = await parent_service.get_all(current_user)
        return to_pydantic_list(parents, user_models.ParentRead)

    async def get_by_id(self, parent_id: UUID, user_service: Annotated[UserService, Depends(UserService)]):
        parent = await user_service.get_user_by_id(parent_id)
        if not parent or not isinstance(parent, db_models.Parents):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent not found")
        return user_models.ParentRead.model_validate(parent)

    async def update(self, parent_id: UUID, update_data: user_models.ParentUpdate, current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)], parent_service: Annotated[ParentService, Depends(ParentService)]):
        return await parent_service.update_parent(parent_id, update_data, current_user)

    async def delete(self, parent_id: UUID, current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)], parent_service: Annotated[ParentService, Depends(ParentService)]):
        await parent_service.delete_parent(parent_id, current_user)


class StudentsAPI:
    """CRUD endpoints for Student users."""
    def __init__(self):
        self.router = APIRouter(
                prefix="/students", 
                tags=["Students"])
        self._register_routes()

    def _register_routes(self):
        self.router.add_api_route(
                "/", 
                self.create,
                methods=["POST"], 
                status_code=status.HTTP_201_CREATED, 
                response_model=user_models.StudentRead)
        self.router.add_api_route(
                "/", 
                self.get_all,
                methods=["GET"],
                response_model=list[user_models.StudentRead])
        self.router.add_api_route(
                "/{student_id}", 
                self.get_by_id, 
                methods=["GET"], 
                response_model=user_models.StudentRead)
        self.router.add_api_route(
                "/{student_id}", 
                self.update, 
                methods=["PATCH"], 
                response_model=user_models.StudentRead)
        self.router.add_api_route(
                "/{student_id}", 
                self.delete, 
                methods=["DELETE"], 
                status_code=status.HTTP_204_NO_CONTENT)
        self.router.add_api_route(
                "/{student_id}/availability",
                self.add_availability_interval,
                methods=["POST"],
                status_code=status.HTTP_201_CREATED,
                response_model=user_models.AvailabilityIntervalRead)
        self.router.add_api_route(
                "/{student_id}/availability/{interval_id}",
                self.update_availability_interval,
                methods=["PATCH"],
                response_model=user_models.AvailabilityIntervalRead)
        self.router.add_api_route(
                "/{student_id}/availability/{interval_id}",
                self.delete_availability_interval,
                methods=["DELETE"],
                status_code=status.HTTP_204_NO_CONTENT)

    async def create(
        self,
        student_data: user_models.StudentCreate,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        student_service: Annotated[StudentService, Depends(StudentService)],
        tuition_service: Annotated[TuitionService, Depends(TuitionService)] # Inject TuitionService
    ):
        new_student = await student_service.create_student(student_data, current_user)
        #TODO: should be moved to the (to-be) made update tuition endpoints, triggered by admins only.
        await tuition_service.regenerate_all_tuitions() # Call regenerate
        return new_student

    async def get_all(self, current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)], student_service: Annotated[StudentService, Depends(StudentService)]):
        students = await student_service.get_all(current_user)
        return to_pydantic_list(students, user_models.StudentRead)

    async def get_by_id(self, student_id: UUID, user_service: Annotated[UserService, Depends(UserService)]):
        student = await user_service.get_user_by_id(student_id)
        if not student or not isinstance(student, db_models.Students):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
        return user_models.StudentRead.model_validate(student)

    async def update(
        self,
        student_id: UUID,
        update_data: user_models.StudentUpdate,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        student_service: Annotated[StudentService, Depends(StudentService)],
        tuition_service: Annotated[TuitionService, Depends(TuitionService)] # Inject TuitionService
    ):
        updated_student = await student_service.update_student(student_id, update_data, current_user)
        await tuition_service.regenerate_all_tuitions() # Call regenerate
        return updated_student

    async def delete(
        self,
        student_id: UUID,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        student_service: Annotated[StudentService, Depends(StudentService)],
        tuition_service: Annotated[TuitionService, Depends(TuitionService)] # Inject TuitionService
    ):
        await student_service.delete_student(student_id, current_user)
        await tuition_service.regenerate_all_tuitions() # Call regenerate

    async def add_availability_interval(
        self,
        student_id: UUID,
        interval_data: user_models.AvailabilityIntervalCreate,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        student_service: Annotated[StudentService, Depends(StudentService)]
    ):
        return await student_service.add_availability_interval(student_id, interval_data, current_user)

    async def update_availability_interval(
        self,
        student_id: UUID,
        interval_id: UUID,
        update_data: user_models.AvailabilityIntervalUpdate,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        student_service: Annotated[StudentService, Depends(StudentService)]
    ):
        return await student_service.update_availability_interval(student_id, interval_id, update_data, current_user)

    async def delete_availability_interval(
        self,
        student_id: UUID,
        interval_id: UUID,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        student_service: Annotated[StudentService, Depends(StudentService)]
    ):
        await student_service.delete_availability_interval(student_id, interval_id, current_user)
        return Response(status_code=status.HTTP_204_NO_CONTENT)


class TeachersAPI:
    """CRUD endpoints for Teacher users."""
    def __init__(self):
        self.router = APIRouter(
                prefix="/teachers", 
                tags=["Teachers"])
        self._register_routes()

    def _register_routes(self):
        self.router.add_api_route(
                "/", 
                self.get_all, 
                methods=["GET"], 
                response_model=list[user_models.TeacherRead])
        self.router.add_api_route(
                "/by_specialty",
                self.get_all_by_specialty,
                methods=["GET"],
                response_model=list[user_models.TeacherRead])
        self.router.add_api_route(
                "/{teacher_id}/specialties",
                self.get_specialties_for_teacher,
                methods=["GET"],
                response_model=list[user_models.TeacherSpecialtyRead])
        self.router.add_api_route(
                "/{teacher_id}", 
                self.get_by_id, 
                methods=["GET"], 
                response_model=user_models.TeacherRead)
        self.router.add_api_route(
                "/{teacher_id}", 
                self.update, 
                methods=["PATCH"], 
                response_model=user_models.TeacherRead)
        self.router.add_api_route(
                "/{teacher_id}", 
                self.delete, 
                methods=["DELETE"], 
                status_code=status.HTTP_204_NO_CONTENT)
        self.router.add_api_route(
                "/{teacher_id}/specialties",
                self.add_specialty,
                methods=["POST"],
                status_code=status.HTTP_201_CREATED,
                response_model=user_models.TeacherRead)
        self.router.add_api_route(
                "/{teacher_id}/specialties/{specialty_id}",
                self.delete_specialty,
                methods=["DELETE"],
                status_code=status.HTTP_204_NO_CONTENT)
        self.router.add_api_route(
                "/{teacher_id}/availability",
                self.add_availability_interval,
                methods=["POST"],
                status_code=status.HTTP_201_CREATED,
                response_model=user_models.AvailabilityIntervalRead)
        self.router.add_api_route(
                "/{teacher_id}/availability/{interval_id}",
                self.update_availability_interval,
                methods=["PATCH"],
                response_model=user_models.AvailabilityIntervalRead)
        self.router.add_api_route(
                "/{teacher_id}/availability/{interval_id}",
                self.delete_availability_interval,
                methods=["DELETE"],
                status_code=status.HTTP_204_NO_CONTENT)

    async def get_specialties_for_teacher(
        self,
        teacher_id: UUID,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        teacher_service: Annotated[TeacherService, Depends(TeacherService)]
    ) -> list[user_models.TeacherSpecialtyRead]:
        """
        Retrieves all specialties for a specific teacher.
        Authorized for the teacher themselves or an admin.
        """
        return await teacher_service.get_specialties(teacher_id, current_user)

    async def get_all(self, current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)], teacher_service: Annotated[TeacherService, Depends(TeacherService)]):
        teachers = await teacher_service.get_all(current_user)
        return to_pydantic_list(teachers, user_models.TeacherRead)

    async def get_all_by_specialty(self, current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)], query: Annotated[user_models.TeacherSpecialtyQuery, Depends()], teacher_service: Annotated[TeacherService, Depends(TeacherService)]):
        """
        Gets all teachers that match a specific specialty query.
        """
        teachers = await teacher_service.get_all_for_student_subject(query, current_user)
        return to_pydantic_list(teachers, user_models.TeacherRead)

    async def get_by_id(self, teacher_id: UUID, user_service: Annotated[UserService, Depends(UserService)]):
        teacher = await user_service.get_user_by_id(teacher_id)
        if not teacher or not isinstance(teacher, db_models.Teachers):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
        return user_models.TeacherRead.model_validate(teacher)

    async def update(self, teacher_id: UUID, update_data: user_models.TeacherUpdate, current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)], teacher_service: Annotated[TeacherService, Depends(TeacherService)]):
        return await teacher_service.update_teacher(teacher_id, update_data, current_user)

    async def delete(self, teacher_id: UUID, current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)], teacher_service: Annotated[TeacherService, Depends(TeacherService)]):
        success = await teacher_service.delete_teacher(teacher_id, current_user)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found or could not be deleted.")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def add_specialty(
        self,
        teacher_id: UUID,
        specialty_data: user_models.TeacherSpecialtyWrite,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        teacher_service: Annotated[TeacherService, Depends(TeacherService)]
    ):
        """
        Adds a new specialty to a teacher's profile.
        """
        return await teacher_service.add_specialty_to_teacher(teacher_id, specialty_data, current_user)

    async def delete_specialty(
        self,
        teacher_id: UUID,
        specialty_id: UUID,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        teacher_service: Annotated[TeacherService, Depends(TeacherService)]
    ):
        """
        Deletes a specialty from a teacher's profile.
        """
        success = await teacher_service.delete_teacher_specialty(teacher_id, specialty_id, current_user)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specialty not found or could not be deleted.")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def add_availability_interval(
        self,
        teacher_id: UUID,
        interval_data: user_models.AvailabilityIntervalCreate,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        teacher_service: Annotated[TeacherService, Depends(TeacherService)]
    ):
        return await teacher_service.add_availability_interval(teacher_id, interval_data, current_user)

    async def update_availability_interval(
        self,
        teacher_id: UUID,
        interval_id: UUID,
        update_data: user_models.AvailabilityIntervalUpdate,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        teacher_service: Annotated[TeacherService, Depends(TeacherService)]
    ):
        return await teacher_service.update_availability_interval(teacher_id, interval_id, update_data, current_user)

    async def delete_availability_interval(
        self,
        teacher_id: UUID,
        interval_id: UUID,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        teacher_service: Annotated[TeacherService, Depends(TeacherService)]
    ):
        await teacher_service.delete_availability_interval(teacher_id, interval_id, current_user)
        return Response(status_code=status.HTTP_204_NO_CONTENT)


# Instantiate and combine routers
user_api = UserAPI()
admins_api = AdminsAPI()
parents_api = ParentsAPI()
students_api = StudentsAPI()
teachers_api = TeachersAPI()

router = APIRouter()
router.include_router(user_api.router)
router.include_router(admins_api.router)
router.include_router(parents_api.router)
router.include_router(students_api.router)
router.include_router(teachers_api.router)
