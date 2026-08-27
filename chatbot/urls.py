from django.urls import path
from . import views

urlpatterns = [
    # Public & Auth
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register, name="register"),
    path("logout/", views.logout_user, name="logout"),
    path("chat/", views.chat_api, name="chat_api"),
    path("admin/create-staff/", views.create_staff_account, name="create_staff"),

    # Dashboards
    path("dashboard/", views.dashboard, name="dashboard"),
    path("my-portal/", views.student_portal, name="student_portal"),

    # Student Management
    path("students/", views.students, name="students"),
    path("students/add/", views.add_student, name="add_student"),
    path("students/<int:id>/", views.student_detail, name="student_detail"),
    path("students/edit/<int:id>/", views.edit_student, name="edit_student"),
    path("students/delete/<int:id>/", views.delete_student, name="delete_student"),
    path("student-data/<int:id>/", views.get_student_data, name="get_student_data"),

    # Subjects & Marks Management
    path("marks/", views.manage_marks, name="manage_marks"),
    path("marks/<int:student_id>/", views.manage_marks, name="student_marks"),
    path("subjects/add/", views.add_subject, name="add_subject"),
    path("subjects/delete/<int:id>/", views.delete_subject, name="delete_subject"),

    # Analytics & Prediction
    path("analysis/", views.analysis, name="analysis"),
    path("prediction/", views.prediction, name="prediction"),

    # Reports
    path("reports/", views.reports, name="reports"),
    path("reports/student/", views.generate_student_report, name="generate_student_report"),
    path("reports/class/", views.generate_class_report, name="generate_class_report"),
]