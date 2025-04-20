from logging import config
import re
import traceback
import MySQLdb
from flask import Flask, Blueprint, jsonify, render_template, request, redirect, url_for, flash, session, current_app
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from . import mysql
from datetime import datetime
from werkzeug.utils import secure_filename
import os 
import uuid




app = Flask(__name__)

# Configure MySQL
mysql = MySQL(app)

# Blueprints
auth = Blueprint('auth', __name__)

# Utility function to handle DB operations
def execute_query(query, params=None, fetchone=False, fetchall=False, commit=False):
    try:
        with mysql.connection.cursor() as cursor:
            cursor.execute(query, params or ())
            if commit:
                mysql.connection.commit()
                return True
            if fetchone:
                return cursor.fetchone()
            if fetchall:
                return cursor.fetchall()
    except Exception as e:
        current_app.logger.error(f"Database error: {e}")
        flash(f"Database error: {e}", category='danger')
        return None

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        user = execute_query(
            "SELECT id, password, is_approved, is_admin FROM students WHERE email = %s",
            (email,),
            fetchone=True
        )
        if user:
            user_id, stored_password, is_approved, is_admin = user

            if check_password_hash(stored_password, password):
                session['user_id'] = int(user_id)
                session['is_admin'] = bool(is_admin)
                session['user_email'] = email  # 👈 ADD THIS LINE

                if is_admin:
                    flash('Admin login successful.', category='success')
                    return redirect(url_for('auth.admin_panel'))

                if is_approved:
                    flash('Login successful.', category='success')
                    return redirect(url_for('auth.pgpc'))
                else:
                    flash('Account not yet approved. Redirecting to enrollment page.', category='info')
                    return redirect(url_for('auth.enroll_now'))  # was 'auth.enroll_now' earlier

            else:
                flash('Incorrect password.', category='danger')
        else:
            flash('Email not found.', category='danger')

    return render_template("login.html")

# enrllment

UPLOAD_FOLDER = 'static/uploads'

@auth.route('/enrollment', methods=['GET', 'POST'])
def enrollment():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to edit your enrollment.", "error")
        return redirect(url_for('auth.login'))

    conn = mysql.connection
    cursor = conn.cursor(MySQLdb.cursors.DictCursor)

    # Get student record first (to check done_enrollment)
    cursor.execute("SELECT * FROM students WHERE id=%s", (user_id,))
    student = cursor.fetchone()

    if not student:
        flash("Student record not found.", "error")
        return redirect(url_for('auth.login'))

    # 🚫 Block access if enrollment is already done
    if student.get('done_enrollment'):
        flash("You have already completed your enrollment.", "info")
        return redirect(url_for('auth.awaiting_approval'))

    if request.method == 'POST':
        # Gather form data
        firstname = request.form['firstname']
        middlename = request.form['middlename']
        lastname = request.form['lastname']
        dob = request.form['dob']
        gender = request.form['gender']
        nationality = request.form['nationality']
        contact = request.form['contact']
        email = request.form['email']
        address = request.form['address']

        college = request.form['college']
        academic_year = request.form['academic_year']
        term = request.form['term']
        program = request.form['program']
        degree_program = request.form['degree_program']
        student_id = request.form.get('student_id', '')
        previous_school = request.form.get('previous_school', '')

    
        # File upload helper
        def save_file(fieldname):
            file = request.files.get(fieldname)
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                upload_path = os.path.join(UPLOAD_FOLDER)
                os.makedirs(upload_path, exist_ok=True)
                filepath = os.path.join(upload_path, filename)
                file.save(filepath)
                return filename
            return None

        form138 = save_file('form138')
        birth_cert = save_file('birth_cert')
        good_moral = save_file('good_moral')
        id_photos = save_file('id_photos')

        # Update student data
        update_query = """
            UPDATE students SET
                firstname=%s, middlename=%s, lastname=%s, dob=%s, gender=%s, nationality=%s, contact=%s,
                email=%s, address=%s, college=%s, academic_year=%s, term=%s, degree_program=%s,
                student_id=%s, previous_school=%s,
                form138=%s, birth_cert=%s, good_moral=%s, id_photos=%s
            WHERE id=%s
        """
        cursor.execute(update_query, (
            firstname, middlename, lastname, dob, gender, nationality, contact,
            email, address, college, academic_year, term, degree_program,
            student_id, previous_school,
            form138, birth_cert, good_moral, id_photos,
            user_id
        ))

        # ✅ Mark enrollment as done
        cursor.execute("UPDATE students SET done_enrollment = TRUE WHERE id = %s", (user_id,))

        conn.commit()
        flash("Enrollment information updated successfully!", "success")
        return redirect(url_for('auth.awaiting_approval'))

    return render_template("enrollment.html", student=student)

def validate_form(email, firstname, lastname, password1, password2, course, dob, gender, nationality, contact, address, college, academic_year, term):
    if not email or len(email) < 5:
        flash('Email must be greater than 4 characters.', category='danger')
        return False
    if not firstname or len(firstname) < 3:
        flash('First name must be at least 3 characters.', category='danger')
        return False
    if not lastname or len(lastname) < 3:
        flash('Last name must be at least 3 characters.', category='danger')
        return False
    if not dob:
        flash('Date of Birth is required.', category='danger')
        return False
    if gender not in ['Male', 'Female', 'Other']:
        flash('Please select a valid gender.', category='danger')
        return False
    if not nationality:
        flash('Nationality is required.', category='danger')
        return False
    if not contact or len(contact) < 7:
        flash('Valid contact number is required.', category='danger')
        return False
    if not address:
        flash('Address is required.', category='danger')
        return False
    if not college:
        flash('College/Faculty selection is required.', category='danger')
        return False
    if not course:
        flash('Degree Program is required.', category='danger')
        return False
    if not academic_year:
        flash('Academic Year is required.', category='danger')
        return False
    if not term:
        flash('Term/Semester is required.', category='danger')
        return False
    if not password1 or not password2:
        flash('Password is required.', category='danger')
        return False
    if password1 != password2:
        flash('Passwords do not match.', category='danger')
        return False
    if len(password1) < 7:
        flash('Password must be at least 7 characters long.', category='danger')
        return False
    return True

@auth.route("/approval")
def awaiting_approval():
    if not session.get('user_id'):
        flash('You must log in first.', category='danger')
        return redirect(url_for('auth.login'))

    user_id = session['user_id']

    cur = mysql.connection.cursor()
    cur.execute("SELECT temp_id, is_approved FROM students WHERE id = %s", (user_id,))
    result = cur.fetchone()
    cur.close()

    if result:
        temp_id, is_approved = result[0], result[1]

        if is_approved == 1:
            flash('Your enrollment has been approved.', category='success')
            return redirect(url_for('auth.pgpc'))  

        return render_template('approval.html', temp_id=temp_id)

    else:
        flash('User not found.', category='danger')
        return redirect(url_for('auth.login'))

@auth.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('is_admin', None)
    session.pop('photo_url', None)
    flash('Logged out successfully.', category='success')
    return redirect(url_for('auth.login'))

@auth.route('/')
def home():
    return render_template('home.html')

@auth.route('/about')
def about():
    return render_template('about.html')

@auth.route('/academics')
def academics():
    return render_template('academics.html')

@auth.route('/apply_now')
def apply_now():
    return render_template('apply_now.html')

@auth.route('/create_account', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password1 = request.form.get('password1', '').strip()

        print(f"Email: '{email}', Password: '{password1}'")

        if not email or not password1:
            flash('Email and password are required.', category='danger')
        elif len(password1) < 6:
            flash('Password must be at least 6 characters.', category='danger')
        else:
            existing_student = execute_query(
                "SELECT email FROM students WHERE email = %s", 
                (email,), 
                fetchone=True
            )
            if existing_student:
                flash('Email already registered.', category='danger')
            else:
                hashed_password = generate_password_hash(password1)
                temp_id = f"TEMP-{uuid.uuid4().hex[:8].upper()}"

                success = execute_query("""
                    INSERT INTO students (email, Password, temp_id)
                    VALUES (%s, %s, %s)
                """, (email, hashed_password, temp_id), commit=True)

                if success:
                    flash(f'Account created successfully. Your temporary ID is {temp_id}', category='success')
                    return redirect(url_for('auth.enroll_now'))
                else:
                    flash('Error creating account. Please try again.', category='danger')

    return render_template('create_account.html')

@auth.route('/requirments')
def requirments():
    return render_template('requirments.html')

@auth.route('/enroll_now')
def enroll_now():
    if not session.get('user_id'):
        flash('You must log in first.', category='danger')
        return redirect(url_for('auth.login'))

    user_id = session['user_id']

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, email, temp_id FROM students WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()

    if user:
        user_data = {
            'id': user[0],
            'email': user[1],
            'temp_id': user[2]
        }
        return render_template('enroll_now.html', user=user_data, now=datetime.now())
    else:
        flash('User not found.', category='danger')
        return redirect(url_for('auth.login'))

# Routes for the Admin Panel
@auth.route("/admin")
def admin_panel():
    if not session.get('is_admin', False):
        flash('You are not authorized to view the admin panel.', category='danger')
        return redirect(url_for('auth.pgpc'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get logged-in admin info
    cursor.execute("SELECT firstname, lastname FROM students WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()

    # Get students with pending approval
    cursor.execute("SELECT id, firstname FROM students WHERE done_enrollment = 1 AND is_approved = 0")
    pending_students = cursor.fetchall()

    # Get count of approved students
    cursor.execute("SELECT COUNT(*) AS total FROM students WHERE is_approved = 1")
    approved_count = cursor.fetchone()['total']

    # Get total new enrollees (done_enrollment = 1)
    cursor.execute("SELECT COUNT(*) AS total FROM students WHERE done_enrollment = 1")
    new_enrollees = cursor.fetchone()['total']

    # Get count of pending application
    cursor.execute("SELECT COUNT(*) AS total FROM students WHERE is_approved = 0")
    pending_count = cursor.fetchone()['total']

    cursor.close()

    return render_template(
        "admin_panel.html",
        notifications=pending_students,
        user=user,
        approved_count=approved_count,
        new_enrollees=new_enrollees,
        pending_count=pending_count
    )


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
UPLOAD_FOLDER = 'static/uploads'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@auth.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if not session.get('is_admin'):
        flash('Unauthorized access', 'danger')
        return redirect(url_for('auth.pgpc'))

    conn = mysql.connection
    cursor = conn.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT firstname, lastname FROM students WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()

    if not user:
        flash("Admin not found", "error")
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        form = request.form

        # Check for missing fields
        required_fields = [
            'firstname', 'lastname', 'dob', 'gender', 'nationality',
            'contact', 'email', 'address', 'password', 'confirm_password',
            'college', 'academic_year', 'term',  'degree_program'
        ]
        missing = [f for f in required_fields if not form.get(f)]
        if missing:
            flash("Missing required fields", "error")
            return redirect(url_for('auth.add_student'))

        # Validate password confirmation
        if form['password'] != form['confirm_password']:
            flash("Passwords do not match", "error")
            return redirect(url_for('auth.add_student'))

        if len(form['password']) < 8:
            flash("Password must be at least 8 characters", "error")
            return redirect(url_for('auth.add_student'))

        if not re.match(r"[^@]+@[^@]+\.[^@]+", form['email']):
            flash("Invalid email format", "error")
            return redirect(url_for('auth.add_student'))

        # File upload helper function
        def save_file(fieldname):
            file = request.files.get(fieldname)
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                upload_path = os.path.join(UPLOAD_FOLDER)
                os.makedirs(upload_path, exist_ok=True)
                file.save(os.path.join(upload_path, unique_filename))
                return unique_filename
            return None

        # Handle file uploads
        profile_pic = save_file('profile_pic')
        form138 = save_file('form138')
        birth_cert = save_file('birth_cert')
        good_moral = save_file('good_moral')
        id_photos = save_file('id_photos')

        try:
            cursor.execute("""
                INSERT INTO students (
                    firstname, middlename, lastname, dob, gender, nationality,
                    contact, email, address, password, college, academic_year,
                    term, degree_program, student_id, previous_school,
                    profile_pic, form138, birth_cert, good_moral, id_photos,
                    done_enrollment, is_approved
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                form['firstname'].strip(),
                form.get('middlename', '').strip(),
                form['lastname'].strip(),
                form['dob'],
                form['gender'],
                form['nationality'],
                form['contact'].strip(),
                form['email'].strip().lower(),
                form['address'].strip(),
                generate_password_hash(form['password']),
                form['college'],
                form['academic_year'],
                form['term'],
                form['degree_program'],
                form.get('student_id', '').strip(),
                form.get('previous_school', '').strip(),
                profile_pic, form138, birth_cert, good_moral, id_photos,
                1,  # done_enrollment = 1
                1   # is_approved = 1
            ))

            conn.commit()
            flash("Student added and auto-approved successfully!", "success")
            return redirect(url_for('auth.add_student'))

        except MySQLdb.Error as e:
            conn.rollback()
            if e.args[0] == 1062:  # Duplicate entry error code for email
                flash("Email already exists", "error")
            else:
                flash(f"Database error: {e}", "error")
            return redirect(url_for('auth.add_student'))

    # For GET request, render the form with colleges and programs
    colleges = [
        {'value': 'CCBA', 'name': 'College of Computing and Business Administration'},
        {'value': 'COC', 'name': 'College of Criminology'}
    ]
    programs = [
        {'value': 'BSCS', 'name': 'Bachelor of Science in Computer Science'},
        {'value': 'BSCRIM', 'name': 'Bachelor of Science in Criminology'},
        {'value': 'BSMA', 'name': 'Bachelor of Science in Management Accounting'},
        {'value': 'BPA', 'name': 'Bachelor of Public Administration'}
    ]
    academic_years = ['2023-2024', '2024-2025', '2025-2026']
    terms = [
        {'value': '1', 'name': 'First Semester'},
        {'value': '2', 'name': 'Second Semester'},
        {'value': 'Summer', 'name': 'Summer'}
    ]

    return render_template("add_student.html",
                           user=user,
                           colleges=colleges,
                           programs=programs,
                           academic_years=academic_years,
                           terms=terms)


@auth.route('/unapproved')
def unapproved():
    if not session.get('is_admin'):
        flash('You are not authorized to view this page', 'danger')
        return redirect(url_for('auth.pgpc'))

    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Get logged-in admin info
        cursor.execute("SELECT firstname, lastname FROM students WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        
        # Search functionality
        search_query = request.args.get('search', '')
        selected_id = request.args.get('selected', type=int)
        
        # Base query for pending students
        query = """
            SELECT id, firstname, lastname, student_id, degree_program, created_at 
            FROM students 
            WHERE done_enrollment = 1 AND is_approved = 0
        """
        
        params = []
        
        if search_query:
            query += " AND (firstname LIKE %s OR lastname LIKE %s OR student_id LIKE %s)"
            params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])
        
        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        students = cursor.fetchall()
        
        selected_student = None
        all_valid = False
        
        if selected_id:
            # Get full details for selected student
            cursor.execute("""
                SELECT * FROM students 
                WHERE id = %s AND done_enrollment = 1 AND is_approved = 0
            """, (selected_id,))
            selected_student = cursor.fetchone()
            
            if selected_student:
                # Check if all validations are complete (simplified version)
                all_valid = all([
                    selected_student.get('firstname'),
                    selected_student.get('lastname'),
                    selected_student.get('dob'),
                    selected_student.get('degree_program'),
                    selected_student.get('form138'),
                    selected_student.get('birth_cert'),
                    selected_student.get('good_moral'),
                    selected_student.get('id_photos')
                ])
        
        return render_template(
            "unapproved_student.html",
            students=students,
            user=user,
            selected_student=selected_student,
            all_valid=all_valid,
            valid_personal=bool(selected_student and selected_student.get('firstname') and selected_student.get('lastname') and selected_student.get('dob')),
            valid_academic=bool(selected_student and selected_student.get('degree_program')),
            valid_documents=bool(selected_student and selected_student.get('form138') and selected_student.get('birth_cert') and selected_student.get('good_moral')),
            valid_photos=bool(selected_student and selected_student.get('id_photos'))
        )
        
    except Exception as e:
        flash(f'Database error: {str(e)}', 'error')
        return redirect(url_for('auth.pgpc'))
    finally:
        cursor.close()

@auth.route('/approve_student/<int:student_id>', methods=['POST'])
def approve_student(student_id):
    if not session.get('is_admin'):
        flash('Unauthorized', 'danger')
        return redirect(url_for('auth.pgpc'))

    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Verify all validations are checked
        if not all([
            request.form.get('valid_personal') == 'on',
            request.form.get('valid_academic') == 'on',
            request.form.get('valid_documents') == 'on',
            request.form.get('valid_photos') == 'on'
        ]):
            flash('Please complete all validations before approval', 'warning')
            return redirect(url_for('auth.unapproved', selected=student_id))
        
        # Check if student is already approved
        cursor.execute("SELECT is_approved FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()

        if student and student['is_approved'] == 1:
            flash('This student has already been approved.', 'info')
            return redirect(url_for('auth.unapproved'))
        
        # Ensure the user_id and student_id are integers
        approved_by = int(session['user_id'])
        student_id = int(student_id)
        
        # Update approval status
        cursor.execute("""
            UPDATE students 
            SET is_approved = 1, approved_by = %s, approval_date = NOW() 
            WHERE id = %s
        """, (approved_by, student_id))
        mysql.connection.commit()
        
        flash('Student approved successfully! Approval status updated.', 'success')
        return redirect(url_for('auth.unapproved'))
        
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error approving student: {str(e)}', 'error')
        return redirect(url_for('auth.unapproved', selected=student_id))
    finally:
        cursor.close()

@auth.route('/reject_student/<int:student_id>')
def reject_student(student_id):
    if not session.get('is_admin'):
        flash('Unauthorized', 'danger')
        return redirect(url_for('auth.pgpc'))

    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Get student name for flash message
        cursor.execute("SELECT firstname, lastname FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()
        
        if student:
            # Delete student record
            cursor.execute("DELETE FROM students WHERE id = %s", (student_id,))
            mysql.connection.commit()
            
            flash(f"Rejected application for {student['firstname']} {student['lastname']}", 'warning')
        else:
            flash('Student not found', 'error')
            
        return redirect(url_for('auth.unapproved'))
        
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error rejecting student: {str(e)}', 'error')
        return redirect(url_for('auth.unapproved'))
    finally:
        cursor.close()



from datetime import datetime
from flask import render_template, flash, redirect, url_for, session
import MySQLdb

@auth.route("/pgpc")
def pgpc():
    if not session.get('user_id'):
        flash('You must log in first.', category='danger')
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    cursor.execute("SELECT id, firstname, lastname, student_id, degree_program FROM students WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    
    if user:
        now = datetime.now()
        hour = now.hour
        day_name = now.strftime("%A")
        current_time = now.strftime("%B %d, %Y | %I:%M %p")
        is_weekend = now.weekday() >= 5

        if 5 <= hour < 12:
            greeting = "Good Morning"
        elif 12 <= hour < 18:
            greeting = "Good Afternoon"
        elif 18 <= hour < 21:
            greeting = "Good Evening"
        else:
            greeting = "Good Night"

        # Fetch announcements
        cursor.execute("SELECT * FROM announcements ORDER BY time_created DESC")
        announcements = cursor.fetchall()

        # Convert announcement timestamp to datetime if it's a string and format it
        for announcement in announcements:
            if isinstance(announcement['time_created'], str):  # Check if it's a string
                announcement['time_created'] = datetime.strptime(announcement['time_created'], '%Y-%m-%d %H:%M:%S')
            announcement['time_created'] = announcement['time_created'].strftime('%b %d, %Y | %I:%M %p')

        # Fetch events
        cursor.execute("SELECT id, title, event_date, start_time, end_time, location, created_at FROM events ORDER BY event_date DESC")
        events = cursor.fetchall()

        # Convert event_date to datetime if it's a string and format it
        for event in events:
            if isinstance(event['event_date'], str):  # Check if it's a string
                event['event_date'] = datetime.strptime(event['event_date'], '%Y-%m-%d')
            event['event_date'] = event['event_date'].strftime('%b %d, %Y')

            # Format start and end times
            if isinstance(event['start_time'], str):
                event['start_time'] = datetime.strptime(event['start_time'], '%H:%M:%S').strftime('%I:%M %p')
            if isinstance(event['end_time'], str):
                event['end_time'] = datetime.strptime(event['end_time'], '%H:%M:%S').strftime('%I:%M %p')

            # Format created_at if it's a string
            if isinstance(event['created_at'], str):
                event['created_at'] = datetime.strptime(event['created_at'], '%Y-%m-%d %H:%M:%S').strftime('%b %d, %Y | %I:%M %p')

        cursor.close()

        return render_template(
            "pgpc.html",
            user=user,
            current_time=current_time,
            day_name=day_name,
            is_weekend=is_weekend,
            greeting=greeting,
            announcements=announcements,
            events=events
        )
    else:
        flash('User not found.', category='danger')
        return redirect(url_for('auth.login'))



@auth.route('/announcement', methods=['GET', 'POST'])
def announcement():
    if not session.get('is_admin', False):
        flash('You are not authorized to view the admin panel.', category='danger')
        return redirect(url_for('auth.pgpc'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT firstname, lastname FROM students WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()

    cursor.execute("SELECT id, firstname FROM students WHERE done_enrollment = 1 AND is_approved = 0")
    pending_students = cursor.fetchall()

    if request.method == 'POST':
        # Announcement handling
        if 'announcement_title' in request.form and 'announcement_message' in request.form:
            title = request.form.get('announcement_title', '')
            message = request.form.get('announcement_message', '')
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Use the variable 'timestamp' correctly

            cursor.execute("INSERT INTO announcements (title, message, time_created) VALUES (%s, %s, %s)", (title, message, timestamp))
            mysql.connection.commit()
            flash('Announcement posted successfully!', category='success')

        # Event handling
        if 'event_title' in request.form and 'event_description' in request.form:
            event_title = request.form.get('event_title', '')
            event_description = request.form.get('event_description', '')
            event_date = request.form.get('event_date', '')
            start_time = request.form.get('start_time', '')
            end_time = request.form.get('end_time', '')
            location = request.form.get('location', '')

            if event_title and event_description and event_date and start_time and end_time and location:
                cursor.execute(
                    "INSERT INTO events (title, description, event_date, start_time, end_time, location) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (event_title, event_description, event_date, start_time, end_time, location)
                )
                mysql.connection.commit()
                flash('Event posted successfully!', category='success')
            else:
                flash('Please fill in all event fields.', category='danger')

    cursor.execute("SELECT * FROM announcements ORDER BY time_created DESC")
    announcements = cursor.fetchall()

    if 'delete_announcement' in request.args:
        announcement_id = request.args.get('delete_announcement')
        cursor.execute("DELETE FROM announcements WHERE id = %s", (announcement_id,))
        mysql.connection.commit()
        flash('Announcement deleted successfully!', category='success')

    # Fetching events from the database
    cursor.execute("SELECT * FROM events ORDER BY event_date DESC")
    events = cursor.fetchall()

    if 'delete_event' in request.args:
        event_id = request.args.get('delete_event')
        cursor.execute("DELETE FROM events WHERE id = %s", (event_id,))
        mysql.connection.commit()
        flash('Event deleted successfully!', category='success')

    cursor.close()

    return render_template(
        "announcement.html",
        notifications=pending_students,
        user=user,
        announcements=announcements,
        events=events
    )



if __name__ == '__main__':
    app.run(debug=True)
