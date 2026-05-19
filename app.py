from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime
import certifi

app = Flask(__name__)
app.secret_key = "srms_secret_key_2024"

# ── MongoDB Atlas Connection ──
uri = "mongodb+srv://adminuser:admin123456@cluster0.bageaje.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

client = MongoClient(
    uri,
    server_api=ServerApi('1'),
    tlsCAFile=certifi.where(),
    tlsAllowInvalidCertificates=True
)

db = client["student_management"]

users_col      = db["users"]
students_col   = db["students"]
marks_col      = db["marks"]
attendance_col = db["attendance"]

# ── Home ──
@app.route("/")
def home():
    return redirect(url_for("login"))

# ── Login ──
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = users_col.find_one({
            "username": username,
            "password": password
        })
        if user:
            session["user"] = username
            session["role"] = user["role"]
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("student_dashboard"))
        else:
            flash("Invalid username or password!", "error")
    return render_template("login.html")

# ── Logout ──
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ── Admin Dashboard ──
@app.route("/admin")
def admin_dashboard():
    if "user" not in session or session["role"] != "admin":
        return redirect(url_for("login"))
    total_students = students_col.count_documents({})
    total_marks    = marks_col.count_documents({})
    total_attend   = attendance_col.count_documents({})
    return render_template("admin_dashboard.html",
                           total_students=total_students,
                           total_marks=total_marks,
                           total_attend=total_attend)

# ── Student Dashboard ──
@app.route("/student")
def student_dashboard():
    if "user" not in session or session["role"] != "student":
        return redirect(url_for("login"))

    student = students_col.find_one({"username": session["user"]})
    if not student:
        return redirect(url_for("logout"))

    student_id = student["student_id"]

    # Marks
    student_marks  = list(marks_col.find({"student_id": student_id}))
    total_subjects = len(student_marks)
    avg_percentage = 0
    if student_marks:
        avg_percentage = round(
            sum(m["percentage"] for m in student_marks) / total_subjects, 1
        )

    # Attendance
    student_attendance = list(attendance_col.find(
        {"student_id": student_id},
        sort=[("date", -1)]
    ))
    total_records    = len(student_attendance)
    present_count    = sum(1 for r in student_attendance if r["status"] == "Present")
    absent_count     = sum(1 for r in student_attendance if r["status"] == "Absent")
    late_count       = sum(1 for r in student_attendance if r["status"] == "Late")
    attendance_percent = 0
    if total_records > 0:
        attendance_percent = round((present_count / total_records) * 100, 1)

    return render_template("student_dashboard.html",
                           student=student,
                           student_marks=student_marks,
                           total_subjects=total_subjects,
                           avg_percentage=avg_percentage,
                           student_attendance=student_attendance,
                           present_count=present_count,
                           absent_count=absent_count,
                           late_count=late_count,
                           attendance_percent=attendance_percent)

# ── Add Student ──
@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    if "user" not in session or session["role"] != "admin":
        return redirect(url_for("login"))
    if request.method == "POST":
        name     = request.form["name"]
        phone    = request.form["phone"]
        address  = request.form["address"]
        course   = request.form["course"]
        password = request.form["password"]

        # Auto Student ID Generate
        count      = students_col.count_documents({})
        student_id = f"TY-2024-{str(count + 1).zfill(3)}"

        # Student Save
        students_col.insert_one({
            "student_id":    student_id,
            "name":          name,
            "phone":         phone,
            "address":       address,
            "course":        course,
            "password":      password,
            "username":      name.lower().replace(" ", ""),
            "enrolled_date": datetime.now().strftime("%Y-%m-%d"),
            "status":        "active"
        })

        # User Login Create
        users_col.insert_one({
            "username": name.lower().replace(" ", ""),
            "password": password,
            "role":     "student",
            "name":     name
        })

        flash("Student added successfully!", "success")
        return redirect(url_for("students"))
    return render_template("add_student.html")

# ── Students List ──
@app.route("/students")
def students():
    if "user" not in session or session["role"] != "admin":
        return redirect(url_for("login"))
    all_students = list(students_col.find())
    return render_template("students.html", students=all_students)

# ── Marks ──
@app.route("/marks", methods=["GET", "POST"])
def marks():
    if "user" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    all_students = list(students_col.find())

    if request.method == "POST":
        student_id     = request.form["student_id"]
        subject        = request.form["subject"]
        marks_obtained = int(request.form["marks"])
        total_marks    = int(request.form["total_marks"])

        # Grade Calculate
        percentage = (marks_obtained / total_marks) * 100
        if percentage >= 90:
            grade = "A+"
        elif percentage >= 80:
            grade = "A"
        elif percentage >= 70:
            grade = "B"
        elif percentage >= 60:
            grade = "C"
        elif percentage >= 50:
            grade = "D"
        else:
            grade = "F"

        marks_col.insert_one({
            "student_id":     student_id,
            "subject":        subject,
            "marks_obtained": marks_obtained,
            "total_marks":    total_marks,
            "percentage":     round(percentage, 2),
            "grade":          grade,
            "date":           datetime.now().strftime("%Y-%m-%d")
        })

        flash("Marks added successfully!", "success")
        return redirect(url_for("marks"))

    all_marks = list(marks_col.find())
    return render_template("marks.html",
                           students=all_students,
                           all_marks=all_marks)

# ── Attendance ──
@app.route("/attendance", methods=["GET", "POST"])
def attendance():
    if "user" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    all_students = list(students_col.find())
    today        = datetime.now().strftime("%Y-%m-%d")

    if request.method == "POST":
        student_id = request.form["student_id"]
        date       = request.form["date"]
        status     = request.form["status"]

        # Student name fetch karo
        student = students_col.find_one({"student_id": student_id})
        student_name = student["name"] if student else "Unknown"

        # Duplicate check - same student same date
        existing = attendance_col.find_one({
            "student_id": student_id,
            "date":       date
        })
        if existing:
            flash(f"Attendance already marked for {student_name} on {date}!", "error")
        else:
            attendance_col.insert_one({
                "student_id":   student_id,
                "student_name": student_name,
                "date":         date,
                "status":       status,
                "marked_at":    datetime.now().strftime("%Y-%m-%d %H:%M")
            })
            flash(f"Attendance marked for {student_name} - {status}!", "success")

        return redirect(url_for("attendance"))

    # Filter logic
    query = {}
    filter_student = request.args.get("filter_student", "").strip()
    filter_status  = request.args.get("filter_status", "").strip()

    if filter_student:
        query["student_id"] = {"$regex": filter_student, "$options": "i"}
    if filter_status:
        query["status"] = filter_status

    attendance_records = list(attendance_col.find(query, sort=[("date", -1)]))

    # Stats (always on full data)
    total_present = attendance_col.count_documents({"status": "Present"})
    total_absent  = attendance_col.count_documents({"status": "Absent"})
    total_late    = attendance_col.count_documents({"status": "Late"})
    total_records = attendance_col.count_documents({})

    return render_template("attendance.html",
                           students=all_students,
                           attendance_records=attendance_records,
                           today=today,
                           total_present=total_present,
                           total_absent=total_absent,
                           total_late=total_late,
                           total_records=total_records)

# ── Admin Create (First Run) ──
if __name__ == "__main__":
    if not users_col.find_one({"username": "admin"}):
        users_col.insert_one({
            "username": "admin",
            "password": "admin123",
            "role":     "admin"
        })
    app.run(debug=True)
