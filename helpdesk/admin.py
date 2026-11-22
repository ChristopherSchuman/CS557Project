from django.contrib import admin

from .models import Category, StatusHistory, Ticket, TicketComment, User

admin.site.site_header = "Help-Desk Hub"
admin.site.site_title = "Help-Desk Hub"
admin.site.index_title = "SQL tables"


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "email", "role", "is_active", "date_joined")
    list_filter = ("role", "is_active")
    search_fields = ("username", "email")
    readonly_fields = ("password", "date_joined", "last_login")

    def has_add_permission(self, request):
        return False


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description")
    search_fields = ("name",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "requester",
        "assigned_technician",
        "category",
        "priority",
        "status",
        "created_at",
        "resolved_at",
    )
    list_filter = ("status", "priority", "category")
    search_fields = ("title", "description")


@admin.register(TicketComment)
class TicketCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "ticket", "author", "created_at")
    search_fields = ("body",)


@admin.register(StatusHistory)
class StatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "ticket", "old_status", "new_status", "changed_by", "changed_at")
    search_fields = ("note",)
