from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, blank=True)
    max_marks = models.FloatField(default=100)
    pass_marks = models.FloatField(default=50)

    def __str__(self):
        if self.code:
            return f"{self.code} - {self.name}"
        return self.name

    def save(self, *args, **kwargs):
        if not self.code and self.name:
            self.code = "".join([w[:3].upper() for w in self.name.split()[:2]])
        super().save(*args, **kwargs)


class Student(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_profile"
    )
    student_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    father_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    attendance = models.FloatField(default=0)
    marks = models.FloatField(default=0)  # Percentage / overall score
    total_marks = models.FloatField(default=0)  # Sum of marks obtained
    max_total_marks = models.FloatField(default=0)  # Sum of max marks
    grade = models.CharField(max_length=5, blank=True)
    predicted_marks = models.FloatField(null=True, blank=True)
    performance_level = models.CharField(max_length=30, blank=True)

    # Prediction features
    study_hours = models.FloatField(default=0)
    assignment_score = models.FloatField(default=0)
    quiz_score = models.FloatField(default=0)
    previous_marks = models.FloatField(default=0)

    def __str__(self):
        return f"{self.student_id} - {self.name}"

    def calculate_totals(self):
        """Calculate total marks, percentage, and grade from enrolled subjects."""
        marks_qs = self.subject_marks.all()
        if marks_qs.exists():
            obtained = sum(m.marks_obtained for m in marks_qs)
            maximum = sum(m.subject.max_marks for m in marks_qs)
            self.total_marks = round(obtained, 2)
            self.max_total_marks = round(maximum, 2)
            if maximum > 0:
                self.marks = round((obtained / maximum) * 100, 2)
            else:
                self.marks = 0
        else:
            self.total_marks = self.marks
            self.max_total_marks = 100

        # Assign Grade based on percentage (self.marks)
        pct = self.marks
        if pct >= 90:
            self.grade = "A+"
        elif pct >= 80:
            self.grade = "A"
        elif pct >= 70:
            self.grade = "B"
        elif pct >= 60:
            self.grade = "C"
        elif pct >= 50:
            self.grade = "D"
        else:
            self.grade = "F"

        super().save(update_fields=["total_marks", "max_total_marks", "marks", "grade"])


class StudentSubjectMark(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="subject_marks"
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="student_marks"
    )
    marks_obtained = models.FloatField(default=0)
    grade = models.CharField(max_length=5, blank=True)
    remarks = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ("student", "subject")

    def __str__(self):
        return f"{self.student.name} - {self.subject.name}: {self.marks_obtained}"

    def calculate_grade(self):
        max_m = self.subject.max_marks if self.subject and self.subject.max_marks > 0 else 100
        pct = (self.marks_obtained / max_m) * 100
        if pct >= 90:
            return "A+"
        elif pct >= 80:
            return "A"
        elif pct >= 70:
            return "B"
        elif pct >= 60:
            return "C"
        elif pct >= 50:
            return "D"
        return "F"

    @property
    def is_passed(self):
        pass_m = self.subject.pass_marks if self.subject else 50
        return self.marks_obtained >= pass_m

    def save(self, *args, **kwargs):
        self.grade = self.calculate_grade()
        super().save(*args, **kwargs)
        # Update student totals automatically
        self.student.calculate_totals()


class Profile(models.Model):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("teacher", "Teacher"),
        ("student", "Student"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="student"
    )

    def __str__(self):
        return f"{self.user.username} - {self.role}"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
    else:
        if hasattr(instance, "profile"):
            instance.profile.save()