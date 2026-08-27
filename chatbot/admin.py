from django.contrib import admin
from .models import Student, Subject, StudentSubjectMark, Profile


class StudentSubjectMarkInline(admin.TabularInline):
    model = StudentSubjectMark
    extra = 1


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("student_id", "name", "email", "attendance", "total_marks", "marks", "grade", "performance_level")
    search_fields = ("student_id", "name", "email")
    list_filter = ("grade", "performance_level", "gender")
    inlines = [StudentSubjectMarkInline]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "max_marks", "pass_marks")
    search_fields = ("code", "name")


@admin.register(StudentSubjectMark)
class StudentSubjectMarkAdmin(admin.ModelAdmin):
    list_display = ("student", "subject", "marks_obtained", "grade")
    list_filter = ("subject", "grade")
    search_fields = ("student__name", "student__student_id", "subject__name")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email")

