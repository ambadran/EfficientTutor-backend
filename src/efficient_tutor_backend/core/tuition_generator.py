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
                            "cost_per_hour": student_row['cost_per_hour'],
                            "min_duration_minutes": student_row['min_duration_mins'],
                            "max_duration_minutes": student_row['max_duration_mins'],
                        }
                        generated_tuitions.append(tuition)
                        # Add the key to our set so we don't process it again.
                        processed_tuitions.add(tuition_key)

                except KeyError as e:
                    print(f"WARNING: Skipping broken subject record for student {primary_student_id}. Reason: {e}")
                    continue
        
        self.db.replace_all_tuitions(generated_tuitions)
        print(f"Successfully generated and saved {len(generated_tuitions)} unique tuitions to the database.")

