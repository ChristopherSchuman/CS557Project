from django.core.management.base import BaseCommand

from helpdesk.models import ROLE_CUSTOMER, ROLE_TECHNICIAN, Category, User

CATEGORIES = [
    ("Hardware", "Computers, peripherals, and other physical equipment."),
    ("Software", "Applications, installations, and program errors."),
    ("Network", "Connectivity, Wi-Fi, and VPN issues."),
    ("Account_Access", "Passwords, permissions, and locked accounts."),
    ("Printer", "Printers, scanners, and print queues."),
    ("Other", "Issues that do not fit the other categories."),
]

DEMO_USERS = [
    ("technician1", "tech@helpdeskhub.test", "HelpDesk!tech", ROLE_TECHNICIAN),
    ("customer1", "customer@helpdeskhub.test", "HelpDesk!user", ROLE_CUSTOMER),
]


class Command(BaseCommand):
    help = "Create the proposal categories and the technician1 / customer1 demo logins."

    def handle(self, *args, **options):
        for name, description in CATEGORIES:
            Category.objects.get_or_create(name=name, defaults={"description": description})
        for username, email, password, role in DEMO_USERS:
            if User.objects.filter(username=username).exists():
                continue
            User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role=role,
            )
        self.stdout.write(self.style.SUCCESS("Help-Desk Hub seed data is ready."))
