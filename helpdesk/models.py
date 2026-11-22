"""Help-Desk Hub tables.

SQL table and column names follow the Group 5 proposal:
Users, Categories, Tickets, Ticket_Comments, and Status_History.
"""

from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from .managers import UserManager
from .roles import ROLE_CUSTOMER, ROLE_TECHNICIAN

ROLE_CHOICES = [
    (ROLE_TECHNICIAN, "Technician"),
    (ROLE_CUSTOMER, "Help Desk Customer"),
]

PRIORITY_LOW = "Low"
PRIORITY_MEDIUM = "Medium"
PRIORITY_HIGH = "High"
PRIORITY_CRITICAL = "Critical"
PRIORITY_CHOICES = [
    (PRIORITY_LOW, "Low"),
    (PRIORITY_MEDIUM, "Medium"),
    (PRIORITY_HIGH, "High"),
    (PRIORITY_CRITICAL, "Critical"),
]
PRIORITY_VALUES = [value for value, _label in PRIORITY_CHOICES]

STATUS_OPEN = "Open"
STATUS_IN_PROGRESS = "In Progress"
STATUS_RESOLVED = "Resolved"
STATUS_CLOSED = "Closed"
STATUS_CHOICES = [
    (STATUS_OPEN, "Open"),
    (STATUS_IN_PROGRESS, "In Progress"),
    (STATUS_RESOLVED, "Resolved"),
    (STATUS_CLOSED, "Closed"),
]
STATUS_VALUES = [value for value, _label in STATUS_CHOICES]
RESOLVED_STATUSES = {STATUS_RESOLVED, STATUS_CLOSED}


class User(AbstractBaseUser):
    id = models.BigAutoField(primary_key=True, db_column="Id")
    username = models.CharField(max_length=150, unique=True, db_column="Username")
    email = models.EmailField(unique=True, db_column="Email")
    password = models.CharField(max_length=128, db_column="Password")
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, db_column="Role")
    is_active = models.BooleanField(default=True, db_column="Is_active")
    date_joined = models.DateTimeField(default=timezone.now, db_column="Date_Joined")

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email", "role"]
    EMAIL_FIELD = "email"

    class Meta:
        db_table = "Users"
        ordering = ["username"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=[ROLE_TECHNICIAN, ROLE_CUSTOMER]),
                name="users_role_valid",
            ),
        ]

    def __str__(self):
        return self.username

    @property
    def is_technician(self):
        return self.role == ROLE_TECHNICIAN

    @property
    def is_staff(self):
        return self.is_technician

    def has_perm(self, perm, obj=None):
        return self.is_active and self.is_technician

    def has_module_perms(self, app_label):
        return self.is_active and self.is_technician


class Category(models.Model):
    id = models.BigAutoField(primary_key=True, db_column="Id")
    name = models.CharField(max_length=64, unique=True, db_column="Name")
    description = models.TextField(blank=True, db_column="Description")

    class Meta:
        db_table = "Categories"
        ordering = ["id"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Ticket(models.Model):
    id = models.BigAutoField(primary_key=True, db_column="id")
    requester = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="requested_tickets",
        db_column="Requester_id",
    )
    # Column spelling matches the proposal: Assigned_Technichan_id.
    assigned_technician = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_tickets",
        db_column="Assigned_Technichan_id",
    )
    # The proposal writes "category _id"; the SQL column is category_id.
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="tickets",
        db_column="category_id",
    )
    title = models.CharField(max_length=200, db_column="Title")
    description = models.TextField(db_column="Description")
    priority = models.CharField(
        max_length=16,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_MEDIUM,
        db_column="Priority",
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
        db_column="Status",
    )
    created_at = models.DateTimeField(default=timezone.now, db_column="Created_at")
    resolved_at = models.DateTimeField(null=True, blank=True, db_column="resolved_at")

    class Meta:
        db_table = "Tickets"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(priority__in=PRIORITY_VALUES),
                name="tickets_priority_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=STATUS_VALUES),
                name="tickets_status_valid",
            ),
        ]

    def __str__(self):
        return f"{self.reference}: {self.title}"

    @property
    def reference(self):
        return f"HD-{self.id:04d}" if self.id else "HD-new"

    @property
    def status_class(self):
        return self.status.lower().replace(" ", "-")

    @property
    def priority_class(self):
        return self.priority.lower().replace(" ", "-")

    def get_absolute_url(self):
        return reverse("ticket_detail", args=[self.pk])

    def clean(self):
        super().clean()
        technician = self.assigned_technician
        if technician is not None and technician.role != ROLE_TECHNICIAN:
            raise ValidationError(
                {"assigned_technician": "Only a Technician can be assigned to a ticket."}
            )


class TicketComment(models.Model):
    id = models.BigAutoField(primary_key=True, db_column="id")
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="comments",
        db_column="ticket_id",
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="comments",
        db_column="author_id",
    )
    body = models.TextField(db_column="Body")
    created_at = models.DateTimeField(default=timezone.now, db_column="created_at")

    class Meta:
        db_table = "Ticket_Comments"
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"Comment {self.id} on ticket {self.ticket_id}"


class StatusHistory(models.Model):
    id = models.BigAutoField(primary_key=True, db_column="id")
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="status_history",
        db_column="ticket_id",
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="status_changes",
        db_column="changed_by_id",
    )
    old_status = models.CharField(max_length=16, blank=True, db_column="old_Status")
    new_status = models.CharField(max_length=16, db_column="New_status")
    changed_at = models.DateTimeField(default=timezone.now, db_column="Changed_at")
    note = models.TextField(blank=True, db_column="Note")

    class Meta:
        db_table = "Status_History"
        ordering = ["changed_at", "id"]
        verbose_name_plural = "status history"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(old_status="") | models.Q(old_status__in=STATUS_VALUES),
                name="status_history_old_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(new_status__in=STATUS_VALUES),
                name="status_history_new_status_valid",
            ),
        ]

    def __str__(self):
        previous = self.old_status or "New"
        return f"{previous} -> {self.new_status}"
