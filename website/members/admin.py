"""
This module registers admin pages for the models
"""
import datetime

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.http import HttpResponse
import csv

from . import forms, models


class MembershipInline(admin.StackedInline):
    model = models.Membership
    extra = 0


class MemberInline(admin.StackedInline):
    fields = ('starting_year', 'programme', 'address_street',
              'address_street2', 'address_postal_code', 'address_city',
              'student_number', 'phone_number', 'receive_optin',
              'receive_newsletter', 'birthday', 'show_birthday',
              'direct_debit_authorized', 'bank_account', 'initials',
              'nickname', 'display_name_preference', 'profile_description',
              'website', 'photo', 'emergency_contact',
              'emergency_contact_phone_number', 'language',
              'event_permissions')
    model = models.Member
    can_delete = False


class MembershipTypeListFilter(admin.SimpleListFilter):
    title = _('membership type')
    parameter_name = 'membership'

    def lookups(self, request, model_admin):
        return models.Membership.MEMBERSHIP_TYPES

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        queryset.prefetch_related('user__memberships')
        users = set()
        for user in queryset:
            try:
                if user.member.current_membership:
                    if user.member.current_membership.type == self.value():
                        users.add(user.pk)
            except models.Member.DoesNotExist:
                # The superuser does not have a .member object attached.
                pass
        return queryset.filter(pk__in=users)


class AgeListFilter(admin.SimpleListFilter):
    title = _('Age')
    parameter_name = 'birthday'

    def lookups(self, request, model_admin):
        return (
            ('18+', _('≥ 18')),
            ('18-', _('< 18')),
            ('unknown', _('Unknown')),
        )

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        users = set()
        for user in queryset:
            try:
                today = datetime.date.today()
                eightteen_years_ago = today.replace(year=today.year - 18)
                if user.member.birthday is None:
                    if self.value() == 'unknown':
                        users.add(user.pk)
                    continue
                elif (user.member.birthday <= eightteen_years_ago and
                      self.value() == '18+'):
                    users.add(user.pk)
                elif (user.member.birthday > eightteen_years_ago and
                      self.value() == '18-'):
                    users.add(user.pk)
            except models.Member.DoesNotExist:
                # The superuser does not have a .member object attached.
                pass
        return queryset.filter(pk__in=users)


class UserAdmin(BaseUserAdmin):
    form = forms.UserChangeForm
    add_form = forms.UserCreationForm

    actions = ['address_csv_export', 'student_number_csv_export']

    inlines = (MemberInline, MembershipInline)
    # FIXME include proper filter for expiration
    # https://docs.djangoproject.com/en/1.9/ref/contrib/admin/#django.contrib.admin.ModelAdmin.list_filter
    list_filter = (MembershipTypeListFilter,
                   'is_superuser',
                   AgeListFilter,
                   'member__event_permissions',)

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'username', 'email',
                       'send_welcome_email')
        }),
    )

    def address_csv_export(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment;\
                                           filename="addresses.csv"'
        writer = csv.writer(response)
        writer.writerow([_('First name'), _('Last name'), _('Address'),
                         _('Address line 2'), _('Postal code'), _('City')])
        for user in queryset.exclude(member=None):
            writer.writerow([user.first_name,
                             user.last_name,
                             user.member.address_street,
                             user.member.address_street2,
                             user.member.address_postal_code,
                             user.member.address_city,
                             ])
        return response
    address_csv_export.short_description = _('Download address label for '
                                             'selected users')

    def student_number_csv_export(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment;\
                                           filename="student_numbers.csv"'
        writer = csv.writer(response)
        writer.writerow([_('First name'), _('Last name'), _('Student number')])
        for user in queryset.exclude(member=None):
            writer.writerow([user.first_name,
                             user.last_name,
                             user.member.student_number
                             ])
        return response
    student_number_csv_export.short_description = _('Download student number '
                                                    'label for selected users')


admin.site.register(models.BecomeAMemberDocument)

# re-register User admin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
