# Generated by Django 2.0.6 on 2018-07-11 17:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pushnotifications', '0010_rename_partner_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='url',
            field=models.CharField(max_length=256, null=True, blank=True, verbose_name='url'),
        ),
    ]
