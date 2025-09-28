"""
Provide all needed timetable_runs db  table interactions
"""

class TimetableService:
    """
    Handles business logic related to fetching and processing timetable data.
    """
    def __init__(self, db_handler):
        self.db = db_handler

    def get_schedulable_tuitions(self):
        """
        Fetches all active tuitions and enriches them with their scheduled times
        from the latest successful timetable run.
        """
        # 1. Get raw data from the database
        all_tuitions = self.db.get_active_tuitions()
        latest_schedule = self.db.get_latest_successful_schedule()
        
        if not latest_schedule:
            # If there's no schedule, return tuitions without time info
            return all_tuitions

        # 2. Create a lookup map for quick access to scheduled times
        scheduled_times_map = {}
        for session in latest_schedule.get('solution_data', []):
            if session.get('category') == 'Tuition':
                # Key is the unique tuition name, e.g., "Tuition_Ali_Math_1"
                tuition_key = session.get('name') 
                scheduled_times_map[tuition_key] = {
                    "start_time": session.get('start_time'),
                    "end_time": session.get('end_time')
                }
        
        # 3. Enrich tuition data with scheduled times
        enriched_tuitions = []
        student_id_name_map = self.db.get_student_id_to_name_map() # We already fetch this map

        for tuition in all_tuitions:
            # === MODIFIED LOGIC START ===
            raw_ids = tuition.get('student_ids', [])
            
            # This check handles both single IDs and multiple IDs in the string format '{id1,id2}'
            if isinstance(raw_ids, str):
                student_ids = raw_ids.strip('{}').split(',')
            else:
                student_ids = raw_ids or []

            names = [student_id_name_map.get(str(sid), 'Unknown Student') for sid in student_ids]
            tuition['student_names'] = names
            # === MODIFIED LOGIC END ===

            # Reconstruct the tuition key to find it in the map
            participant_names = sorted(names) 
            key = f"Tuition_{'_'.join(participant_names)}_{tuition['subject']}_{tuition['lesson_index']}"
            
            schedule_info = scheduled_times_map.get(key, {})
            tuition['scheduled_start_time'] = schedule_info.get('start_time')
            tuition['scheduled_end_time'] = schedule_info.get('end_time')
            enriched_tuitions.append(tuition)
            
            
        return enriched_tuitions
