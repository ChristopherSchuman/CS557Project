from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from helpdesk.models import (
    ROLE_CUSTOMER,
    ROLE_TECHNICIAN,
    STATUS_CLOSED,
    STATUS_IN_PROGRESS,
    STATUS_OPEN,
    STATUS_RESOLVED,
    Category,
    StatusHistory,
    Ticket,
    User,
)
from helpdesk.services import open_ticket, update_ticket


def column_names(table):
    with connection.cursor() as cursor:
        return {column.name for column in connection.introspection.get_table_description(cursor, table)}


class SchemaTests(TestCase):
    def test_proposal_tables_and_columns(self):
        tables = set(connection.introspection.table_names())
        self.assertTrue(
            {"Users", "Categories", "Tickets", "Ticket_Comments", "Status_History"} <= tables
        )
        self.assertEqual(
            column_names("Users"),
            {"Id", "Username", "Email", "Password", "Role", "Is_active", "Date_Joined", "last_login"},
        )
        self.assertEqual(column_names("Categories"), {"Id", "Name", "Description"})
        self.assertEqual(
            column_names("Tickets"),
            {
                "id",
                "Requester_id",
                "Assigned_Technichan_id",
                "category_id",
                "Title",
                "Description",
                "Priority",
                "Status",
                "Created_at",
                "resolved_at",
            },
        )
        self.assertEqual(
            column_names("Ticket_Comments"),
            {"id", "ticket_id", "author_id", "Body", "created_at"},
        )
        self.assertEqual(
            column_names("Status_History"),
            {"id", "ticket_id", "changed_by_id", "old_Status", "New_status", "Changed_at", "Note"},
        )

    def test_role_constraint_rejects_unknown_role(self):
        with self.assertRaises(IntegrityError):
            User.objects.create(
                username="manager",
                email="manager@example.com",
                password="not-a-login",
                role="Manager",
                is_active=True,
                date_joined=timezone.now(),
            )


class WorkflowTests(TestCase):
    def setUp(self):
        self.category, _created = Category.objects.get_or_create(
            name="Hardware",
            defaults={"description": "Devices"},
        )
        self.customer = User.objects.create_user(
            username="ada",
            email="ada@example.com",
            password="HelpDesk!user",
            role=ROLE_CUSTOMER,
        )
        self.other = User.objects.create_user(
            username="grace",
            email="grace@example.com",
            password="HelpDesk!user",
            role=ROLE_CUSTOMER,
        )
        self.technician = User.objects.create_user(
            username="linus",
            email="linus@example.com",
            password="HelpDesk!tech",
            role=ROLE_TECHNICIAN,
        )
        self.ticket = open_ticket(
            requester=self.customer,
            title="Laptop will not boot",
            description="The fan spins, then the screen stays black.",
            category=self.category,
            priority="High",
        )

    def test_password_is_hashed(self):
        self.assertNotEqual(self.customer.password, "HelpDesk!user")
        self.assertTrue(self.customer.check_password("HelpDesk!user"))
        validate_password("HelpDesk!user")

    def test_opening_a_ticket_writes_status_history(self):
        history = StatusHistory.objects.get(ticket=self.ticket)
        self.assertEqual(history.old_status, "")
        self.assertEqual(history.new_status, STATUS_OPEN)
        self.assertEqual(history.changed_by, self.customer)
        self.assertEqual(self.ticket.requester, self.customer)

    def test_customer_sees_only_their_tickets(self):
        open_ticket(
            requester=self.other,
            title="Printer jam",
            description="Tray 2 is stuck.",
            category=self.category,
            priority="Low",
        )
        self.client.force_login(self.customer)
        response = self.client.get(reverse("ticket_list"))
        self.assertContains(response, "Laptop will not boot")
        self.assertNotContains(response, "Printer jam")
        hidden = Ticket.objects.get(title="Printer jam")
        missing = self.client.get(reverse("ticket_detail", args=[hidden.pk]))
        self.assertEqual(missing.status_code, 404)

    def test_technician_sees_every_ticket_and_reports(self):
        self.client.force_login(self.technician)
        response = self.client.get(reverse("ticket_list"))
        self.assertContains(response, "Laptop will not boot")
        reports = self.client.get(reverse("reports"))
        self.assertEqual(reports.status_code, 200)
        self.assertContains(reports, "Reports")

    def test_customer_cannot_open_reports_or_update_a_ticket(self):
        self.client.force_login(self.customer)
        reports = self.client.get(reverse("reports"))
        self.assertEqual(reports.status_code, 403)
        update = self.client.post(
            reverse("ticket_detail", args=[self.ticket.pk]),
            {
                "update_ticket": "1",
                "title": "Changed",
                "description": self.ticket.description,
                "category": self.category.pk,
                "priority": "Low",
                "status": STATUS_CLOSED,
                "assigned_technician": "",
                "note": "Closing it myself",
            },
        )
        self.assertEqual(update.status_code, 403)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, STATUS_OPEN)

    def test_technician_status_change_records_history_and_resolved_at(self):
        update_ticket(
            ticket=self.ticket,
            editor=self.technician,
            title=self.ticket.title,
            description=self.ticket.description,
            category=self.category,
            priority="High",
            status=STATUS_IN_PROGRESS,
            assigned_technician=self.technician,
            note="Looking at the power supply.",
        )
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.resolved_at)
        self.assertEqual(self.ticket.assigned_technician, self.technician)
        update_ticket(
            ticket=self.ticket,
            editor=self.technician,
            title=self.ticket.title,
            description=self.ticket.description,
            category=self.category,
            priority="High",
            status=STATUS_RESOLVED,
            assigned_technician=self.technician,
            note="Replaced the drive.",
        )
        self.ticket.refresh_from_db()
        self.assertIsNotNone(self.ticket.resolved_at)
        self.assertEqual(self.ticket.status_history.count(), 3)
        latest = self.ticket.status_history.order_by("-id").first()
        self.assertEqual(latest.old_status, STATUS_IN_PROGRESS)
        self.assertEqual(latest.new_status, STATUS_RESOLVED)

    def test_reopening_clears_resolved_at(self):
        update_ticket(
            ticket=self.ticket,
            editor=self.technician,
            title=self.ticket.title,
            description=self.ticket.description,
            category=self.category,
            priority="High",
            status=STATUS_CLOSED,
            assigned_technician=self.technician,
            note="Closed after confirmation.",
        )
        update_ticket(
            ticket=self.ticket,
            editor=self.technician,
            title=self.ticket.title,
            description=self.ticket.description,
            category=self.category,
            priority="High",
            status=STATUS_OPEN,
            assigned_technician=self.technician,
            note="The fault came back.",
        )
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.resolved_at)
        self.assertEqual(self.ticket.status, STATUS_OPEN)

    def test_customer_cannot_be_assigned(self):
        with self.assertRaises(ValidationError):
            update_ticket(
                ticket=self.ticket,
                editor=self.technician,
                title=self.ticket.title,
                description=self.ticket.description,
                category=self.category,
                priority="High",
                status=STATUS_OPEN,
                assigned_technician=self.customer,
                note="",
            )

    def test_technician_form_writes_status_history(self):
        self.client.force_login(self.technician)
        response = self.client.post(
            reverse("ticket_detail", args=[self.ticket.pk]),
            {
                "update_ticket": "1",
                "title": self.ticket.title,
                "description": self.ticket.description,
                "category": self.category.pk,
                "priority": "High",
                "status": STATUS_RESOLVED,
                "assigned_technician": self.technician.pk,
                "note": "Replaced the drive.",
            },
        )
        self.assertRedirects(response, self.ticket.get_absolute_url())
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, STATUS_RESOLVED)
        self.assertIsNotNone(self.ticket.resolved_at)
        latest = self.ticket.status_history.order_by("-id").first()
        self.assertEqual(latest.old_status, STATUS_OPEN)
        self.assertEqual(latest.new_status, STATUS_RESOLVED)
        self.assertEqual(latest.note, "Replaced the drive.")
        self.assertEqual(latest.changed_by, self.technician)
        page = self.client.get(self.ticket.get_absolute_url())
        self.assertContains(page, "Replaced the drive.")

    def test_customer_comment_and_login_flow(self):
        self.assertTrue(self.client.login(username="ada", password="HelpDesk!user"))
        response = self.client.post(
            reverse("ticket_detail", args=[self.ticket.pk]),
            {"add_comment": "1", "body": "It failed again after lunch."},
        )
        self.assertRedirects(response, self.ticket.get_absolute_url())
        self.assertEqual(self.ticket.comments.get().author, self.customer)
        self.client.post(reverse("logout"))
        dashboard = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard.status_code, 302)
