'''

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
            # It's important to still clear the table in case the last student was deleted
            self.db.replace_all_tuitions([])
            return

        generated_tuitions = []

        for student_row in all_students_raw:
            student_json = student_row['student_data']
            primary_student_id = student_json['id']

            for subject_info in student_json.get('subjects', []):
                try:
                    # Combine the primary student and any shared students
                    student_ids = sorted([primary_student_id] + subject_info.get('sharedWith', []))
                    
                    lessons_count = subject_info.get('lessonsPerWeek', 1)
                    subject_name = subject_info['name'] # The string from JSON

                    for i in range(lessons_count):
                        # The cost is determined by the primary student whose record we are processing.
                        # This can be overridden by the admin later.
                        tuition = {
                            "student_ids": student_ids,
                            "subject": subject_name, # This will be a string like "Math"
                            "lesson_index": i + 1,
                            "cost_per_hour": student_row['cost_per_hour'], # Added this field
                            "min_duration_minutes": student_row['min_duration_mins'],
                            "max_duration_minutes": student_row['max_duration_mins'],
                        }
                        generated_tuitions.append(tuition)
                except KeyError as e:
                    print(f"WARNING: Skipping broken subject record for student {primary_student_id}. Reason: {e}")
                    continue
        
        # Now, save this list to the database
        self.db.replace_all_tuitions(generated_tuitions)
        print(f"Successfully generated and saved {len(generated_tuitions)} tuitions to the database.")
