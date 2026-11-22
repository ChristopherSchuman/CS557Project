from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from .models import (
    PRIORITY_CHOICES,
    RESOLVED_STATUSES,
    ROLE_TECHNICIAN,
    STATUS_CHOICES,
    STATUS_OPEN,
    Category,
    StatusHistory,
    Ticket,
    TicketComment,
    User,
)


def visible_tickets(user):
    tickets = Ticket.objects.select_related("requester", "assigned_technician", "category")
    if user.role == ROLE_TECHNICIAN:
        return tickets
    return tickets.filter(requester=user)


@transaction.atomic
def open_ticket(*, requester, title, description, category, priority):
    ticket = Ticket(
        requester=requester,
        title=title,
        description=description,
        category=category,
        priority=priority,
        status=STATUS_OPEN,
    )
    ticket.full_clean()
    ticket.save()
    StatusHistory.objects.create(
        ticket=ticket,
        changed_by=requester,
        old_status="",
        new_status=STATUS_OPEN,
        note="Ticket opened.",
    )
    return ticket


@transaction.atomic
def update_ticket(
    *,
    ticket,
    editor,
    title,
    description,
    category,
    priority,
    status,
    assigned_technician,
    note,
):
    if editor.role != ROLE_TECHNICIAN:
        raise PermissionDenied("Only a technician can update a ticket.")

    # Read the stored status before applying edits. A bound ModelForm mutates
    # the same instance during validation, which would hide the change.
    previous_status = Ticket.objects.values_list("status", flat=True).get(pk=ticket.pk)
    ticket.title = title
    ticket.description = description
    ticket.category = category
    ticket.priority = priority
    ticket.status = status
    ticket.assigned_technician = assigned_technician
    ticket.full_clean()

    if status in RESOLVED_STATUSES:
        if ticket.resolved_at is None:
            ticket.resolved_at = timezone.now()
    elif previous_status in RESOLVED_STATUSES:
        ticket.resolved_at = None

    ticket.save()
    if previous_status != status:
        StatusHistory.objects.create(
            ticket=ticket,
            changed_by=editor,
            old_status=previous_status,
            new_status=status,
            note=note.strip() if note else "Status updated.",
        )
    return ticket


def add_comment(*, ticket, author, body):
    if author.role != ROLE_TECHNICIAN and ticket.requester_id != author.id:
        raise PermissionDenied("You can only comment on tickets you opened.")
    comment = TicketComment(ticket=ticket, author=author, body=body.strip())
    comment.full_clean()
    comment.save()
    return comment


def _with_percent(rows):
    total = sum(row["total"] for row in rows) or 0
    for row in rows:
        row["percent"] = round((row["total"] / total) * 100) if total else 0
    return rows


def ticket_kpis():
    counts = {
        row["status"]: row["total"]
        for row in Ticket.objects.values("status").annotate(total=Count("id"))
    }
    status_rows = _with_percent(
        [{"label": label, "total": counts.get(value, 0)} for value, label in STATUS_CHOICES]
    )
    priority_counts = {
        row["priority"]: row["total"]
        for row in Ticket.objects.values("priority").annotate(total=Count("id"))
    }
    priority_rows = _with_percent(
        [
            {"label": label, "total": priority_counts.get(value, 0)}
            for value, label in PRIORITY_CHOICES
        ]
    )
    category_rows = _with_percent(
        [
            {"label": row["name"], "total": row["total"]}
            for row in Category.objects.annotate(total=Count("tickets"))
            .values("name", "total")
            .order_by("id")
        ]
    )
    technician_rows = [
        {"label": row["username"], "total": row["total"]}
        for row in User.objects.filter(role=ROLE_TECHNICIAN, is_active=True)
        .annotate(total=Count("assigned_tickets"))
        .values("username", "total")
        .order_by("-total", "username")
    ]
    open_queue = Ticket.objects.filter(
        assigned_technician__isnull=True,
    ).exclude(status__in=RESOLVED_STATUSES)
    resolved_tickets = list(
        Ticket.objects.filter(resolved_at__isnull=False).only("created_at", "resolved_at")
    )
    average_hours = None
    if resolved_tickets:
        seconds = sum(
            (ticket.resolved_at - ticket.created_at).total_seconds()
            for ticket in resolved_tickets
        )
        average_hours = round(seconds / len(resolved_tickets) / 3600, 1)

    return {
        "total": Ticket.objects.count(),
        "open": counts.get("Open", 0),
        "in_progress": counts.get("In Progress", 0),
        "resolved": counts.get("Resolved", 0),
        "closed": counts.get("Closed", 0),
        "unassigned": open_queue.count(),
        "average_hours": average_hours,
        "status_rows": status_rows,
        "priority_rows": priority_rows,
        "category_rows": category_rows,
        "technician_rows": technician_rows,
    }
