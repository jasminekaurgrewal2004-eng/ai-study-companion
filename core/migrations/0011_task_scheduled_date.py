from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_add_reminder'),
    ]

    operations = [
        migrations.AddField(
            model_name='studyplantask',
            name='scheduled_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
