# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-10-11 18:50
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def forward_func(apps, schema_editor):
    CommitteeMembership = apps.get_model('activemembers', 'CommitteeMembership')
    Mentorship = apps.get_model('activemembers', 'Mentorship')

    for membership in CommitteeMembership.objects.all():
        membership.member_old = membership.member
        membership.save(update_fields=('member_old',))

    for mentorship in Mentorship.objects.all():
        mentorship.member_old = mentorship.member
        mentorship.save(update_fields=('member_old',))


class Migration(migrations.Migration):

    dependencies = [
        ('activemembers', '0022_0_user_foreign_keys'),
    ]

    operations = [
        migrations.RunPython(
            code=forward_func,
        ),
    ]
