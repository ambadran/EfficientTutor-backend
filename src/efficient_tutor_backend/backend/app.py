'''
Main backend API response
'''
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import time

# Import the DatabaseHandler from its module
from ..core.tuition_generator import TuitionGenerator
from ..core.timetable_service import TimetableService
from ..core.finance import LogbookService, FinancialLedgerService
from ..database.db_handler import DatabaseHandler
from ..common.logger import log

# Instead of a full Flask app, we create a Blueprint to keep routes organized.
main_routes = Blueprint('main_routes', __name__)

# Instantiate the database handler which will be used by our routes.
db = DatabaseHandler()

# Instantiate the new service
timetable_service = TimetableService(db)
logbook_service = LogbookService(db)
ledger_service = FinancialLedgerService(db)

@main_routes.route('/', methods=['GET'])
def health_check():
    """
    Health check endpoint to confirm the server is running and can connect to the DB.
    """
    if not db.check_connection():
        return jsonify({"error": "Database connection failed"}), 503
    return jsonify({"status": "ok", "message": "Backend is running and database is connected"}), 200


@main_routes.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    # THE FIX: Use a single, atomic function for signup and login.
    user_data, message = db.signup_and_login_user(email, password)

    if not user_data:
        # This will now correctly report if the user already exists.
        return jsonify({"error": message}), 409
    
    print(f"New user signed up and logged in: {email} (ID: {user_data['id']})")
    # Return the user session data directly, just like the login endpoint.
    return jsonify({"message": message, "user": user_data}), 201

@main_routes.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user_record = db.get_user_by_email(email)
    
    # This remains the same, for existing users.
    user_data, message = db.login_user(user_record, password)

    if not user_data:
        return jsonify({"error": message}), 401
    
    print(f"User logged in: {email}")
    return jsonify({"message": message, "user": user_data}), 200

@main_routes.route('/students', methods=['GET', 'POST', 'DELETE'])
def handle_students():
    """
    Handles all CRUD operations for students, scoped to the logged-in user.
    """
    if request.method == 'GET':
        user_id = request.args.get('userId')
    else: # POST or DELETE
        user_id = request.get_json().get('userId')

    if not user_id:
        return jsonify({"error": "Invalid or missing user ID"}), 401

    if request.method == 'GET':
        students = db.get_students(user_id)
        return jsonify(students), 200

    if request.method == 'POST':
        time.sleep(1.5) # Simulate processing delay for loading spinner
        student_data = request.get_json().get('student')
        student_id = db.save_student(user_id, student_data)

        # --- TRIGGER THE REGENERATION ---
        # After saving the student, regenerate the entire tuition list
        print("Student data saved. Triggering tuition list regeneration...")
        generator = TuitionGenerator(db)
        generator.regenerate_all_tuitions()
        # --- END OF TRIGGER ---

        print(f"Saved student '{student_data['firstName']}' for user {user_id}") # No longer nested in 'basicInfo'
        return jsonify({"message": "Student saved", "studentId": student_id}), 200

    if request.method == 'DELETE':
        student_id = request.get_json().get('studentId')
        if db.delete_student(user_id, student_id):
            print(f"Deleted student {student_id} for user {user_id}")
            return jsonify({"message": "Student deleted"}), 200
        return jsonify({"error": "Student not found"}), 404


@main_routes.route('/timetable', methods=['GET'])
def get_timetable():
    """
    Returns the real, scheduled timetable for a specific student by fetching
    and parsing the latest CSP run.
    """
    student_id = request.args.get('student_id')
    if not student_id:
        return jsonify({"error": "student_id parameter is required"}), 400

    # The db handler now performs all the complex fetching and parsing.
    student_timetable = db.get_student_timetable(student_id)
    
    # The final JSON structure matches exactly what the frontend expects.
    return jsonify({ "tuitions": student_timetable }), 200

@main_routes.route('/logs', methods=['GET'])
def get_logs():
    """
    Returns a full financial summary and detailed logs for a given parent user.
    """
    # NOTE: The frontend sends the parent's user ID as 'userId'
    parent_user_id = request.args.get('userId')
    if not parent_user_id:
        return jsonify({"error": "User ID is required"}), 400

    # The db handler now performs all complex calculations.
    log_data = db.get_user_logs(parent_user_id)
    
    return jsonify(log_data), 200

@main_routes.route('/student-credentials', methods=['GET'])
def get_student_credentials():
    """
    Endpoint for a parent to retrieve the generated credentials for one of their students.
    """
    parent_id = request.args.get('userId')
    student_id = request.args.get('studentId')

    if not parent_id or not student_id:
        return jsonify({"error": "Parent and student IDs are required"}), 400

    credentials = db.get_student_credentials(parent_id, student_id)
    
    if not credentials:
        # This can happen if the student doesn't exist or the parent is not authorized
        return jsonify({"error": "Could not retrieve credentials. Please check the IDs."}), 404
        
    return jsonify(credentials), 200

# --- Student-Facing Endpoints ---

@main_routes.route('/student-profile', methods=['GET'])
def get_student_profile():
    """Endpoint for a logged-in student to retrieve their own full profile."""
    student_id = request.args.get('studentId')
    if not student_id:
        return jsonify({"error": "Student ID is required"}), 400
    
    # SECURITY NOTE: In production, you would validate that the logged-in user's ID
    # from their session token matches the requested student_id.

    student_profile = db.get_student_profile(student_id)
    if not student_profile:
        return jsonify({"error": "Student profile not found"}), 404

    return jsonify(student_profile), 200

# --- NEW ENDPOINT FOR STUDENT NOTES ---
@main_routes.route('/notes', methods=['GET'])
def get_notes():
    """
    Endpoint for a logged-in student to retrieve their list of notes.
    The student's ID would be derived from their session token in a real scenario.
    For now, we'll pass it as a query parameter for testing.
    """
    student_id = request.args.get('studentId')

    if not student_id:
        return jsonify({"error": "Student ID is required"}), 400

    # The user's role would be checked here to ensure they are a student
    # before proceeding. (e.g., if user.role != 'student': return 403 Forbidden)

    notes = db.get_student_notes(student_id)
    
    # The get_student_notes function already handles the case where a student
    # might not be found or has no notes by returning an empty list.
    return jsonify(notes), 200



# --- NEW ENDPOINT FOR STUDENT MEETING LINKS ---
@main_routes.route('/meeting-links', methods=['GET'])
def get_meeting_links():
    """
    Endpoint for a logged-in student to retrieve their list of tuitions
    with their scheduled times and meeting links.
    """
    student_id = request.args.get('studentId')

    if not student_id:
        return jsonify({"error": "Student ID is required"}), 400

    # Again, you would add a security check here to ensure the user
    # making the request is authorized to see this student's links.

    links = db.get_student_meeting_links(student_id)
    
    # The db handler returns an empty list if no links are found, so no
    # special error handling is needed here.
    return jsonify(links), 200


# v0.3 stuff
# methods to get data to choose from
@main_routes.route('/schedulable-tuitions', methods=['GET'])
def get_schedulable_tuitions():
    """
    Returns a list of all defined tuitions, enriched with their scheduled
    times to be displayed on the teacher's UI.
    """
    try:
        enriched_tuitions = timetable_service.get_schedulable_tuitions()
        return jsonify(enriched_tuitions), 200
    except Exception as e:
        # A generic error handler is good practice
        log.error(f"ERROR in /schedulable-tuitions: {e}")
        return jsonify({"error": "An internal error occurred"}), 500


@main_routes.route('/manual-entry-data', methods=['GET'])
def get_manual_entry_data():
    """
    Returns the data needed for the teacher's UI to manually log a tuition:
    a list of all students and a list of all possible subjects.
    """
    try:
        students = db.get_all_students_basic_info()
        subjects = db.get_subject_enum_values()
        
        response_data = {
            "students": students,
            "subjects": subjects
        }
        return jsonify(response_data), 200
    except Exception as e:
        log.error(f"ERROR in /manual-entry-data: {e}")
        return jsonify({"error": "An internal error occurred"}), 500

# methods to actually log stuff
@main_routes.route('/tuition-logs', methods=['POST'])
def create_tuition_log():
    """
    Receives data from the teacher's UI to create a new tuition log.
    Delegates all logic to the LogbookService.
    """
    data = request.get_json()
    try:
        print("laksjdflkjlk")
        new_log_id = logbook_service.create_tuition_log(data)
        return jsonify({"message": "Tuition log created successfully", "log_id": new_log_id}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400 # Bad request
    except Exception as e:
        log.error(f"ERROR in /tuition-logs: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500

@main_routes.route('/payment-logs', methods=['POST'])
def create_payment_log():
    """
    Creates a new payment log entry.
    """
    data = request.get_json()
    try:
        if not data.get('parent_user_id') or data.get('amount_paid') is None:
            raise ValueError("parent_user_id and amount_paid are required.")
        
        new_payment_id = db.insert_payment_log(data)
        return jsonify({"message": "Payment log created", "payment_id": new_payment_id}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        log.error(f"ERROR in /payment-logs: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500

@main_routes.route('/tuition-logs/<log_id>/void', methods=['POST'])
def void_tuition_log(log_id):
    """
    Voids a specific tuition log. This is a safe alternative to deleting.
    """
    try:
        success = db.void_tuition_log(log_id)
        if not success:
            return jsonify({"error": "Log not found or already voided"}), 404
        return jsonify({"message": f"Log {log_id} has been voided"}), 200
    except Exception as e:
        log.error(f"ERROR in /tuition-logs/<log_id>/void: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500

@main_routes.route('/tuition-logs/<log_id>/correction', methods=['POST'])
def correct_tuition_log(log_id):
    """
    Corrects a log by voiding the original and creating a new one with
    the data provided in the request body.
    """
    correction_data = request.get_json()
    try:
        new_log_id = logbook_service.perform_log_correction(log_id, correction_data)
        return jsonify({
            "message": "Log corrected successfully",
            "original_log_id": log_id,
            "new_log_id": new_log_id
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400 # Catches invalid IDs or bad data
    except Exception as e:
        log.error(f"ERROR in /tuition-logs/<log_id>/correction: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500


@main_routes.route('/financial-report/<parent_id>', methods=['GET'])
def get_financial_report(parent_id):
    """
    Generates and returns a complete financial report for the specified parent.
    """
    try:
        # Here you would typically validate that the user making the request
        # is authorized to view this parent's report.
        
        report = ledger_service.generate_report(parent_id)
        return jsonify(report), 200
    except Exception as e:
        log.error(f"ERROR in /financial-report/{parent_id}: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500


@main_routes.route('/tuition-logs', methods=['GET'])
def get_all_tuition_logs():
    """
    Returns a list of all tuition logs for administrative review.
    """
    try:
        all_logs = db.get_all_tuition_logs()
        return jsonify(all_logs), 200
    except Exception as e:
        log.error(f"ERROR in GET /tuition-logs: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500

