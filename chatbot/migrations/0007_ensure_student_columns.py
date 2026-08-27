from django.db import migrations


def add_missing_student_columns(apps, schema_editor):
    from django.db import connection
    with connection.cursor() as cur:
        # Check existing columns in chatbot_student
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
        ('chatbot', '0006_subject_studentsubjectmark_student_enhancements'),
    ]

    operations = [
        migrations.RunPython(add_missing_student_columns, reverse_code=migrations.RunPython.noop),
    ]
