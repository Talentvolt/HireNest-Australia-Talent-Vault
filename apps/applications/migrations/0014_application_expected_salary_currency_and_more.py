# Generated migration for HireNest worldwide application fields.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0013_alter_application_screening_answers'),
    ]

    operations = [
        migrations.AddField(
            model_name='application',
            name='expected_salary_currency',
            field=models.CharField(blank=True, default='AUD', max_length=10),
        ),
        migrations.AddField(
            model_name='application',
            name='salary_period',
            field=models.CharField(blank=True, default='ANNUALLY', max_length=20),
        ),
    ]
