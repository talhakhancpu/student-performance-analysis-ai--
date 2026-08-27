import os
import json
import joblib
import pandas as pd

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Avg, Max, Min, Count, Q

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable
)

from .models import Student, Subject, StudentSubjectMark, Profile

try:
    from google import genai
except ImportError:
    genai = None


from functools import wraps
from django.db import connection

_schema_verified = False

def ensure_schema_ready():
    """Ensure all required SQLite tables, columns and default demo data exist."""
    global _schema_verified
    if _schema_verified:
        return
    try:
        with connection.cursor() as cur:
            # 1. Ensure Subject table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chatbot_subject (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    code VARCHAR(20) NOT NULL UNIQUE,
                    max_marks REAL NOT NULL DEFAULT 100,
                    pass_marks REAL NOT NULL DEFAULT 50
                );
            """)

            # 2. Ensure StudentSubjectMark table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chatbot_studentsubjectmark (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    marks_obtained REAL NOT NULL DEFAULT 0,
                    grade VARCHAR(5) NOT NULL DEFAULT '',
                    remarks VARCHAR(100) NOT NULL DEFAULT '',
                    student_id BIGINT NOT NULL REFERENCES chatbot_student(id) DEFERRABLE INITIALLY DEFERRED,
                    subject_id BIGINT NOT NULL REFERENCES chatbot_subject(id) DEFERRABLE INITIALLY DEFERRED,
                    UNIQUE (student_id, subject_id)
                );
            """)

            # 3. Check and add all missing columns to chatbot_student
            cur.execute("PRAGMA table_info(chatbot_student);")
            cols = [row[1] for row in cur.fetchall()]
            if cols:
                if "user_id" not in cols:
                    try:
                        cur.execute("ALTER TABLE chatbot_student ADD COLUMN user_id INTEGER REFERENCES auth_user(id);")
                    except Exception:
                        pass
                if "total_marks" not in cols:
                    try:
                        cur.execute("ALTER TABLE chatbot_student ADD COLUMN total_marks REAL NOT NULL DEFAULT 0;")
                    except Exception:
                        pass
                if "max_total_marks" not in cols:
                    try:
                        cur.execute("ALTER TABLE chatbot_student ADD COLUMN max_total_marks REAL NOT NULL DEFAULT 0;")
                    except Exception:
                        pass
                if "father_name" not in cols:
                    try:
                        cur.execute("ALTER TABLE chatbot_student ADD COLUMN father_name VARCHAR(100) NOT NULL DEFAULT '';")
                    except Exception:
                        pass
                if "phone" not in cols:
                    try:
                        cur.execute("ALTER TABLE chatbot_student ADD COLUMN phone VARCHAR(30) NOT NULL DEFAULT '';")
                    except Exception:
                        pass
                if "study_hours" not in cols:
                    try:
                        cur.execute("ALTER TABLE chatbot_student ADD COLUMN study_hours REAL NOT NULL DEFAULT 0;")
                    except Exception:
                        pass
                if "assignment_score" not in cols:
                    try:
                        cur.execute("ALTER TABLE chatbot_student ADD COLUMN assignment_score REAL NOT NULL DEFAULT 0;")
                    except Exception:
                        pass
                if "quiz_score" not in cols:
                    try:
                        cur.execute("ALTER TABLE chatbot_student ADD COLUMN quiz_score REAL NOT NULL DEFAULT 0;")
                    except Exception:
                        pass
                if "previous_marks" not in cols:
                    try:
                        cur.execute("ALTER TABLE chatbot_student ADD COLUMN previous_marks REAL NOT NULL DEFAULT 0;")
                    except Exception:
                        pass
                if "predicted_marks" not in cols:
                    try:
                        cur.execute("ALTER TABLE chatbot_student ADD COLUMN predicted_marks REAL NULL;")
                    except Exception:
                        pass
                if "performance_level" not in cols:
                    try:
                        cur.execute("ALTER TABLE chatbot_student ADD COLUMN performance_level VARCHAR(30) NOT NULL DEFAULT '';")
                    except Exception:
                        pass

        # Seed subjects if missing
        sub_math, _ = Subject.objects.get_or_create(name="Mathematics", defaults={"code": "MATH-101", "max_marks": 100, "pass_marks": 50})
        sub_cs, _ = Subject.objects.get_or_create(name="Computer Science", defaults={"code": "CS-101", "max_marks": 100, "pass_marks": 50})
        sub_phy, _ = Subject.objects.get_or_create(name="Physics", defaults={"code": "PHY-101", "max_marks": 100, "pass_marks": 50})
        sub_eng, _ = Subject.objects.get_or_create(name="English", defaults={"code": "ENG-101", "max_marks": 100, "pass_marks": 50})
        sub_ds, _ = Subject.objects.get_or_create(name="Data Science", defaults={"code": "DS-101", "max_marks": 100, "pass_marks": 50})

        # Seed demo users if missing
        admin_u, created_a = User.objects.get_or_create(username="admin", defaults={"email": "admin@qa.edu", "is_staff": True, "is_superuser": True})
        if created_a:
            admin_u.set_password("admin123")
            admin_u.save()
        admin_p, _ = Profile.objects.get_or_create(user=admin_u)
        admin_p.role = "admin"
        admin_p.save()

        teach_u, created_t = User.objects.get_or_create(username="teacher", defaults={"email": "teacher@qa.edu", "is_staff": False})
        if created_t:
            teach_u.set_password("teacher123")
            teach_u.save()
        teach_p, _ = Profile.objects.get_or_create(user=teach_u)
        teach_p.role = "teacher"
        teach_p.save()

        sarah_u, created_s = User.objects.get_or_create(username="sarah", defaults={"email": "sarah.ahmed@qa.edu"})
        if created_s:
            sarah_u.set_password("student123")
            sarah_u.save()
        sarah_p, _ = Profile.objects.get_or_create(user=sarah_u)
        sarah_p.role = "student"
        sarah_p.save()

        # Seed 6 sample students if database is empty
        if Student.objects.count() < 4:
            samples = [
                {
                    "user": sarah_u, "student_id": "QA-1001", "name": "Sarah Ahmed", "email": "sarah.ahmed@qa.edu",
                    "father_name": "Tariq Ahmed", "phone": "+92 301 5551234", "age": 19, "gender": "Female",
                    "attendance": 96.5, "study_hours": 6.0, "assignment_score": 95.0, "quiz_score": 92.0, "previous_marks": 90.0,
                    "marks_dict": {sub_math: 94.0, sub_cs: 98.0, sub_phy: 91.0, sub_eng: 89.0, sub_ds: 96.0}
                },
                {
                    "user": None, "student_id": "QA-1002", "name": "Bilal Khan", "email": "bilal.khan@qa.edu",
                    "father_name": "Rashid Khan", "phone": "+92 302 5552345", "age": 20, "gender": "Male",
                    "attendance": 88.0, "study_hours": 4.5, "assignment_score": 86.0, "quiz_score": 84.0, "previous_marks": 82.0,
                    "marks_dict": {sub_math: 85.0, sub_cs: 89.0, sub_phy: 81.0, sub_eng: 79.0, sub_ds: 86.0}
                },
                {
                    "user": None, "student_id": "QA-1003", "name": "Ayesha Malik", "email": "ayesha.malik@qa.edu",
                    "father_name": "Zafar Malik", "phone": "+92 303 5553456", "age": 19, "gender": "Female",
                    "attendance": 81.5, "study_hours": 3.5, "assignment_score": 78.0, "quiz_score": 75.0, "previous_marks": 73.0,
                    "marks_dict": {sub_math: 72.0, sub_cs: 78.0, sub_phy: 70.0, sub_eng: 82.0, sub_ds: 74.0}
                },
                {
                    "user": None, "student_id": "QA-1004", "name": "Hamza Tariq", "email": "hamza.tariq@qa.edu",
                    "father_name": "Tariq Mahmood", "phone": "+92 304 5554567", "age": 21, "gender": "Male",
                    "attendance": 74.0, "study_hours": 2.5, "assignment_score": 68.0, "quiz_score": 65.0, "previous_marks": 63.0,
                    "marks_dict": {sub_math: 62.0, sub_cs: 68.0, sub_phy: 58.0, sub_eng: 71.0, sub_ds: 64.0}
                },
                {
                    "user": None, "student_id": "QA-1005", "name": "Zainab Raza", "email": "zainab.raza@qa.edu",
                    "father_name": "Ali Raza", "phone": "+92 305 5555678", "age": 18, "gender": "Female",
                    "attendance": 67.0, "study_hours": 2.0, "assignment_score": 56.0, "quiz_score": 54.0, "previous_marks": 52.0,
                    "marks_dict": {sub_math: 52.0, sub_cs: 56.0, sub_phy: 48.0, sub_eng: 62.0, sub_ds: 54.0}
                },
                {
                    "user": None, "student_id": "QA-1006", "name": "Usman Farooq", "email": "usman.farooq@qa.edu",
                    "father_name": "Farooq Azam", "phone": "+92 306 5556789", "age": 20, "gender": "Male",
                    "attendance": 92.0, "study_hours": 5.2, "assignment_score": 90.0, "quiz_score": 88.0, "previous_marks": 87.0,
                    "marks_dict": {sub_math: 90.0, sub_cs: 93.0, sub_phy: 87.0, sub_eng: 85.0, sub_ds: 91.0}
                },
            ]
            for s_data in samples:
                m_dict = s_data.pop("marks_dict")
                st, _ = Student.objects.update_or_create(student_id=s_data["student_id"], defaults=s_data)
                for sub_obj, mark_num in m_dict.items():
                    smark, _ = StudentSubjectMark.objects.get_or_create(student=st, subject=sub_obj)
                    smark.marks_obtained = mark_num
                    smark.remarks = "Satisfactory" if mark_num >= 50 else "Needs Improvement"
                    smark.save()
                st.calculate_totals()

        _schema_verified = True
    except Exception:
        pass


# ==============================================================================
# Role-Based Access Control Helpers & Decorators
# ==============================================================================

def get_user_role(user):
    ensure_schema_ready()
    if not user or not user.is_authenticated:
        return "guest"
    if user.is_superuser or user.is_staff:
        return "admin"
    try:
        if hasattr(user, "profile"):
            return user.profile.role
    except Exception:
        pass
    return "student"


def is_admin(user):
    ensure_schema_ready()
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    try:
        if hasattr(user, "profile"):
            return user.profile.role == "admin"
    except Exception:
        pass
    return False


def is_teacher(user):
    ensure_schema_ready()
    if not user or not user.is_authenticated:
        return False
    try:
        if hasattr(user, "profile"):
            return user.profile.role == "teacher"
    except Exception:
        pass
    return False


def is_student(user):
    ensure_schema_ready()
    if not user or not user.is_authenticated:
        return False
    if is_admin(user) or is_teacher(user):
        return False
    try:
        if hasattr(user, "profile"):
            return user.profile.role == "student"
    except Exception:
        pass
    return True


def teacher_or_admin(user):
    return is_admin(user) or is_teacher(user)


def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        ensure_schema_ready()
        if not is_admin(request.user):
            messages.error(request, "Admin access required. Permission denied.")
            return redirect("dashboard" if teacher_or_admin(request.user) else "student_portal")
        return view_func(request, *args, **kwargs)
    return wrapper


def teacher_or_admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        ensure_schema_ready()
        if not teacher_or_admin(request.user):
            messages.error(request, "Teacher or Admin access required. Permission denied.")
            return redirect("student_portal")
        return view_func(request, *args, **kwargs)
    return wrapper



# ==============================================================================
# Public & Authentication Views
# ==============================================================================

def home(request):
    """Clean, stylish QA Landing page."""
    role = get_user_role(request.user)
    return render(request, "chatbot/index.html", {
        "user_role": role,
    })


def login_view(request):
    """Clean login view with role-based post-login redirection."""
    if request.user.is_authenticated:
        if is_student(request.user):
            return redirect("student_portal")
        return redirect("dashboard")

    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            if is_student(user):
                return redirect("student_portal")
            return redirect("dashboard")
        else:
            error = "Invalid username or password. Please try again."

    return render(request, "chatbot/login.html", {"error": error})


def register(request):
    """Public registration — Students only. Admin/Teacher accounts must be created by an Admin."""
    if request.user.is_authenticated:
        return redirect("student_portal" if is_student(request.user) else "dashboard")

    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        confirm_password = request.POST.get("confirm_password", "").strip()
        full_name = request.POST.get("full_name", "").strip() or username

        if not username or not password:
            error = "Username and password are required."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif password != confirm_password:
            error = "Passwords do not match."
        elif User.objects.filter(username=username).exists():
            error = f"Username '{username}' is already taken."
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            # All public registrations are STUDENT only — hardcoded, not from form
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.role = "student"
            profile.save()

            # Auto-create linked Student record
            student_id = f"QA-{user.id:04d}"
            Student.objects.get_or_create(
                user=user,
                defaults={
                    "student_id": student_id,
                    "name": full_name,
                    "email": email,
                    "attendance": 80.0,
                    "marks": 0,
                    "total_marks": 0,
                    "max_total_marks": 100,
                }
            )

            messages.success(request, "Student account created! Please log in.")
            return redirect("login")

    return render(request, "chatbot/register.html", {"error": error})


@admin_required
def create_staff_account(request):
    """Admins only: create teacher or admin accounts."""
    error = None
    success = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        role = request.POST.get("role", "teacher").strip()
        full_name = request.POST.get("full_name", "").strip() or username

        # Only allow teacher or admin roles here
        if role not in ("teacher", "admin"):
            role = "teacher"

        if not username or not password:
            error = "Username and password are required."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif User.objects.filter(username=username).exists():
            error = f"Username '{username}' is already taken."
        else:
            is_superuser = role == "admin"
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                is_staff=is_superuser,
                is_superuser=is_superuser
            )
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.role = role
            profile.save()
            success = f"{'Admin' if role == 'admin' else 'Teacher'} account '{username}' created successfully."

    all_staff = User.objects.filter(profile__role__in=["teacher", "admin"]).select_related("profile").order_by("-id")
    return render(request, "chatbot/create_staff.html", {
        "error": error,
        "success": success,
        "staff_users": all_staff,
        "is_admin": True,
    })


def logout_user(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect("home")


# ==============================================================================
# AI Chatbot Assistant API
# ==============================================================================

def get_gemini_response(message):
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key and genai:
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=message
            )
            return response.text
        except Exception as e:
            return f"QA Assistant: I'm currently running in offline mode. {message}"
    
    # Safe intelligent fallback when no API key is provided
    msg_lower = message.lower()
    if "mark" in msg_lower or "grade" in msg_lower or "score" in msg_lower:
        return "QA Assistant: You can manage and view subject marks, total calculations, and grading under the Marks or Dashboard tab."
    elif "report" in msg_lower:
        return "QA Assistant: PDF report cards can be generated under the Reports section for both individual students and class summaries."
    elif "predict" in msg_lower or "ml" in msg_lower:
        return "QA Assistant: Our ML model predicts future student performance based on attendance, study hours, assignments, and previous scores."
    elif "student" in msg_lower:
        return "QA Assistant: Students can log in to view their personal performance dashboard, subject grades, and download their official report card."
    return f"QA Assistant: Hello! I'm here to help you navigate QA Student Analytics. Feel free to ask about student grades, analytics, reports, or ML predictions!"


def chat_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            message = data.get("message", "")
            answer = get_gemini_response(message)
            return JsonResponse({"response": answer})
        except Exception as e:
            return JsonResponse({"response": "Sorry, I could not process that message."})
    return JsonResponse({"error": "POST request required"}, status=400)


# ==============================================================================
# Dashboards
# ==============================================================================

@login_required
def dashboard(request):
    """Dynamic Teacher & Admin Dashboard with live stats and switchable charts."""
    # If logged-in user is a student, route them strictly to their personal portal
    if is_student(request.user):
        return redirect("student_portal")

    students = Student.objects.all()
    total_students = students.count()
    subjects = Subject.objects.all()

    if total_students > 0:
        average_marks = round(sum(s.marks for s in students) / total_students, 2)
        average_attendance = round(sum(s.attendance for s in students) / total_students, 2)
        passed_students = students.filter(marks__gte=50).count()
        pass_rate = round((passed_students / total_students) * 100, 2)
        highest_marks = round(max(s.marks for s in students), 2)
    else:
        average_marks = 0
        average_attendance = 0
        pass_rate = 0
        highest_marks = 0

    # 1. Grade Distribution
    grade_data = {"A+": 0, "A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for student in students:
        g = student.grade or "F"
        if g in grade_data:
            grade_data[g] += 1
        else:
            grade_data[g] = 1

    # 2. Subject-Wise Performance
    subject_names = []
    subject_averages = []
    subject_highest = []
    subject_pass_rates = []
    subject_stats = []

    for sub in subjects:
        sub_marks = StudentSubjectMark.objects.filter(subject=sub)
        count = sub_marks.count()
        if count > 0:
            avg_m = round(sub_marks.aggregate(Avg("marks_obtained"))["marks_obtained__avg"] or 0, 2)
            max_m = round(sub_marks.aggregate(Max("marks_obtained"))["marks_obtained__max"] or 0, 2)
            passed = sub_marks.filter(marks_obtained__gte=sub.pass_marks).count()
            p_rate = round((passed / count) * 100, 2)
        else:
            avg_m = 0
            max_m = 0
            p_rate = 0

        subject_names.append(sub.name)
        subject_averages.append(avg_m)
        subject_highest.append(max_m)
        subject_pass_rates.append(p_rate)

        subject_stats.append({
            "id": sub.id,
            "name": sub.name,
            "code": sub.code,
            "max_marks": sub.max_marks,
            "pass_marks": sub.pass_marks,
            "avg_marks": avg_m,
            "max_marks_obtained": max_m,
            "pass_rate": p_rate,
            "enrolled": count,
        })

    # 3. Attendance vs Marks Scatter Data
    attendance_marks_data = []
    for s in students:
        attendance_marks_data.append({
            "name": s.name,
            "attendance": s.attendance,
            "marks": s.marks,
            "total_marks": s.total_marks,
        })

    # 4. Pass vs Fail Ratio
    passed_count = students.filter(marks__gte=50).count()
    fail_count = total_students - passed_count
    pass_fail_data = {"Passed": passed_count, "Failed": fail_count}

    return render(
        request,
        "chatbot/dashboard.html",
        {
            "total_students": total_students,
            "average_marks": average_marks,
            "average_attendance": average_attendance,
            "pass_rate": pass_rate,
            "highest_marks": highest_marks,
            "total_subjects": subjects.count(),
            "subject_stats": subject_stats,
            "grade_data": json.dumps(grade_data),
            "attendance_marks_data": json.dumps(attendance_marks_data),
            "subject_names": json.dumps(subject_names),
            "subject_averages": json.dumps(subject_averages),
            "subject_highest": json.dumps(subject_highest),
            "pass_fail_data": json.dumps(pass_fail_data),
            "user_role": get_user_role(request.user),
        }
    )


@login_required
def student_portal(request):
    """Dedicated Student Dashboard - Student can access ONLY their own academic records."""
    student = None
    try:
        if hasattr(request.user, "student_profile"):
            student = request.user.student_profile
    except Exception:
        student = None

    if not student:
        student = Student.objects.filter(
            Q(user=request.user) | Q(email=request.user.email) | Q(name=request.user.username)
        ).first()

    if not student:
        # Auto-provision initial student profile
        student = Student.objects.create(
            user=request.user,
            student_id=f"QA-{request.user.id:04d}",
            name=request.user.get_full_name() or request.user.username,
            email=request.user.email or f"{request.user.username}@qa.local",
            attendance=85.0,
            marks=0,
            total_marks=0,
            max_total_marks=100
        )

    # Ensure student is enrolled in available subjects
    subjects = Subject.objects.all()
    if subjects.exists() and not student.subject_marks.exists():
        for sub in subjects:
            StudentSubjectMark.objects.get_or_create(
                student=student,
                subject=sub,
                defaults={"marks_obtained": 0.0}
            )
        student.calculate_totals()

    # Subject marks list
    subject_marks = student.subject_marks.select_related("subject").all()

    # Personal subject chart data
    sub_labels = [sm.subject.name for sm in subject_marks]
    sub_scores = [sm.marks_obtained for sm in subject_marks]
    sub_max = [sm.subject.max_marks for sm in subject_marks]

    return render(
        request,
        "chatbot/student_portal.html",
        {
            "student": student,
            "subject_marks": subject_marks,
            "sub_labels_json": json.dumps(sub_labels),
            "sub_scores_json": json.dumps(sub_scores),
            "sub_max_json": json.dumps(sub_max),
            "user_role": "student",
        }
    )



# ==============================================================================
# Student Management Views (Teachers & Admins)
# ==============================================================================

@teacher_or_admin_required
def students(request):
    """Students list view with role-based controls."""
    search = request.GET.get("search", "").strip()
    student_list = Student.objects.all().prefetch_related("subject_marks__subject").order_by("-id")

    if search:
        student_list = student_list.filter(
            Q(name__icontains=search) | Q(student_id__icontains=search) | Q(email__icontains=search)
        )

    return render(
        request,
        "chatbot/students.html",
        {
            "students": student_list,
            "search": search,
            "is_admin": is_admin(request.user),
            "user_role": get_user_role(request.user),
        }
    )


@login_required
def student_detail(request, id):
    """Student profile detail with subject breakdown and security check."""
    student = get_object_or_404(Student, id=id)

    # If student user, enforce that they can only view their own profile
    if is_student(request.user):
        user_student = getattr(request.user, "student_profile", None)
        if not user_student or user_student.id != student.id:
            messages.error(request, "Access restricted: You can only view your own profile.")
            return redirect("student_portal")

    subject_marks = student.subject_marks.select_related("subject").all()

    # Chart data
    sub_labels = [sm.subject.name for sm in subject_marks]
    sub_scores = [sm.marks_obtained for sm in subject_marks]

    return render(
        request,
        "chatbot/student_detail.html",
        {
            "student": student,
            "subject_marks": subject_marks,
            "sub_labels_json": json.dumps(sub_labels),
            "sub_scores_json": json.dumps(sub_scores),
            "is_admin": is_admin(request.user),
            "is_teacher": is_teacher(request.user),
            "user_role": get_user_role(request.user),
        }
    )


@admin_required
def add_student(request):
    """Admin-only view to create a new student record."""
    subjects = Subject.objects.all()
    error = None

    if request.method == "POST":
        student_id = request.POST.get("student_id", "").strip()
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()

        if not student_id or not name:
            error = "Student ID and Name are required."
        elif Student.objects.filter(student_id=student_id).exists():
            error = f"Student ID '{student_id}' already exists. Please choose a unique ID."
        else:
            student = Student.objects.create(
                student_id=student_id,
                name=name,
                email=email,
                father_name=request.POST.get("father_name", "").strip(),
                phone=request.POST.get("phone", "").strip(),
                age=request.POST.get("age") or None,
                gender=request.POST.get("gender", ""),
                attendance=float(request.POST.get("attendance") or 0),
                study_hours=float(request.POST.get("study_hours") or 0),
                assignment_score=float(request.POST.get("assignment_score") or 0),
                quiz_score=float(request.POST.get("quiz_score") or 0),
                previous_marks=float(request.POST.get("previous_marks") or 0),
            )

            # Auto-enroll in all existing subjects with initial 0 marks
            for sub in subjects:
                sub_mark_val = request.POST.get(f"subject_{sub.id}")
                marks_val = float(sub_mark_val) if sub_mark_val not in (None, "") else 0.0
                StudentSubjectMark.objects.create(
                    student=student,
                    subject=sub,
                    marks_obtained=marks_val
                )

            student.calculate_totals()
            messages.success(request, f"Student '{name}' added successfully!")
            return redirect("students")

    return render(
        request,
        "chatbot/add_student.html",
        {
            "subjects": subjects,
            "error": error,
            "user_role": get_user_role(request.user),
        }
    )


@admin_required
def edit_student(request, id):
    """Admin-only view to update a student's personal info."""
    student = get_object_or_404(Student, id=id)
    error = None

    if request.method == "POST":
        student_id = request.POST.get("student_id", "").strip()
        name = request.POST.get("name", "").strip()

        if not student_id or not name:
            error = "Student ID and Name are required."
        elif Student.objects.filter(student_id=student_id).exclude(id=student.id).exists():
            error = f"Student ID '{student_id}' is already in use by another student."
        else:
            student.student_id = student_id
            student.name = name
            student.email = request.POST.get("email", "").strip()
            student.father_name = request.POST.get("father_name", "").strip()
            student.phone = request.POST.get("phone", "").strip()
            student.age = request.POST.get("age") or None
            student.gender = request.POST.get("gender", "")
            student.attendance = float(request.POST.get("attendance") or 0)
            student.study_hours = float(request.POST.get("study_hours") or 0)
            student.assignment_score = float(request.POST.get("assignment_score") or 0)
            student.quiz_score = float(request.POST.get("quiz_score") or 0)
            student.previous_marks = float(request.POST.get("previous_marks") or 0)
            student.save()

            messages.success(request, f"Student '{student.name}' updated successfully!")
            return redirect("students")

    return render(
        request,
        "chatbot/edit_student.html",
        {
            "student": student,
            "error": error,
            "user_role": get_user_role(request.user),
        }
    )


@admin_required
def delete_student(request, id):
    """Admin-only view to delete a student."""
    student = get_object_or_404(Student, id=id)
    name = student.name
    student.delete()
    messages.success(request, f"Student '{name}' has been deleted.")
    return redirect("students")


# ==============================================================================
# Subject & Marks Management (Teachers & Admins)
# ==============================================================================

@teacher_or_admin_required
def manage_marks(request, student_id=None):
    """Add, view, and update marks across multiple subjects with auto-total calculation."""
    students = Student.objects.all().order_by("name")
    subjects = Subject.objects.all().order_by("name")

    selected_student = None
    if student_id:
        selected_student = get_object_or_404(Student, id=student_id)
    elif request.GET.get("student_id"):
        selected_student = Student.objects.filter(id=request.GET.get("student_id")).first()

    if not selected_student and students.exists():
        selected_student = students.first()

    # Ensure subject mark records exist for all subjects for the selected student
    student_subject_marks = []
    if selected_student:
        for sub in subjects:
            sm, _ = StudentSubjectMark.objects.get_or_create(
                student=selected_student,
                subject=sub,
                defaults={"marks_obtained": 0}
            )
            student_subject_marks.append(sm)

    if request.method == "POST" and selected_student:
        for sub in subjects:
            mark_key = f"mark_{sub.id}"
            remarks_key = f"remarks_{sub.id}"
            if mark_key in request.POST:
                try:
                    val = float(request.POST.get(mark_key) or 0)
                    val = max(0, min(val, sub.max_marks))  # Clamp between 0 and max_marks
                    remarks = request.POST.get(remarks_key, "").strip()

                    sm, _ = StudentSubjectMark.objects.get_or_create(
                        student=selected_student,
                        subject=sub
                    )
                    sm.marks_obtained = val
                    sm.remarks = remarks
                    sm.save()
                except ValueError:
                    pass

        # Trigger total recalculation
        selected_student.calculate_totals()
        messages.success(request, f"Marks updated and totals calculated for {selected_student.name}!")
        return redirect("student_marks", student_id=selected_student.id)

    return render(
        request,
        "chatbot/manage_marks.html",
        {
            "students": students,
            "subjects": subjects,
            "selected_student": selected_student,
            "student_subject_marks": student_subject_marks,
            "user_role": get_user_role(request.user),
            "is_admin": is_admin(request.user),
        }
    )


@teacher_or_admin_required
def add_subject(request):
    """Add a new curriculum subject."""
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        code = request.POST.get("code", "").strip()
        max_marks = float(request.POST.get("max_marks") or 100)
        pass_marks = float(request.POST.get("pass_marks") or 50)

        if name:
            if Subject.objects.filter(name__iexact=name).exists():
                messages.error(request, f"Subject '{name}' already exists.")
            else:
                Subject.objects.create(
                    name=name,
                    code=code,
                    max_marks=max_marks,
                    pass_marks=pass_marks
                )
                messages.success(request, f"Subject '{name}' created successfully!")
        return redirect("manage_marks")
    return redirect("manage_marks")


@admin_required
def delete_subject(request, id):
    """Admin-only deletion of a subject."""
    subject = get_object_or_404(Subject, id=id)
    name = subject.name
    subject.delete()
    # Recalculate totals for all students
    for s in Student.objects.all():
        s.calculate_totals()
    messages.success(request, f"Subject '{name}' deleted.")
    return redirect("manage_marks")


# ==============================================================================
# Analytics & Prediction
# ==============================================================================

@teacher_or_admin_required
def analysis(request):
    """Subject Performance & Overall Analytics with CSV Batch Analysis."""
    students = Student.objects.all()
    subjects = Subject.objects.all()

    # Calculate live DB statistics
    statistics = None
    marks_data = []
    attendance_data = []
    grade_data = {"A+": 0, "A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    pass_fail_data = {"Pass": 0, "Fail": 0}
    attendance_marks_data = []
    subject_performance_data = []
    table = None
    error = None

    if students.exists():
        total = students.count()
        avg_m = round(sum(s.marks for s in students) / total, 2)
        avg_att = round(sum(s.attendance for s in students) / total, 2)
        high_m = round(max(s.marks for s in students), 2)
        pass_cnt = students.filter(marks__gte=50).count()

        statistics = {
            "total_students": total,
            "average_marks": avg_m,
            "average_attendance": avg_att,
            "highest_marks": high_m,
        }

        marks_data = [s.marks for s in students]
        attendance_data = [s.attendance for s in students]
        attendance_marks_data = [{"attendance": s.attendance, "marks": s.marks, "name": s.name} for s in students]

        for s in students:
            g = s.grade or "F"
            grade_data[g] = grade_data.get(g, 0) + 1

        pass_fail_data = {
            "Pass": pass_cnt,
            "Fail": total - pass_cnt
        }

        for sub in subjects:
            sms = StudentSubjectMark.objects.filter(subject=sub)
            if sms.exists():
                s_avg = round(sms.aggregate(Avg("marks_obtained"))["marks_obtained__avg"] or 0, 2)
                s_max = round(sms.aggregate(Max("marks_obtained"))["marks_obtained__max"] or 0, 2)
                s_pass = sms.filter(marks_obtained__gte=sub.pass_marks).count()
                s_rate = round((s_pass / sms.count()) * 100, 2)
            else:
                s_avg, s_max, s_rate = 0, 0, 0
            subject_performance_data.append({
                "name": sub.name,
                "average": s_avg,
                "highest": s_max,
                "pass_rate": s_rate,
            })

    # Optional CSV upload batch analysis
    if request.method == "POST" and request.FILES.get("csv_file"):
        csv_file = request.FILES.get("csv_file")
        try:
            df = pd.read_csv(csv_file)
            statistics = {
                "total_students": len(df),
                "average_marks": round(df["marks"].mean(), 2) if "marks" in df else 0,
                "average_attendance": round(df["attendance"].mean(), 2) if "attendance" in df else 0,
                "highest_marks": round(df["marks"].max(), 2) if "marks" in df else 0,
            }
            if "marks" in df:
                marks_data = df["marks"].tolist()
                pass_count = (df["marks"] >= 50).sum()
                pass_fail_data = {"Pass": int(pass_count), "Fail": int(len(df) - pass_count)}
            if "attendance" in df:
                attendance_data = df["attendance"].tolist()
            if "grade" in df:
                grade_data = df["grade"].value_counts().to_dict()
            if "attendance" in df and "marks" in df:
                attendance_marks_data = df[["attendance", "marks"]].to_dict("records")

            table = df.head(10).to_html(classes="student-table", index=False)
            messages.success(request, "CSV dataset analyzed successfully!")
        except Exception as e:
            error = f"Error processing CSV: {str(e)}"

    return render(
        request,
        "chatbot/analysis.html",
        {
            "statistics": statistics,
            "table": table,
            "error": error,
            "marks_data": marks_data,
            "attendance_data": attendance_data,
            "grade_data": grade_data,
            "pass_fail_data": pass_fail_data,
            "attendance_marks_data": attendance_marks_data,
            "subject_performance_data": subject_performance_data,
            "user_role": get_user_role(request.user),
        }
    )


@teacher_or_admin_required
def prediction(request):
    """Predict student marks using trained Machine Learning model."""
    result = None
    performance = None
    selected_student = None
    students = Student.objects.all().order_by("name")

    if request.method == "POST":
        student_id = request.POST.get("student_id")
        attendance = float(request.POST.get("attendance") or 0)
        study_hours = float(request.POST.get("study_hours") or 0)
        assignment_score = float(request.POST.get("assignment_score") or 0)
        quiz_score = float(request.POST.get("quiz_score") or 0)
        previous_marks = float(request.POST.get("previous_marks") or 0)

        # Load trained ML model
        model_path = os.path.join(
            os.path.dirname(__file__),
            "ml",
            "student_performance_model.pkl"
        )

        try:
            if os.path.exists(model_path):
                model = joblib.load(model_path)
                input_data = [[attendance, study_hours, assignment_score, quiz_score, previous_marks]]
                predicted_marks = model.predict(input_data)[0]
                result = round(min(100, max(0, predicted_marks)), 2)
            else:
                # Rule-based fallback if pickle is missing
                result = round(0.3 * attendance + 0.25 * assignment_score + 0.25 * quiz_score + 0.2 * previous_marks, 2)

            if result >= 80:
                performance = "Excellent"
            elif result >= 70:
                performance = "Good"
            elif result >= 60:
                performance = "Average"
            else:
                performance = "Needs Improvement"

            if student_id:
                selected_student = Student.objects.filter(id=student_id).first()
                if selected_student:
                    selected_student.attendance = attendance
                    selected_student.study_hours = study_hours
                    selected_student.assignment_score = assignment_score
                    selected_student.quiz_score = quiz_score
                    selected_student.previous_marks = previous_marks
                    selected_student.predicted_marks = result
                    selected_student.performance_level = performance
                    selected_student.save()
                    messages.success(request, f"Prediction updated for {selected_student.name}!")
        except Exception as e:
            messages.error(request, f"Prediction error: {str(e)}")

    return render(
        request,
        "chatbot/prediction.html",
        {
            "result": result,
            "performance": performance,
            "students": students,
            "selected_student": selected_student,
            "user_role": get_user_role(request.user),
        }
    )


def get_student_data(request, id):
    """JSON API returning student data for auto-populating prediction forms."""
    student = get_object_or_404(Student, id=id)
    return JsonResponse({
        "name": student.name,
        "student_id": student.student_id,
        "attendance": student.attendance,
        "study_hours": student.study_hours,
        "assignment_score": student.assignment_score,
        "quiz_score": student.quiz_score,
        "previous_marks": student.previous_marks or student.marks,
        "marks": student.marks,
    })


# ==============================================================================
# PDF Reports
# ==============================================================================

@login_required
def reports(request):
    """Reports overview hub."""
    if is_student(request.user):
        return redirect("generate_student_report")

    students = Student.objects.all().order_by("name")
    return render(
        request,
        "chatbot/reports.html",
        {
            "students": students,
            "user_role": get_user_role(request.user),
            "is_admin": is_admin(request.user),
        }
    )


@login_required
def generate_student_report(request):
    """Generate a clean, professional Purple & White PDF Report Card for a student."""
    # If student user, enforce generating their own report card only
    if is_student(request.user):
        try:
            student = getattr(request.user, "student_profile", None)
        except Exception:
            student = None

        if not student:
            student = Student.objects.filter(
                Q(user=request.user) | Q(email=request.user.email) | Q(name=request.user.username)
            ).first()

        if not student:
            student = Student.objects.create(
                user=request.user,
                student_id=f"QA-{request.user.id:04d}",
                name=request.user.get_full_name() or request.user.username,
                email=request.user.email or f"{request.user.username}@qa.local",
                attendance=85.0,
                marks=0,
                total_marks=0,
                max_total_marks=100
            )

        # Ensure enrolled in subjects
        subjects = Subject.objects.all()
        if subjects.exists() and not student.subject_marks.exists():
            for sub in subjects:
                StudentSubjectMark.objects.get_or_create(student=student, subject=sub, defaults={"marks_obtained": 0.0})
            student.calculate_totals()
    else:
        student_id = request.GET.get("student_id")
        if not student_id:
            messages.error(request, "Please select a student to generate the report.")
            return redirect("reports")
        student = get_object_or_404(Student, id=student_id)


    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="QA_Report_{student.student_id}.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    # Custom styles
    brand_style = ParagraphStyle(
        "BrandHeader",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=26,
        leading=30,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#6d28d9"),
        spaceAfter=4
    )

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=15,
        leading=18,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1e1b4b"),
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=10,
        textColor=colors.HexColor("#6b7280"),
        spaceAfter=16
    )

    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#5b21b6"),
        spaceBefore=14,
        spaceAfter=8
    )

    body_style = ParagraphStyle(
        "TableBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#1f2937")
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontSize=10,
        leading=12,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        alignment=TA_CENTER
    )

    story = []

    # 1. Header Banner
    story.append(Paragraph("QA ACADEMIC SUITE", brand_style))
    story.append(Paragraph("OFFICIAL STUDENT PERFORMANCE REPORT CARD", title_style))
    story.append(Paragraph("Quality Academics &bull; Advanced Academic Performance Evaluation", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#7c3aed"), spaceAfter=15))

    # 2. Student Info Card
    student_info_data = [
        [
            Paragraph("<b>Student Name:</b>", body_style), Paragraph(student.name, body_style),
            Paragraph("<b>Student ID:</b>", body_style), Paragraph(student.student_id, body_style),
        ],
        [
            Paragraph("<b>Father's Name:</b>", body_style), Paragraph(student.father_name or "N/A", body_style),
            Paragraph("<b>Email:</b>", body_style), Paragraph(student.email or "N/A", body_style),
        ],
        [
            Paragraph("<b>Phone:</b>", body_style), Paragraph(student.phone or "N/A", body_style),
            Paragraph("<b>Attendance:</b>", body_style), Paragraph(f"<b>{student.attendance}%</b>", body_style),
        ],
    ]

    info_table = Table(student_info_data, colWidths=[90, 165, 80, 175])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f3ff")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#ddd6fe")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ede9fe")),
        ("PADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 12))

    # 3. Subject-wise Marks Breakdown Table
    story.append(Paragraph("Subject-Wise Academic Performance", heading_style))

    subject_marks = student.subject_marks.select_related("subject").all()
    sub_table_data = [
        [
            Paragraph("Code", table_header_style),
            Paragraph("Subject Name", table_header_style),
            Paragraph("Max Marks", table_header_style),
            Paragraph("Marks Obtained", table_header_style),
            Paragraph("Grade", table_header_style),
            Paragraph("Status", table_header_style),
        ]
    ]

    if subject_marks.exists():
        for sm in subject_marks:
            status_color = "#16a34a" if sm.is_passed else "#dc2626"
            status_text = "PASS" if sm.is_passed else "FAIL"
            sub_table_data.append([
                Paragraph(sm.subject.code or "-", body_style),
                Paragraph(sm.subject.name, body_style),
                Paragraph(str(int(sm.subject.max_marks)), body_style),
                Paragraph(f"<b>{sm.marks_obtained}</b>", body_style),
                Paragraph(f"<b>{sm.grade}</b>", body_style),
                Paragraph(f"<font color='{status_color}'><b>{status_text}</b></font>", body_style),
            ])
    else:
        # Fallback if single mark
        sub_table_data.append([
            Paragraph("GEN", body_style),
            Paragraph("General Performance", body_style),
            Paragraph("100", body_style),
            Paragraph(str(student.marks), body_style),
            Paragraph(student.grade or "N/A", body_style),
            Paragraph("<font color='#16a34a'>PASS</font>" if student.marks >= 50 else "<font color='#dc2626'>FAIL</font>", body_style),
        ])

    sub_table = Table(sub_table_data, colWidths=[65, 175, 75, 95, 50, 50])
    sub_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6d28d9")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (1, 1), (1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#faf5ff")]),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(sub_table)
    story.append(Spacer(1, 12))

    # 4. Overall Result Summary
    story.append(Paragraph("Overall Result Summary", heading_style))

    total_obtained = student.total_marks if student.total_marks > 0 else student.marks
    max_total = student.max_total_marks if student.max_total_marks > 0 else 100

    summary_data = [
        [
            Paragraph("<b>Total Marks:</b>", body_style),
            Paragraph(f"<b>{total_obtained} / {max_total}</b>", body_style),
            Paragraph("<b>Overall Percentage:</b>", body_style),
            Paragraph(f"<b>{student.marks}%</b>", body_style),
        ],
        [
            Paragraph("<b>Overall Grade:</b>", body_style),
            Paragraph(f"<b><font color='#6d28d9' size=12>{student.grade or 'N/A'}</font></b>", body_style),
            Paragraph("<b>Academic Standing:</b>", body_style),
            Paragraph(
                "<font color='#16a34a'><b>PASSED</b></font>" if student.marks >= 50 else "<font color='#dc2626'><b>NEEDS ATTENTION</b></font>",
                body_style
            ),
        ],
        [
            Paragraph("<b>Predicted Score (AI):</b>", body_style),
            Paragraph(f"<b>{student.predicted_marks or 'N/A'}</b>", body_style),
            Paragraph("<b>Performance Level:</b>", body_style),
            Paragraph(f"<b>{student.performance_level or 'N/A'}</b>", body_style),
        ],
    ]

    summary_table = Table(summary_data, colWidths=[120, 135, 125, 130])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#7c3aed")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("PADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 25))

    # 5. Signatures & Footer
    footer_text = Paragraph(
        "<i>This is a computer-generated performance document verified by QA Academic Suite.</i>",
        subtitle_style
    )
    story.append(footer_text)

    doc.build(story)
    return response


@teacher_or_admin_required
def generate_class_report(request):
    """Generate Class Performance Summary PDF."""
    students = Student.objects.all().order_by("-marks")
    subjects = Subject.objects.all()

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="QA_Class_Performance_Report.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=35,
        leftMargin=35,
        topMargin=35,
        bottomMargin=35
    )

    styles = getSampleStyleSheet()

    brand_style = ParagraphStyle(
        "BrandHeader",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=24,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#6d28d9"),
        spaceAfter=4
    )

    title_style = ParagraphStyle(
        "ClassTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=15,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1e1b4b"),
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        "ClassSubtitle",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=10,
        textColor=colors.HexColor("#6b7280"),
        spaceAfter=14
    )

    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=12,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#5b21b6"),
        spaceBefore=10,
        spaceAfter=6
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontSize=9,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        alignment=TA_CENTER
    )

    body_style = ParagraphStyle(
        "TableBody",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#1f2937")
    )

    story = []

    story.append(Paragraph("QA ACADEMIC SUITE", brand_style))
    story.append(Paragraph("CLASS PERFORMANCE & RANKING REPORT", title_style))
    story.append(Paragraph("Comprehensive Class Analytics & Evaluation Summary", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#7c3aed"), spaceAfter=12))

    total = students.count()
    if total > 0:
        avg_m = round(sum(s.marks for s in students) / total, 2)
        avg_att = round(sum(s.attendance for s in students) / total, 2)
        high_m = round(max(s.marks for s in students), 2)
        pass_cnt = students.filter(marks__gte=50).count()
        pass_pct = round((pass_cnt / total) * 100, 2)
    else:
        avg_m, avg_att, high_m, pass_pct = 0, 0, 0, 0

    # Summary Stats
    summary_data = [
        ["Total Students", str(total), "Average Score", f"{avg_m}%"],
        ["Average Attendance", f"{avg_att}%", "Highest Score", f"{high_m}%"],
        ["Passing Rate", f"{pass_pct}%", "Curriculum Subjects", str(subjects.count())],
    ]

    sum_table = Table(summary_data, colWidths=[120, 135, 125, 130])
    sum_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f3ff")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#ddd6fe")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ede9fe")),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
    ]))
    story.append(sum_table)
    story.append(Spacer(1, 14))

    # Student Ranking Table
    story.append(Paragraph("Student Performance Roster", heading_style))

    table_data = [
        [
            Paragraph("Rank", table_header_style),
            Paragraph("Student ID", table_header_style),
            Paragraph("Name", table_header_style),
            Paragraph("Attendance", table_header_style),
            Paragraph("Total Marks", table_header_style),
            Paragraph("Percentage", table_header_style),
            Paragraph("Grade", table_header_style),
        ]
    ]

    for rank, s in enumerate(students, 1):
        table_data.append([
            Paragraph(f"#{rank}", body_style),
            Paragraph(s.student_id, body_style),
            Paragraph(s.name, body_style),
            Paragraph(f"{s.attendance}%", body_style),
            Paragraph(str(s.total_marks), body_style),
            Paragraph(f"{s.marks}%", body_style),
            Paragraph(f"<b>{s.grade or 'N/A'}</b>", body_style),
        ])

    student_table = Table(table_data, colWidths=[40, 85, 160, 75, 75, 75, 40], repeatRows=1)
    student_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6d28d9")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (2, 1), (2, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#faf5ff")]),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(student_table)
    story.append(Spacer(1, 20))

    story.append(Paragraph("<i>Generated by QA Academic Performance & Analysis System.</i>", subtitle_style))

    doc.build(story)
    return response
