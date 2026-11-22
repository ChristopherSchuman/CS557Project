from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CommentForm, RegisterForm, TicketCreateForm, TicketUpdateForm
from .models import PRIORITY_CHOICES, ROLE_TECHNICIAN, STATUS_CHOICES, Category
from .services import add_comment, open_ticket, ticket_kpis, update_ticket, visible_tickets


class HelpdeskLoginView(LoginView):
    template_name = "helpdesk/login.html"
    redirect_authenticated_user = True


class HelpdeskLogoutView(LogoutView):
    pass


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "helpdesk/home.html")


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Account created. Log in to open a ticket.")
        return redirect("login")
    return render(request, "helpdesk/register.html", {"form": form})


@login_required
def dashboard(request):
    tickets = visible_tickets(request.user)
    context = {
        "open_count": tickets.filter(status="Open").count(),
        "in_progress_count": tickets.filter(status="In Progress").count(),
        "mine_count": tickets.count(),
        "recent_tickets": tickets[:6],
    }
    if request.user.role == ROLE_TECHNICIAN:
        context["kpis"] = ticket_kpis()
    return render(request, "helpdesk/dashboard.html", context)


@login_required
def ticket_list(request):
    tickets = visible_tickets(request.user)
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    priority = request.GET.get("priority", "").strip()
    category = request.GET.get("category", "").strip()

    if query:
        tickets = tickets.filter(Q(title__icontains=query) | Q(description__icontains=query))
    valid_status = {value for value, _label in STATUS_CHOICES}
    valid_priority = {value for value, _label in PRIORITY_CHOICES}
    if status in valid_status:
        tickets = tickets.filter(status=status)
    else:
        status = ""
    if priority in valid_priority:
        tickets = tickets.filter(priority=priority)
    else:
        priority = ""
    if category.isdigit() and Category.objects.filter(pk=int(category)).exists():
        tickets = tickets.filter(category_id=int(category))
    else:
        category = ""

    paginator = Paginator(tickets, 12)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "helpdesk/ticket_list.html",
        {
            "page": page,
            "query": query,
            "status": status,
            "priority": priority,
            "category": category,
            "status_choices": STATUS_CHOICES,
            "priority_choices": PRIORITY_CHOICES,
            "categories": Category.objects.all(),
        },
    )


@login_required
def ticket_create(request):
    form = TicketCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ticket = open_ticket(
            requester=request.user,
            title=form.cleaned_data["title"],
            description=form.cleaned_data["description"],
            category=form.cleaned_data["category"],
            priority=form.cleaned_data["priority"],
        )
        messages.success(request, f"{ticket.reference} opened.")
        return redirect(ticket)
    return render(request, "helpdesk/ticket_form.html", {"form": form})


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(visible_tickets(request.user), pk=pk)
    is_technician = request.user.role == ROLE_TECHNICIAN
    comment_form = CommentForm()
    update_form = TicketUpdateForm(instance=ticket) if is_technician else None

    if request.method == "POST" and "add_comment" in request.POST:
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            add_comment(
                ticket=ticket,
                author=request.user,
                body=comment_form.cleaned_data["body"],
            )
            messages.success(request, "Comment added.")
            return redirect(ticket)
    elif request.method == "POST" and "update_ticket" in request.POST:
        if not is_technician:
            raise PermissionDenied("Only a technician can update a ticket.")
        update_form = TicketUpdateForm(request.POST, instance=ticket)
        if update_form.is_valid():
            data = update_form.cleaned_data
            update_ticket(
                ticket=ticket,
                editor=request.user,
                title=data["title"],
                description=data["description"],
                category=data["category"],
                priority=data["priority"],
                status=data["status"],
                assigned_technician=data["assigned_technician"],
                note=data["note"],
            )
            messages.success(request, f"{ticket.reference} updated.")
            return redirect(ticket)

    return render(
        request,
        "helpdesk/ticket_detail.html",
        {
            "ticket": ticket,
            "comments": ticket.comments.select_related("author"),
            "history": ticket.status_history.select_related("changed_by"),
            "comment_form": comment_form,
            "update_form": update_form,
            "is_technician": is_technician,
        },
    )


@login_required
def category_list(request):
    if request.user.role == ROLE_TECHNICIAN:
        categories = Category.objects.annotate(ticket_count=Count("tickets"))
    else:
        categories = Category.objects.annotate(
            ticket_count=Count("tickets", filter=Q(tickets__requester=request.user))
        )
    return render(request, "helpdesk/categories.html", {"categories": categories})


@login_required
def reports(request):
    if request.user.role != ROLE_TECHNICIAN:
        raise PermissionDenied("Reports are limited to technicians.")
    return render(request, "helpdesk/reports.html", {"kpis": ticket_kpis()})
