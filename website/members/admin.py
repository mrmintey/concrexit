"""
This module registers admin pages for the models
"""
import datetime

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm
from django.utils.translation import ugettext_lazy as _

from . import models, forms


class MembershipInline(admin.StackedInline):
    model = models.Membership
    extra = 1


class MemberInline(admin.StackedInline):
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


class UserCreationForm(BaseUserCreationForm):
    class Meta(BaseUserCreationForm.Meta):
        fields = ('username', 'first_name', 'last_name')


class UserAdmin(BaseUserAdmin):
    add_form = forms.UserCreationForm

    inlines = (MemberInline, MembershipInline)
    # FIXME include proper filter for expiration
    # https://docs.djangoproject.com/en/1.9/ref/contrib/admin/#django.contrib.admin.ModelAdmin.list_filter
    list_filter = (MembershipTypeListFilter,
                   'is_superuser',
                   AgeListFilter,)

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'username', 'email',
                       'send_welcome_email')
        }),
    )

admin.site.register(models.BecomeAMemberDocument)

# re-register User admin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
