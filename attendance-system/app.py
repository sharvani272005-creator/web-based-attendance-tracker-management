from flask import Flask, render_template, request, redirect, Response, session
import sqlite3
from io import StringIO
import csv
import os
from werkzeug.utils import secure_filename
from datetime import date

app = Flask(__name__)
app.secret_key = "my_super_secret_key_123"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "attendance.db")
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT,
        year TEXT,
        photo TEXT
                
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student TEXT,
        teacher TEXT,
        date TEXT,
        period INTEGER,
        status TEXT,
        UNIQUE(student, date , period )
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS teacher_assignment (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       teacher TEXT,
       year TEXT,
       period INTEGER
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- FIRST TIME SETUP ----------------
@app.route("/setup", methods=["GET", "POST"])
def setup():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE role='admin'")
    admin = cur.fetchone()

    if admin:
        conn.close()
        return redirect("/")

    if request.method == "POST":
        full_name = request.form["full_name"]
        username = request.form["username"]
        password = request.form["password"]

        cur.execute("""
        INSERT INTO users (full_name, username, password, role, photo)
        VALUES (?, ?, ?, 'admin', NULL)
        """, (full_name, username, password))

        conn.commit()
        conn.close()
        return redirect("/")

    conn.close()
    return render_template("setup.html")
@app.route("/db-path")
def db_path():
    import os
    return os.path.abspath(DB_NAME)

# ---------------- VIEW ASSIGNMENTS ----------------
@app.route("/admin/assignments")
def view_assignments():

    if "role" not in session or session["role"] != "admin":
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM teacher_assignment")
    assignments = cur.fetchall()

    conn.close()

    return render_template("view_assignments.html", assignments=assignments)
# ---------------- DELETE ASSIGNMENT ----------------
@app.route("/admin/delete-assignment/<int:id>")
def delete_assignment(id):

    if "role" not in session or session["role"] != "admin":
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM teacher_assignment WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect("/admin/assignments")
# ---------------- EDIT ASSIGNMENT ----------------
@app.route("/admin/edit-assignment/<int:id>", methods=["GET", "POST"])
def edit_assignment(id):

    if "role" not in session or session["role"] != "admin":
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        teacher = request.form["teacher"]
        year = request.form["year"]
        period = request.form["period"]

        cur.execute("""
        UPDATE teacher_assignment
        SET teacher=?, year=?, period=?
        WHERE id=?
        """, (teacher, year, period, id))

        conn.commit()
        conn.close()
        return redirect("/admin/assignments")

    cur.execute("SELECT * FROM teacher_assignment WHERE id=?", (id,))
    assignment = cur.fetchone()

    cur.execute("SELECT username FROM users WHERE role='teacher'")
    teachers = cur.fetchall()

    conn.close()

    return render_template(
        "edit_assignment.html",
        assignment=assignment,
        teachers=teachers
    )
# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
def login():

    # Redirect to setup if no admin exists
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE role='admin'")
    admin_exists = cur.fetchone()
    conn.close()

    if not admin_exists:
        return redirect("/setup")

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE username=? AND password=? AND role=?",
            (username, password, role)
        )
        user = cur.fetchone()
        conn.close()

        if user:
            session["username"] = user["username"]
            session["role"] = user["role"]

            if role == "admin":
                return redirect("/admin")
            elif role == "teacher":
                return redirect("/teacher/dashboard")
            elif role == "student":
                return redirect(f"/student/dashboard/{username}")

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")

# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin")
def admin_dashboard():

    if "role" not in session or session["role"] != "admin":
        return redirect("/")

    search_query = request.args.get("search")

    conn = get_db()
    cur = conn.cursor()

    if search_query:
        cur.execute("SELECT * FROM users WHERE username LIKE ?", ('%' + search_query + '%',))
    else:
        cur.execute("SELECT * FROM users")

    users = cur.fetchall()

    # 👇 NEW: Split students by year
    year1_students = []
    year2_students = []
    year3_students = []

    for user in users:
        if user["role"] == "student":
            if user["year"] == "1":
                year1_students.append(user)
            elif user["year"] == "2":
                year2_students.append(user)
            elif user["year"] == "3":
                year3_students.append(user)

    conn.close()

    return render_template(
        "admin_dashboard.html",
        users=users,   # ← keep for teacher table
        year1_students=year1_students,
        year2_students=year2_students,
        year3_students=year3_students,
        search_query=search_query
    )
#----------------assign period----------------------------
@app.route("/assign-period", methods=["GET", "POST"])
def assign_period():

    if "role" not in session or session["role"] != "admin":
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT username FROM users WHERE role='teacher'")
    teachers = cur.fetchall()

    if request.method == "POST":
        teacher = request.form["teacher"]
        year = request.form["year"]
        period = request.form["period"]

        cur.execute("""
        INSERT INTO teacher_assignment (teacher, year, period)
        VALUES (?, ?, ?)
        """, (teacher, year, period))

        conn.commit()
        conn.close()
        return redirect("/admin")

    conn.close()
    return render_template("assign_period.html", teachers=teachers)
# ---------------- ADMIN EDIT USER ----------------
@app.route("/admin/edit-user/<int:user_id>", methods=["GET", "POST"])
def admin_edit_user(user_id):

    # Make sure only admin can access
    if "role" not in session or session["role"] != "admin":
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        full_name = request.form["full_name"]
        password = request.form["password"]
        role = request.form["role"]

        cur.execute("""
            UPDATE users
            SET full_name=?, password=?, role=?
            WHERE id=?
        """, (full_name, password, role, user_id))

        conn.commit()
        conn.close()

        return redirect("/admin")

    # GET request → Load user info
    cur.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = cur.fetchone()
    conn.close()

    return render_template("admin_edit_user.html", user=user)
# ---------------- CREATE USER ----------------
@app.route("/create-user", methods=["GET", "POST"])
def create_user():

    if "role" not in session or session["role"] != "admin":
        return redirect("/")

    if request.method == "POST":
        full_name = request.form["full_name"]
        username = request.form["username"]
        password = request.form["password"]
        role = "teacher"

        photo_file = request.files["photo"]
        photo_filename = None

        if photo_file and photo_file.filename != "":
            filename = secure_filename(photo_file.filename)
            photo_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            photo_file.save(photo_path)
            photo_filename = filename

        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute("""
            INSERT INTO users (full_name, username, password, role, photo)
            VALUES (?, ?, ?, ?, ?)
            """, (full_name, username, password, role, photo_filename))

            conn.commit()
            conn.close()
            return redirect("/admin")

        except sqlite3.IntegrityError:
            conn.close()
            return render_template("create_user.html", msg="User already exists")

    return render_template("create_user.html")
#----------------CREATE STUDENT--------------------------
@app.route("/create-student", methods=["GET", "POST"])
def create_student():

    if "role" not in session or session["role"] != "admin":
        return redirect("/")

    if request.method == "POST":
        full_name = request.form["full_name"]
        username = request.form["username"]
        password = request.form["password"]
        year = request.form["year"]
        role = "student"

        photo_file = request.files["photo"]
        photo_filename = None

        if photo_file and photo_file.filename != "":
            filename = secure_filename(photo_file.filename)
            photo_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            photo_file.save(photo_path)
            photo_filename = filename

        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute("""
            INSERT INTO users (full_name, username, password, role, year, photo)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (full_name, username, password,role , year, photo_filename))

            conn.commit()
            conn.close()
            return redirect("/admin")

        except sqlite3.IntegrityError:
            conn.close()
            return render_template("create_student.html", msg="User already exists")

    return render_template("create_student.html")

# ---------------- ADMIN DELETE ----------------

@app.route("/admin/delete-user/<int:user_id>")
def admin_delete_user(user_id):

    if "role" not in session or session["role"] != "admin":
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT username FROM users WHERE id=?", (user_id,))
    user = cur.fetchone()

    if user and user["username"] == "admin":
        conn.close()
        return redirect("/admin")

    cur.execute("""
        DELETE FROM attendance
        WHERE student = (SELECT username FROM users WHERE id=?)
    """, (user_id,))

    cur.execute("DELETE FROM users WHERE id=?", (user_id,))

    conn.commit()
    conn.close()

    return redirect("/admin")

# ---------------- TEACHER DASHBOARD ----------------
@app.route("/teacher/dashboard")
def teacher_dashboard():

    if "username" not in session or session["role"] != "teacher":
        return redirect("/")

    teacher = session["username"]
    today = date.today().strftime("%Y-%m-%d")

    conn = get_db()
    cur = conn.cursor()

    # ---------------- ASSIGNED CLASSES ----------------
    cur.execute("""
        SELECT year, period
        FROM teacher_assignment
        WHERE teacher=?
    """, (teacher,))
    assignments = cur.fetchall()

    assigned_classes = []
    today_status = []

    for a in assignments:
        year = a["year"]
        period = a["period"]

        assigned_classes.append({
            "year": year,
            "period": period
        })

        # Check if marked today
        cur.execute("""
            SELECT COUNT(*) as count
            FROM attendance
            WHERE teacher=? AND date=? AND period=?
        """, (teacher, today, period))

        marked = cur.fetchone()["count"]

        today_status.append({
            "period": period,
            "year": year,
            "status": "Completed" if marked > 0 else "Pending"
        })

    # ---------------- YEAR-WISE STUDENT COUNT ----------------
    cur.execute("SELECT COUNT(*) as total FROM users WHERE role='student' AND year='1'")
    year1_total = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) as total FROM users WHERE role='student' AND year='2'")
    year2_total = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) as total FROM users WHERE role='student' AND year='3'")
    year3_total = cur.fetchone()["total"]

    # ---------------- YEAR-WISE ATTENDANCE ----------------
    def get_year_attendance(year):
        cur.execute("""
            SELECT COUNT(*) as total
            FROM attendance a
            JOIN users u ON a.student = u.username
            WHERE u.year=?
        """, (year,))
        total = cur.fetchone()["total"]

        cur.execute("""
            SELECT COUNT(*) as present
            FROM attendance a
            JOIN users u ON a.student = u.username
            WHERE u.year=? AND a.status='Present'
        """, (year,))
        present = cur.fetchone()["present"]

        if total == 0:
            return 0

        return round((present / total) * 100, 2)

    year1_attendance = get_year_attendance('1')
    year2_attendance = get_year_attendance('2')
    year3_attendance = get_year_attendance('3')

    # ---------------- TEACHER PROFILE ----------------
    cur.execute("""
        SELECT full_name, photo
        FROM users
        WHERE username=? AND role='teacher'
    """, (teacher,))
    teacher_data = cur.fetchone()

    conn.close()

    # ---------------- RETURN ----------------
    return render_template(
        "teacher_dashboard.html",
        teacher_name=teacher_data["full_name"],
        teacher_photo=teacher_data["photo"],
        assigned_classes=assigned_classes,
        today_status=today_status,
        year1_total=year1_total,
        year2_total=year2_total,
        year3_total=year3_total,
        year1_attendance=year1_attendance,
        year2_attendance=year2_attendance,
        year3_attendance=year3_attendance
    )
# ---------------- TEACHER STUDENTS ----------------
@app.route("/teacher/students")
def teacher_students():

    if "username" not in session or session["role"] != "teacher":
        return redirect("/")

    teacher = session["username"]
    conn = get_db()
    cur = conn.cursor()

    # Get assigned years
    cur.execute("""
        SELECT DISTINCT year
        FROM teacher_assignment
        WHERE teacher=?
    """, (teacher,))
    years = [row["year"] for row in cur.fetchall()]

    year1_students = []
    year2_students = []
    year3_students = []

    if '1' in years:
        cur.execute("SELECT * FROM users WHERE role='student' AND year='1'")
        year1_students = cur.fetchall()

    if '2' in years:
        cur.execute("SELECT * FROM users WHERE role='student' AND year='2'")
        year2_students = cur.fetchall()

    if '3' in years:
        cur.execute("SELECT * FROM users WHERE role='student' AND year='3'")
        year3_students = cur.fetchall()

    conn.close()

    return render_template(
        "teacher_students.html",
        year1_students=year1_students,
        year2_students=year2_students,
        year3_students=year3_students
    )
# ---------------- MARK ATTENDANCE ----------------
@app.route("/teacher/mark-attendance", methods=["GET", "POST"])
def mark_attendance():
    if "username" not in session or session["role"] != "teacher":
        return redirect("/")

    teacher = session["username"]
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT year, period FROM teacher_assignment WHERE teacher=?", (teacher,))
    assignments = cur.fetchall()
    allowed_periods = [a["period"] for a in assignments]

    students = []
    date = ""
    period = ""

    if request.method == "POST":
        from datetime import date as today_date

        selected_date = request.form.get("date")
        today = today_date.today().isoformat()

        if selected_date > today:
            return render_template(
                "mark_attendance.html",
                students=[],
                allowed_periods=allowed_periods,
                date=selected_date,
                period=period,
                error="You cannot mark attendance for future dates."
            )
        date = request.form.get("date")
        period = request.form.get("period")
        action = request.form.get("action")

        if not date or not period:
            return render_template("mark_attendance.html", students=[], allowed_periods=allowed_periods, 
                                   date=date, period=period, error="Please select date and period")

        cur.execute("SELECT year FROM teacher_assignment WHERE teacher=? AND period=?", (teacher, period))
        row = cur.fetchone()
        
        if row:
            assigned_year = row["year"]
            cur.execute("SELECT username FROM users WHERE role='student' AND year=?", (assigned_year,))
            students = [r["username"] for r in cur.fetchall()]

            if action == "save":
                for student in students:
                    status = request.form.get(student)
                    if not status:
                        return render_template("mark_attendance.html", students=students, allowed_periods=allowed_periods, 
                                               date=date, period=period, error="Please mark all students")

                    # Check for existing record
                    cur.execute("SELECT 1 FROM attendance WHERE student=? AND date=? AND period=?", (student, date, period))
                    if cur.fetchone():
                        return render_template("mark_attendance.html", students=students, allowed_periods=allowed_periods, 
                                               date=date, period=period, error=f"Already marked for Period {period}")

                    cur.execute("INSERT INTO attendance (student, teacher, date, period, status) VALUES (?, ?, ?, ?, ?)",
                                (student, teacher, date, period, status))
                
                conn.commit()
                success_msg = f"Attendance saved for Period {period}"
                return render_template("mark_attendance.html", students=students, allowed_periods=allowed_periods, 
                                       date=date, period=period, success=success_msg)

    return render_template("mark_attendance.html", students=students, allowed_periods=allowed_periods, date=date, period=period)
#---------------edit attendance----------------------------------------------
from flask import Flask, render_template, request, session, flash, redirect, url_for
import sqlite3

@app.route('/edit_attendance', methods=['GET', 'POST'])
def edit_attendance():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()

    year1, year2, year3 = [], [], []
    attendance_data = {}
    date = request.form.get('date')
    period = request.form.get('period')
    teacher = session.get('username')

    if request.method == 'POST':
        # 1. Fetch all students first to know who we are dealing with
        cursor.execute("SELECT username, year FROM users WHERE role='student'")
        data = cursor.fetchall()

        # 2. HANDLE THE SAVE ACTION
        if 'save' in request.form:
            for student, year in data:
                status = request.form.get(f'status_{student}')
                if status:
                    cursor.execute("""
                        INSERT OR REPLACE INTO attendance 
                        (student, teacher, date, period, status) 
                        VALUES (?, ?, ?, ?, ?)
                    """, (student, teacher, date, period, status))
            
            conn.commit()
            flash('Attendance updated successfully!', 'success') # <-- THE NOTIFICATION

        # 3. FETCH DATA FOR DISPLAY 
        # (This runs for both 'Load' and 'Save' to ensure UI is fresh)
        for student, year in data:
            if str(year) == '1': year1.append(student)
            elif str(year) == '2': year2.append(student)
            elif str(year) == '3': year3.append(student)

            cursor.execute("""
                SELECT status FROM attendance 
                WHERE student=? AND date=? AND period=?
            """, (student, date, period))
            
            result = cursor.fetchone()
            attendance_data[student] = result[0] if result else None

    conn.close()

    return render_template(
        'edit_attendance.html',
        year1=year1, year2=year2, year3=year3,
        attendance_data=attendance_data,
        date=date, period=period
    )
# ---------------- report ----------------
@app.route("/teacher/reports")
def teacher_reports():
    if "username" not in session or session["role"] != "teacher":
        return redirect("/")

    teacher = session["username"]
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT year FROM teacher_assignment WHERE teacher=?", (teacher,))
    assigned_years = [row["year"] for row in cur.fetchall()]

    year_data = {}

    for year in assigned_years:
        cur.execute("SELECT username FROM users WHERE role='student' AND year=?", (year,))
        students = [row["username"] for row in cur.fetchall()]
        
        student_list = []
        year_present = 0
        year_total_records = 0

        for student in students:
            cur.execute("SELECT COUNT(*) as total FROM attendance WHERE student=?", (student,))
            total = cur.fetchone()["total"]
            cur.execute("SELECT COUNT(*) as present FROM attendance WHERE student=? AND status='Present'", (student,))
            present = cur.fetchone()["present"]

            percent = round((present/total)*100, 2) if total > 0 else 0
            student_list.append({"name": student, "percentage": percent})
            
            year_present += present
            year_total_records += total

        # Store data specific to this year
        year_data[year] = {
            "students": student_list,
            "present": year_present,
            "absent": year_total_records - year_present
        }

    conn.close()
    return render_template("teacher_reports.html", year_data=year_data)
# ---------------- EXPORT CSV ----------------
@app.route("/teacher/export-attendance")
def export_attendance():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT student, date, status
    FROM attendance
    ORDER BY date
    """)
    records = cur.fetchall()
    conn.close()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student", "Date", "Status"])

    for r in records:
        writer.writerow([r["student"], r["date"], r["status"]])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance.csv"}
    )

# ---------------- STUDENT DASHBOARD ----------------
@app.route("/student/dashboard/<username>")
def student_dashboard(username):

    if "username" not in session or session["role"] != "student":
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT full_name, photo
        FROM users
        WHERE username=? AND role='student'
    """, (username,))
    student = cur.fetchone()
    # Get student's academic year
    cur.execute("SELECT year FROM users WHERE username=?", (username,))
    student_year = cur.fetchone()["year"]

    # Get period-wise attendance
    cur.execute("""
        SELECT date, period, status
        FROM attendance
        WHERE student=?
        ORDER BY date DESC, period ASC
    """, (username,))

    rows = cur.fetchall()

    attendance_by_date = {}
    from collections import defaultdict
    monthly_summary = defaultdict(lambda: {
        "present": 0,
        "absent": 0,
        "late": 0,
        "total": 0
    })

    for row in rows:
        d = row["date"]
        p = row["period"]
        s = row["status"]

        if d not in attendance_by_date:
            attendance_by_date[d] = {
                "P1": "-",
                "P2": "-",
                "P3": "-",
                "P4": "-",
                "P5": "-"
            }

        attendance_by_date[d][f"P{p}"] = s[0]  # P / A / L

    # Build table
    table_data = []

    for d, periods in attendance_by_date.items():
        month = d[:7] 
        present = list(periods.values()).count("P")
        absent = list(periods.values()).count("A")
        late = list(periods.values()).count("L")

        total = present + absent + late

        monthly_summary[month]["present"] += present
        monthly_summary[month]["absent"] += absent
        monthly_summary[month]["late"] += late
        monthly_summary[month]["total"] += total
        
        table_data.append({
            "date": d,
            "P1": periods["P1"],
            "P2": periods["P2"],
            "P3": periods["P3"],
            "P4": periods["P4"],
            "P5": periods["P5"],
            "present": present,
            "absent": absent,
            "late": late,
            "total": total
        })

    # -------- MONTH DATA --------
    month_data = []
    for m, data in monthly_summary.items():
        percentage = round((data["present"] / data["total"]) * 100, 2) if data["total"] > 0 else 0
        
        month_data.append({
            "month": m,
            "total": data["total"],
            "present": data["present"],
            "absent": data["absent"],
            "late": data["late"],
            "percentage": percentage
        })
        # Calculate total classes conducted for the student's year
    cur.execute("""
    SELECT COUNT(DISTINCT date || '-' || period) as total
    FROM attendance a
    JOIN users u ON a.student = u.username
    WHERE u.year=?
    """, (student_year,))
    total_classes = cur.fetchone()["total"]

    conn.close()

    # -------- FINAL TOTAL CALCULATION --------
    present_total = 0
    absent_total = 0
    late_total = 0
    

    for row in table_data:
        present_total += row["present"]
        absent_total += row["absent"]
        late_total += row["late"]

    percentage = round((present_total / total_classes) * 100, 2) if total_classes > 0 else 0

    # -------- FINAL STUDENT STATUS --------
    if percentage >= 75:
        status = "Eligible"
        warning = "You are safe for exams"
    elif percentage >= 65:
        status = "Condoned"
        warning = "Warning: Attendance is below safe level"
    elif percentage >= 50:
        status = "Withheld"
        warning = "Risk: Attendance too low"
    else:
        status = "Detained"
        warning = "Critical: You are not eligible for exams"

    return render_template(
        "student_dashboard.html",
        student=student,
        table_data=table_data,
        month_data=month_data,
        present=present_total,
        absent=absent_total,
        late=late_total,
        percentage=percentage,
        status=status,
        warning=warning
    )
# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)