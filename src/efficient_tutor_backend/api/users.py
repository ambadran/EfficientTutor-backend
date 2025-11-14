'''
API endpoints for CRUD operations on User resources (Admins, Parents, Students, Teachers).
'''
from typing import Annotated, List
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
                response_model=List[user_models.AdminRead])
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
                response_model=List[user_models.ParentRead])
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
        return Response(status_code=status.HTTP_204_NO_CONTENT)


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
                response_model=List[user_models.StudentRead])
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

    async def create(
        self,
        student_data: user_models.StudentCreate,
        current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)],
        student_service: Annotated[StudentService, Depends(StudentService)],
        tuition_service: Annotated[TuitionService, Depends(TuitionService)] # Inject TuitionService
    ):
        new_student = await student_service.create_student(student_data, current_user)
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
                response_model=List[user_models.TeacherRead])
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

    async def get_all(self, current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)], teacher_service: Annotated[TeacherService, Depends(TeacherService)]):
        teachers = await teacher_service.get_all(current_user)
        return to_pydantic_list(teachers, user_models.TeacherRead)

    async def get_by_id(self, teacher_id: UUID, user_service: Annotated[UserService, Depends(UserService)]):
        teacher = await user_service.get_user_by_id(teacher_id)
        if not teacher or not isinstance(teacher, db_models.Teachers):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
        return user_models.TeacherRead.model_validate(teacher)

    async def update(self, teacher_id: UUID, update_data: user_models.TeacherUpdate, current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)], teacher_service: Annotated[TeacherService, Depends(TeacherService)]):
        return await teacher_service.update_teacher(teacher_id, update_data, current_user)

    async def delete(self, teacher_id: UUID, current_user: Annotated[db_models.Users, Depends(verify_token_and_get_user)], teacher_service: Annotated[TeacherService, Depends(TeacherService)]):
        await teacher_service.delete_teacher(teacher_id, current_user)
        return Response(status_code=status.HTTP_204_NO_CONTENT)


# Instantiate and combine routers
admins_api = AdminsAPI()
parents_api = ParentsAPI()
students_api = StudentsAPI()
teachers_api = TeachersAPI()

router = APIRouter()
router.include_router(admins_api.router)
router.include_router(parents_api.router)
router.include_router(students_api.router)
router.include_router(teachers_api.router)
