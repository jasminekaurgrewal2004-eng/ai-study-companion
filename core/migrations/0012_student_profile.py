from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_task_scheduled_date'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(blank=True, default='', max_length=120)),
                ('phone', models.CharField(blank=True, default='', max_length=20)),
                ('institute', models.CharField(blank=True, default='', max_length=160)),
                ('grade_level', models.CharField(blank=True, default='', max_length=80)),
                ('target_exam', models.CharField(blank=True, default='', max_length=120)),
                ('bio', models.TextField(blank=True, default='')),
                ('daily_goal_hours', models.FloatField(default=2.0)),
                ('timezone', models.CharField(blank=True, default='', max_length=80)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='student_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
    ]
