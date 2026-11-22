from django.db import migrations

CATEGORIES = [
    ("Hardware", "Computers, peripherals, and other physical equipment."),
    ("Software", "Applications, installations, and program errors."),
    ("Network", "Connectivity, Wi-Fi, and VPN issues."),
    ("Account_Access", "Passwords, permissions, and locked accounts."),
    ("Printer", "Printers, scanners, and print queues."),
    ("Other", "Issues that do not fit the other categories."),
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model("helpdesk", "Category")
    for name, description in CATEGORIES:
        Category.objects.get_or_create(name=name, defaults={"description": description})


def remove_categories(apps, schema_editor):
    Category = apps.get_model("helpdesk", "Category")
    Category.objects.filter(name__in=[name for name, _description in CATEGORIES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("helpdesk", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_categories, remove_categories),
    ]
