'''

'''
class TimeTable:
    """
    Service class for viewing the generated timetable.
    It fetches the latest valid timetable run and processes the solution data.
    """
    def __init__(self):
        self.db = DatabaseHandler()
        self.tuitions_service = Tuitions()

    def get_all(self, viewer_id: UUID) -> list[ScheduledTuition]:
        """
        Fetches the latest successful timetable, filters for tuition events,
        and returns a list of fully hydrated ScheduledTuition objects.
        """
        log.info(f"Fetching latest scheduled tuitions for viewer {viewer_id}...")

        # 1. Fetch only the tuition objects relevant to the viewer.
        all_tuitions_dict = {t.id: t for t in self.tuitions_service.get_all(viewer_id=viewer_id)}
        if not all_tuitions_dict:
            log.warning(f"No tuitions exist for viewer {viewer_id}. Cannot schedule anything.")
            return []

        # 2. Get the raw solution data from the latest timetable run
        solution_data = self.db.get_latest_timetable_solution()
        if not solution_data:
            return []

        scheduled_tuitions = []
        try:
            # 3. Filter, validate, and hydrate the tuition events
            for event in solution_data:
                # We only care about tuition events that have an ID
                if event.get('category') == 'Tuition' and 'id' in event:
                    tuition_id_str = event['id']
                    tuition_id = UUID(tuition_id_str)
                    
                    # Look up the full Tuition object in our pre-fetched dictionary
                    tuition_obj = all_tuitions_dict.get(tuition_id)

                    if tuition_obj:
                        scheduled_tuitions.append(
                            ScheduledTuition(
                                tuition=tuition_obj,
                                start_time=event['start_time'],
                                end_time=event['end_time']
                            )
                        )

            log.info(f"Successfully constructed {len(scheduled_tuitions)} scheduled tuition events.")
            return scheduled_tuitions
        
        except (TypeError, KeyError, ValueError) as e:
            log.error(f"Failed to parse timetable solution_data. Error: {e}", exc_info=True)
            return []

    def get_all_for_api(self, viewer_id: UUID) -> list[dict[str, Any]]:
        """
        RENAMED & REFACTORED: Public dispatcher that returns a lean list of scheduled
        tuitions formatted correctly for the viewer's role.
        """
        role = self.db.identify_user_role(viewer_id)
        rich_scheduled_tuitions = self.get_all(viewer_id) # Get the filtered rich objects

        if role == UserRole.teacher.name:
            return self._format_scheduled_for_teacher_api(rich_scheduled_tuitions)
        elif role in (UserRole.parent.name, UserRole.student.name):
            return self._format_scheduled_for_guardian_api(rich_scheduled_tuitions, viewer_id)
        else:
            raise UnauthorizedRoleError(f"User with role '{role}' is not authorized to view the timetable.")

    def _format_scheduled_for_teacher_api(self, scheduled_tuitions: list[ScheduledTuition]) -> list[dict[str, Any]]:
        """Formats scheduled tuitions for a teacher's view."""
        api_models = [ApiScheduledTuitionForTeacher(source=st) for st in scheduled_tuitions]
        return [model.model_dump(exclude={'source'}) for model in api_models]

    def _format_scheduled_for_guardian_api(self, scheduled_tuitions: list[ScheduledTuition], viewer_id: UUID) -> list[dict[str, Any]]:
        """Formats scheduled tuitions for a parent's or student's view."""
        api_models = [ApiScheduledTuitionForGuardian(source=st, viewer_id=viewer_id) for st in scheduled_tuitions]
        return [model.model_dump(exclude={'source', 'viewer_id'}) for model in api_models]
