'''
This file is responsible to create tuition entries given raw data from parents
'''
from ..database.db_handler import DatabaseHandler

class TuitionGenerator:
    """
    Generates the definitive list of tuition sessions based on student data
    and saves them to the 'tuitions' table.
    """
    def __init__(self, db_handler: DatabaseHandler):
        self.db = db_handler

    def regenerate_all_tuitions(self):
        """
        The main function. Wipes and rebuilds the entire tuitions table.
        This should be called every time a student's subject or sharing
        information changes.
        """
        all_students_raw = self.db.get_all_student_parameters()
        if not all_students_raw:
            print("No student data found to generate tuitions.")
            self.db.replace_all_tuitions([])
            return

        generated_tuitions = []
        
        # THE FIX: Add a set to track tuitions we've already created.
        # This will prevent double-counting shared lessons.
        processed_tuitions = set()

        for student_row in all_students_raw:
            primary_student_id = str(student_row['id'])
            student_json = student_row['student_data'] or {}

            for subject_info in student_json.get('subjects', []):
                try:
                    student_ids_list = sorted([primary_student_id] + subject_info.get('sharedWith', []))
                    
                    lessons_count = subject_info.get('lessonsPerWeek', 1)
                    subject_name = subject_info['name']

                    for i in range(lessons_count):
                        # Create a unique, order-independent key for this tuition session.
                        # A frozenset is perfect because it's hashable and ignores order.
                        tuition_key = (frozenset(student_ids_list), subject_name, i + 1)

                        # If we've already processed this exact tuition, skip it.
                        if tuition_key in processed_tuitions:
                            continue


                        tuition = {
                            "student_ids": student_ids_list,
                            "subject": subject_name,
                            "lesson_index": i + 1,
                            "cost": student_row['cost'],
                            "min_duration_minutes": student_row['min_duration_mins'],
                            "max_duration_minutes": student_row['max_duration_mins'],
                            "meeting_link": None #TODO: get latest_value if data is the same, i've decided to run this individually when student is trying to access
                        }
                        generated_tuitions.append(tuition)
                        # Add the key to our set so we don't process it again.
                        processed_tuitions.add(tuition_key)

                except KeyError as e:
                    print(f"WARNING: Skipping broken subject record for student {primary_student_id}. Reason: {e}")
                    continue
        
        self.db.replace_all_tuitions(generated_tuitions)
        print(f"Successfully generated and saved {len(generated_tuitions)} unique tuitions to the database.")

    # def get_meeting_link(self, student_ids_list, subject_name, lesson_index) -> str:
    #     '''
    #     return meeting link given tuition
    #     '''
    #     # Step 1: check if it's already implemented

    #     latest_timetable = self.db.get_latest_timetable_run_data()
       
    #     scheduled_times = {}
    #     for session in latest_timetable:
    #         if session.get('category') == 'Tuition' and 'name' in session:
    #             scheduled_times[session['name']] = {
    #                 'start_time': session.get('start_time'),
    #                 'end_time': session.get('end_time')
    #             }

    #     name_list = []
    #     for student_id in student_ids_list:
    #         name_list.append(self.db.get_student_name_from_id(student_id)[0])

    #     # Step : filter the scheduled_times_map to only
    #     scheduled_time_filtered = {}
    #     for session_name in scheduled_times.keys():
    #         for student_name in name_list:
    #             if student_name in session_name and subject_name in session_name:
    #                 scheduled_time_filtered[session_name] = scheduled_times[session_name]

    #     print(scheduled_time_filtered)

    #     return ''

