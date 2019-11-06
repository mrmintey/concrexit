# Generated by Django 2.2.6 on 2019-11-06 18:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('newsletters', '0009_auto_20191103_1821'),
    ]

    operations = [
        migrations.AddField(
            model_name='newslettercontent',
            name='url',
            field=models.URLField(blank=True, help_text='If filled, it will make the title a link to this URL', null=True, verbose_name='URL'),
        ),
    ]
