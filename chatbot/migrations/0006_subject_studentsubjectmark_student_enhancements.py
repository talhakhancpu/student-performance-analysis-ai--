import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def add_missing_columns_0006(apps, schema_editor):
    from django.db import connection
    with connection.cursor() as cur:
        # 1. Ensure Subject table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chatbot_subject (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL UNIQUE,
                code VARCHAR(20) NOT NULL UNIQUE,
                max_marks REAL NOT NULL DEFAULT 100,
                pass_marks REAL NOT NULL DEFAULT 50
            );
        """)

        # 2. Ensure StudentSubjectMark table
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

        # 3. Check and add columns to chatbot_student
        cur.execute("PRAGMA table_info(chatbot_student);")
        existing_cols = [row[1] for row in cur.fetchall()]

        if "total_marks" not in existing_cols:
            cur.execute("ALTER TABLE chatbot_student ADD COLUMN total_marks REAL NOT NULL DEFAULT 0;")
        if "max_total_marks" not in existing_cols:
            cur.execute("ALTER TABLE chatbot_student ADD COLUMN max_total_marks REAL NOT NULL DEFAULT 0;")
        if "user_id" not in existing_cols:
            cur.execute("ALTER TABLE chatbot_student ADD COLUMN user_id INTEGER REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED;")


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0005_profile'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='Subject',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('name', models.CharField(max_length=100, unique=True)),
                        ('code', models.CharField(blank=True, max_length=20, unique=True)),
                        ('max_marks', models.FloatField(default=100)),
                        ('pass_marks', models.FloatField(default=50)),
                    ],
                ),
                migrations.AddField(
                    model_name='student',
                    name='max_total_marks',
                    field=models.FloatField(default=0),
                ),
                migrations.AddField(
                    model_name='student',
                    name='total_marks',
                    field=models.FloatField(default=0),
                ),
                migrations.AddField(
                    model_name='student',
                    name='user',
                    field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='student_profile', to=settings.AUTH_USER_MODEL),
                ),
                migrations.AlterField(
                    model_name='profile',
                    name='user',
                    field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL),
                ),
                migrations.CreateModel(
                    name='StudentSubjectMark',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('marks_obtained', models.FloatField(default=0)),
                        ('grade', models.CharField(blank=True, max_length=5)),
                        ('remarks', models.CharField(blank=True, max_length=100)),
                        ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subject_marks', to='chatbot.student')),
                        ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='student_marks', to='chatbot.subject')),
                    ],
                    options={
                        'unique_together': {('student', 'subject')},
                    },
                ),
            ],
            database_operations=[
                migrations.RunPython(add_missing_columns_0006, reverse_code=migrations.RunPython.noop),
            ],
        ),
    ]
