from django.apps import AppConfig
from django.db.models.signals import post_migrate


def seed_initial_data(sender, **kwargs):
    """Seed initial realistic student data and default demo accounts once migrations complete."""
    try:
        from django.db import connection
        with connection.cursor() as cur:
            # 1. Ensure columns in chatbot_student
            cur.execute("PRAGMA table_info(chatbot_student);")
            existing_cols = [row[1] for row in cur.fetchall()]

            if "total_marks" not in existing_cols:
                cur.execute("ALTER TABLE chatbot_student ADD COLUMN total_marks REAL NOT NULL DEFAULT 0;")
            if "max_total_marks" not in existing_cols:
                cur.execute("ALTER TABLE chatbot_student ADD COLUMN max_total_marks REAL NOT NULL DEFAULT 0;")
            if "user_id" not in existing_cols:
                cur.execute("ALTER TABLE chatbot_student ADD COLUMN user_id INTEGER REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED;")
    except Exception:
        pass

    try:
        from chatbot.models import Student, Subject, StudentSubjectMark, Profile
        from django.contrib.auth.models import User

        # Ensure default subjects
        sub_math, _ = Subject.objects.get_or_create(name="Mathematics", defaults={"code": "MATH-101", "max_marks": 100, "pass_marks": 50})
        sub_cs, _ = Subject.objects.get_or_create(name="Computer Science", defaults={"code": "CS-101", "max_marks": 100, "pass_marks": 50})
        sub_phy, _ = Subject.objects.get_or_create(name="Physics", defaults={"code": "PHY-101", "max_marks": 100, "pass_marks": 50})
        sub_eng, _ = Subject.objects.get_or_create(name="English", defaults={"code": "ENG-101", "max_marks": 100, "pass_marks": 50})
        sub_ds, _ = Subject.objects.get_or_create(name="Data Science", defaults={"code": "DS-101", "max_marks": 100, "pass_marks": 50})

        # Ensure demo users
        # 1. Admin
        admin_user, created_admin = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@qa.edu", "is_staff": True, "is_superuser": True}
        )
        if created_admin:
            admin_user.set_password("admin123")
            admin_user.save()
        admin_prof, _ = Profile.objects.get_or_create(user=admin_user)
        admin_prof.role = "admin"
        admin_prof.save()

        # 2. Teacher
        teacher_user, created_teacher = User.objects.get_or_create(
            username="teacher",
            defaults={"email": "teacher@qa.edu", "is_staff": False}
        )
        if created_teacher:
            teacher_user.set_password("teacher123")
            teacher_user.save()
        teacher_prof, _ = Profile.objects.get_or_create(user=teacher_user)
        teacher_prof.role = "teacher"
        teacher_prof.save()

        # 3. Student (Sarah)
        sarah_user, created_sarah = User.objects.get_or_create(
            username="sarah",
            defaults={"email": "sarah.ahmed@qa.edu"}
        )
        if created_sarah:
            sarah_user.set_password("student123")
            sarah_user.save()
        sarah_prof, _ = Profile.objects.get_or_create(user=sarah_user)
        sarah_prof.role = "student"
        sarah_prof.save()

        # Seed sample students if database has fewer than 4 students
        sample_students = [
            {
                "user": sarah_user,
                "student_id": "QA-1001",
                "name": "Sarah Ahmed",
                "email": "sarah.ahmed@qa.edu",
                "father_name": "Tariq Ahmed",
                "phone": "+92 301 5551234",
                "age": 19,
                "gender": "Female",
                "attendance": 96.5,
                "study_hours": 6.0,
                "assignment_score": 95.0,
                "quiz_score": 92.0,
                "previous_marks": 90.0,
                "marks_dict": {sub_math: 94.0, sub_cs: 98.0, sub_phy: 91.0, sub_eng: 89.0, sub_ds: 96.0}
            },
            {
                "user": None,
                "student_id": "QA-1002",
                "name": "Bilal Khan",
                "email": "bilal.khan@qa.edu",
                "father_name": "Rashid Khan",
                "phone": "+92 302 5552345",
                "age": 20,
                "gender": "Male",
                "attendance": 88.0,
                "study_hours": 4.5,
                "assignment_score": 86.0,
                "quiz_score": 84.0,
                "previous_marks": 82.0,
                "marks_dict": {sub_math: 85.0, sub_cs: 89.0, sub_phy: 81.0, sub_eng: 79.0, sub_ds: 86.0}
            },
            {
                "user": None,
                "student_id": "QA-1003",
                "name": "Ayesha Malik",
                "email": "ayesha.malik@qa.edu",
                "father_name": "Zafar Malik",
                "phone": "+92 303 5553456",
                "age": 19,
                "gender": "Female",
                "attendance": 81.5,
                "study_hours": 3.5,
                "assignment_score": 78.0,
                "quiz_score": 75.0,
                "previous_marks": 73.0,
                "marks_dict": {sub_math: 72.0, sub_cs: 78.0, sub_phy: 70.0, sub_eng: 82.0, sub_ds: 74.0}
            },
            {
                "user": None,
                "student_id": "QA-1004",
                "name": "Hamza Tariq",
                "email": "hamza.tariq@qa.edu",
                "father_name": "Tariq Mahmood",
                "phone": "+92 304 5554567",
                "age": 21,
                "gender": "Male",
                "attendance": 74.0,
                "study_hours": 2.5,
                "assignment_score": 68.0,
                "quiz_score": 65.0,
                "previous_marks": 63.0,
                "marks_dict": {sub_math: 62.0, sub_cs: 68.0, sub_phy: 58.0, sub_eng: 71.0, sub_ds: 64.0}
            },
            {
                "user": None,
                "student_id": "QA-1005",
                "name": "Zainab Raza",
                "email": "zainab.raza@qa.edu",
                "father_name": "Ali Raza",
                "phone": "+92 305 5555678",
                "age": 18,
                "gender": "Female",
                "attendance": 67.0,
                "study_hours": 2.0,
                "assignment_score": 56.0,
                "quiz_score": 54.0,
                "previous_marks": 52.0,
                "marks_dict": {sub_math: 52.0, sub_cs: 56.0, sub_phy: 48.0, sub_eng: 62.0, sub_ds: 54.0}
            },
            {
                "user": None,
                "student_id": "QA-1006",
                "name": "Usman Farooq",
                "email": "usman.farooq@qa.edu",
                "father_name": "Farooq Azam",
                "phone": "+92 306 5556789",
                "age": 20,
                "gender": "Male",
                "attendance": 92.0,
                "study_hours": 5.2,
                "assignment_score": 90.0,
                "quiz_score": 88.0,
                "previous_marks": 87.0,
                "marks_dict": {sub_math: 90.0, sub_cs: 93.0, sub_phy: 87.0, sub_eng: 85.0, sub_ds: 91.0}
            },
        ]

        if Student.objects.count() < 4:
            for s_data in sample_students:
                marks_dict = s_data.pop("marks_dict")
                student, _ = Student.objects.update_or_create(
                    student_id=s_data["student_id"],
                    defaults=s_data
                )
                for sub, mark_val in marks_dict.items():
                    sm, _ = StudentSubjectMark.objects.get_or_create(
                        student=student,
                        subject=sub
                    )
                    sm.marks_obtained = mark_val
                    sm.remarks = "Satisfactory" if mark_val >= 50 else "Needs Improvement"
                    sm.save()
                student.calculate_totals()
    except Exception:
        pass


class ChatbotConfig(AppConfig):
    name = 'chatbot'

    def ready(self):
        post_migrate.connect(seed_initial_data, sender=self)
