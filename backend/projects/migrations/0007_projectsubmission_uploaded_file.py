from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0006_studentprojectassignment_recommendation_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectsubmission',
            name='uploaded_file',
            field=models.FileField(
                blank=True,
                help_text='Required for document/design/spreadsheet uploads; not used for CODE.',
                null=True,
                upload_to='submissions/%Y/%m/',
            ),
        ),
    ]
