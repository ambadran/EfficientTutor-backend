'''

'''

# --- Service/Manager Classes (Plural Classes) ---
UserType = TypeVar("UserType", bound=User)

class Users:
    """Base service class that provides database access and common methods."""
    # Subclasses MUST define these two attributes
    _model: Type[UserType]
    _role: UserRole
    def __init__(self):
        self.db = DatabaseHandler()

    def get_by_id(self, user_id: UUID) -> Optional[UserType]:
        """
        A generic method to fetch any user by their ID, validating against
        the specific subclass model and role.
        """
        user_data = self.db.get_user_by_id(user_id)
        # Use the class attributes from the subclass (e.g., Parents._model, Parents._role)
        if user_data and user_data.get('role') == self._role.name:
            return self._model.model_validate(user_data)
        log.warning(f"Could not find a {self._role.name} with ID {user_id}.")
        return None

    def get_all(self) -> list[UserType]:
        """
        A generic method to fetch all users of a specific role.
        Includes detailed error logging for validation failures.
        """
        all_user_data = self.db.get_all_users_by_role(self._role.name)
        validated_users = []
        for data in all_user_data:
            try:
                # Use the subclass's specific model for validation
                validated_users.append(self._model.model_validate(data))
            except ValidationError as e:
                log.error(f"Pydantic validation failed for {self._role.name} data: {data}")
                log.error(f"Validation error details: {e}")
                continue 
        return validated_users

    def get_all_for_api(self) -> list[dict[str, Any]]:
        """
        A generic method to fetch all users of a specific type and format them
        into a lean list of dictionaries for API responses.
        """
        log.info(f"Fetching and preparing API list for {self.__class__.__name__}...")
        all_users_of_type = self.get_all()
        api_users = [ApiUser.model_validate(user) for user in all_users_of_type]
        return [model.model_dump() for model in api_users]

    def delete(self, user_id: UUID) -> bool:
        """Deletes any user by their ID. Inherited by all service classes."""
        return self.db.delete_user(user_id)

class Parents(Users):
    """Service class for managing Parent users."""
    _model = Parent
    _role = UserRole.parent
    def create(self, email: str, password: str, first_name: str, last_name: str, currency: str = 'EGP') -> Optional[Parent]:
        """Creates a new parent and returns the Parent model instance."""
        new_id = self.db.create_parent(
            email=email, password=password, first_name=first_name, 
            last_name=last_name, currency=currency
        )
        return self.get_by_id(new_id) if new_id else None

    def get_all_for_api(self, teacher_id: UUID) -> list[dict[str, Any]]:
        """
        OVERRIDDEN: Fetches a lean list of ONLY the parents associated with a
        specific teacher for API responses.
        """
        log.info(f"Fetching and preparing API list of parents for teacher {teacher_id}...")
        
        # 1. Get the list of relevant parent IDs from the database.
        parent_ids = self.db.get_parent_ids_for_teacher(teacher_id)
        if not parent_ids:
            return []
            
        # 2. Fetch all user details for those specific parents in one batch.
        parents_data = self.db.get_users_by_ids(parent_ids)
        
        # 3. Hydrate the raw data into our rich Pydantic models.
        validated_parents = [Parent.model_validate(data) for data in parents_data]
        
        # 4. Convert the rich models to the lean ApiUser models.
        api_users = [ApiUser.model_validate(user) for user in validated_parents]
        
        # 5. Return the final list of dictionaries.
        return [model.model_dump() for model in api_users]

class Students(Users):
    """Service class for managing Student users."""
    _model = Student
    _role = UserRole.student
    def get_by_parent(self, parent_id: UUID) -> list[Student]:
        """Fetches all students belonging to a specific parent."""
        students_data = self.db.get_students_by_parent_id(parent_id)
        return [Student.model_validate(data) for data in students_data]

    def get_all(self, viewer_id: UUID) -> list[Student]:
        """
        NEW: A generic method to fetch all students relevant to a given viewer.
        - If viewer is a Parent, returns their children.
        - If viewer is a Teacher, returns all students they have taught.
        """
        log.info(f"Fetching all students relevant to viewer {viewer_id}")
        role = self.db.identify_user_role(viewer_id)

        students_data = []
        if role == UserRole.parent.name:
            # We already have a method for this, so we reuse it.
            students_data = self.db.get_students_by_parent_id(viewer_id)
        elif role == UserRole.teacher.name:
            # Use our new database method for this case.
            students_data = self.db.get_students_for_teacher(viewer_id)
        else:
            log.warning(f"User {viewer_id} with role '{role}' is not authorized to view student lists. Returning empty.")
            return []
            
        return [Student.model_validate(data) for data in students_data]

    def get_all_for_api(self, viewer_id: UUID) -> list[dict[str, Any]]:
        """
        NEW & OVERRIDDEN: Fetches all students relevant to a viewer and formats
        them into a lean list of dictionaries for API responses.
        """
        log.info(f"Fetching and preparing student API list for viewer {viewer_id}...")
        
        # 1. Get the rich, filtered Student objects using our new get_all method.
        all_students = self.get_all(viewer_id)
        
        # 2. Convert the full Student objects into the leaner ApiUser models.
        api_users = [ApiUser.model_validate(user) for user in all_students]
        
        # 3. Convert the models to a list of dictionaries for the final JSON response.
        return [model.model_dump() for model in api_users]
   
    # Note: A create method for students would be more complex, requiring details for
    # both the 'users' and 'students' tables. It can be added here following the same pattern.

class Teachers(Users):
    """Service class for managing Teacher users."""
    _model = Teacher
    _role = UserRole.teacher

    def create(self, email: str, password: str, first_name: str, last_name: str) -> Optional[Teacher]:
        """Creates a new teacher and returns the Teacher model instance."""
        new_id = self.db.create_teacher(
            email=email, password=password, first_name=first_name, last_name=last_name
        )
        return self.get_by_id(new_id) if new_id else None
