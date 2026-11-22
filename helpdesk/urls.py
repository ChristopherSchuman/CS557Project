from django.urls import path

from .views import (
    HelpdeskLoginView,
    HelpdeskLogoutView,
    category_list,
    dashboard,
    home,
    register,
    reports,
    ticket_create,
    ticket_detail,
    ticket_list,
)

urlpatterns = [
    path("", home, name="home"),
    path("login/", HelpdeskLoginView.as_view(), name="login"),
    path("logout/", HelpdeskLogoutView.as_view(), name="logout"),
    path("register/", register, name="register"),
    path("dashboard/", dashboard, name="dashboard"),
    path("tickets/", ticket_list, name="ticket_list"),
    path("tickets/new/", ticket_create, name="ticket_create"),
    path("tickets/<int:pk>/", ticket_detail, name="ticket_detail"),
    path("categories/", category_list, name="category_list"),
    path("reports/", reports, name="reports"),
]
