from collections import OrderedDict

from django.db.models import Q
from django.utils import timezone
from django.utils.datetime_safe import date
from django.utils.translation import gettext_lazy as _

from events import emails
from events.exceptions import RegistrationError
from events.models import EventRegistration, RegistrationInformationField, Event
from payments.api.v1.fields import PaymentTypeField
from payments.services import create_payment, delete_payment
from utils.snippets import datetime_to_lectureyear


def is_user_registered(member, event):
    """Return if the user is registered for the specified event.

    :param member: the user
    :param event: the event
    :return: None if registration is not required or no member else True/False
    """
    if not member.is_authenticated:
        return None

    return event.registrations.filter(member=member, date_cancelled=None).count() > 0


def user_registration_pending(member, event):
    """Return if the user is in the queue, but not yet registered for, the specific event.

    :param member: the user
    :param event: the event
    :return: None if registration is not required or no member else True/False
    """
    if not event.registration_required:
        return False
    if not member.is_authenticated:
        return None

    try:
        registration = event.registrations.get(member=member, date_cancelled=None)
        if registration.queue_position:
            return registration.queue_position
        return False
    except EventRegistration.DoesNotExist:
        return False


def is_user_present(member, event):
    if not event.registration_required or not member.is_authenticated:
        return None

    return (
        event.registrations.filter(
            member=member, date_cancelled=None, present=True
        ).count()
        > 0
    )


def event_permissions(member, event, name=None):
    """Return a dictionary with the available event permissions of the user.

    :param member: the user
    :param event: the event
    :param name: the name of a non member registration
    :return: the permission dictionary
    """
    perms = {
        "create_registration": False,
        "cancel_registration": False,
        "update_registration": False,
        "manage_event": is_organiser(member, event),
    }
    if not member:
        return perms
    if not (member.is_authenticated or name):
        return perms

    registration = None
    try:
        registration = EventRegistration.objects.get(
            event=event, member=member, name=name
        )
    except EventRegistration.DoesNotExist:
        pass

    perms["create_registration"] = (
        (registration is None or registration.date_cancelled is not None)
        and (
            event.registration_allowed
            or (event.optional_registration_allowed and not event.registration_required)
        )
        and (name or member.can_attend_events)
    )
    perms["cancel_registration"] = (
        registration is not None
        and registration.date_cancelled is None
        and (
            event.cancellation_allowed
            or name
            or (event.optional_registration_allowed and not event.registration_required)
        )
        and registration.payment is None
    )
    perms["update_registration"] = (
        registration is not None
        and registration.date_cancelled is None
        and event.has_fields
        and (
            event.registration_allowed
            or (event.optional_registration_allowed and not event.registration_required)
        )
        and (name or member.can_attend_events)
    )
    return perms


def is_organiser(member, event):
    if member and member.is_authenticated:
        if member.is_superuser or member.has_perm("events.override_organiser"):
            return True

        if event:
            return member.get_member_groups().filter(pk=event.organiser.pk).count() != 0

    return False


def create_registration(member, event):
    """Create a new user registration for an event.

    :param member: the user
    :param event: the event
    :return: Return the registration if successful
    """
    if event_permissions(member, event)["create_registration"]:
        registration = None
        try:
            registration = EventRegistration.objects.get(event=event, member=member)
        except EventRegistration.DoesNotExist:
            pass

        if registration is None:
            return EventRegistration.objects.create(event=event, member=member)
        if registration.date_cancelled is not None:
            if registration.is_late_cancellation():
                raise RegistrationError(
                    _(
                        "You cannot re-register anymore "
                        "since you've cancelled after the "
                        "deadline."
                    )
                )
            registration.date = timezone.now()
            registration.date_cancelled = None
            registration.save()

        return registration
    if event_permissions(member, event)["cancel_registration"]:
        raise RegistrationError(_("You were already registered."))
    raise RegistrationError(_("You may not register."))


def cancel_registration(member, event):
    """Cancel a user registration for an event.

    :param member: the user
    :param event: the event
    """
    registration = None
    try:
        registration = EventRegistration.objects.get(event=event, member=member)
    except EventRegistration.DoesNotExist:
        pass

    if event_permissions(member, event)["cancel_registration"] and registration:
        if not registration.queue_position:
            emails.notify_first_waiting(event)

            if event.send_cancel_email and event.after_cancel_deadline:
                emails.notify_organiser(event, registration)

        # Note that this doesn"t remove the values for the
        # information fields that the user entered upon registering.
        # But this is regarded as a feature, not a bug. Especially
        # since the values will still appear in the backend.
        registration.date_cancelled = timezone.now()
        registration.save()
    else:
        raise RegistrationError(_("You are not allowed to deregister for this event."))


def update_registration(
    member=None, event=None, name=None, registration=None, field_values=None, actor=None
):
    """Update a user registration of an event.

    :param member: the user
    :param event: the event
    :param name: the name of a registration not associated with a user
    :param registration: the registration
    :param field_values: values for the information fields
    :param actor: Member executing this action
    """
    if not registration:
        try:
            registration = EventRegistration.objects.get(
                event=event, member=member, name=name
            )
        except EventRegistration.DoesNotExist as error:
            raise RegistrationError(
                _("You are not registered for this event.")
            ) from error
    else:
        member = registration.member
        event = registration.event
        name = registration.name

    if not actor:
        actor = member

    permissions = event_permissions(actor, event, name)

    if not field_values:
        return
    if not (permissions["update_registration"] or permissions["manage_event"]):
        raise RegistrationError(_("You are not allowed to update this registration."))

    for field_id, field_value in field_values:
        field = RegistrationInformationField.objects.get(
            id=field_id.replace("info_field_", "")
        )

        if (
            field.type == RegistrationInformationField.INTEGER_FIELD
            and field_value is None
        ):
            field_value = 0
        elif (
            field.type == RegistrationInformationField.BOOLEAN_FIELD
            and field_value is None
        ):
            field_value = False
        elif (
            field.type == RegistrationInformationField.TEXT_FIELD
            and field_value is None
        ):
            field_value = ""

        field.set_value_for(registration, field_value)


def registration_fields(request, member=None, event=None, registration=None, name=None):
    """Return information about the registration fields of a registration.

    :param member: the user (optional if registration provided)
    :param name: the name of a non member registration
                 (optional if registration provided)
    :param event: the event (optional if registration provided)
    :param registration: the registration (optional if member & event provided)
    :return: the fields
    """
    if registration is None:
        try:
            registration = EventRegistration.objects.get(
                event=event, member=member, name=name
            )
        except EventRegistration.DoesNotExist as error:
            raise RegistrationError(
                _("You are not registered for this event.")
            ) from error
        except EventRegistration.MultipleObjectsReturned as error:
            raise RegistrationError(
                _("Unable to find the right registration.")
            ) from error

    member = registration.member
    event = registration.event
    name = registration.name

    perms = event_permissions(member, event, name)[
        "update_registration"
    ] or is_organiser(request.member, event)
    if perms and registration:
        information_fields = registration.information_fields
        fields = OrderedDict()

        for information_field in information_fields:
            field = information_field["field"]

            fields["info_field_{}".format(field.id)] = {
                "type": field.type,
                "label": field.name,
                "description": field.description,
                "value": information_field["value"],
                "required": field.required,
            }

        return fields
    raise RegistrationError(_("You are not allowed to update this registration."))


def update_registration_by_organiser(registration, member, data):
    if not is_organiser(member, registration.event):
        raise RegistrationError(_("You are not allowed to update this registration."))

    if "payment" in data:
        if data["payment"]["type"] == PaymentTypeField.NO_PAYMENT:
            if registration.payment is not None:
                delete_payment(registration, member)
        else:
            registration.payment = create_payment(
                model_payable=registration,
                processed_by=member,
                pay_type=data["payment"]["type"],
            )

    if "present" in data:
        registration.present = data["present"]

    registration.save()


def generate_category_statistics() -> dict:
    """Generate statistics about events per category."""
    current_year = datetime_to_lectureyear(timezone.now())

    data = {
        "labels": [str(current_year - 4 + i) for i in range(5)],
        "datasets": [
            {"label": str(display), "data": []} for _, display in Event.EVENT_CATEGORIES
        ],
    }

    for index, (key, _) in enumerate(Event.EVENT_CATEGORIES):
        for i in range(5):
            year_start = date(year=current_year - 4 + i, month=9, day=1)
            year_end = date(year=current_year - 3 + i, month=9, day=1)

            data["datasets"][index]["data"].append(
                Event.objects.filter(
                    category=key, start__gte=year_start, end__lte=year_end
                ).count()
            )

    return data


def execute_data_minimization(dry_run=False):
    """Delete information about very old events."""
    # Sometimes years are 366 days of course, but better delete 1 or 2 days early than late
    deletion_period = timezone.now().date() - timezone.timedelta(days=(365 * 5))

    queryset = EventRegistration.objects.filter(event__end__lte=deletion_period).filter(
        Q(payment__isnull=False) | Q(member__isnull=False) | ~Q(name__exact="<removed>")
    )
    if not dry_run:
        queryset.update(payment=None, member=None, name="<removed>")
    return queryset.all()
