from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('translation', '0008_imagetranslation_original_image_url_and_more'),
    ]

    operations = [
        # original_text is not used for document translations; make it nullable
        migrations.AlterField(
            model_name='texttranslation',
            name='original_text',
            field=models.TextField(blank=True, null=True),
        ),
        # Increase max_length so long local /media/cloud_local/... URLs are not truncated
        migrations.AlterField(
            model_name='texttranslation',
            name='original_file_url',
            field=models.URLField(blank=True, null=True, max_length=1000),
        ),
        migrations.AlterField(
            model_name='texttranslation',
            name='translated_file_url',
            field=models.URLField(blank=True, null=True, max_length=1000),
        ),
    ]
