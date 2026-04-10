# Generated manually — expands ProjectTemplate.submission_type choices (no DB constraint change).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0003_studentprogresssnapshot_domain_weights'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projecttemplate',
            name='submission_type',
            field=models.CharField(
                choices=[
                    ('CODE', 'Code (repo / implementation)'),
                    ('DOCUMENT', 'Document (general written deliverable)'),
                    ('DESIGN', 'Design (visual / UX / creative)'),
                    ('PDF', 'PDF file'),
                    ('WORD', 'Word / DOCX'),
                    ('SPREADSHEET', 'Spreadsheet (e.g. Excel, Sheets)'),
                ],
                default='CODE',
                max_length=20,
            ),
        ),
    ]
