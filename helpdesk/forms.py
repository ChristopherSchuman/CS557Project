from django import forms
from django.contrib.auth.password_validation import validate_password

from .models import (
    ROLE_CHOICES,
    ROLE_TECHNICIAN,
    Category,
    Ticket,
    User,
)


class RegisterForm(forms.Form):
    username = forms.CharField(label="Username", max_length=150)
    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Password", widget=forms.PasswordInput)
    role = forms.ChoiceField(label="Role", choices=ROLE_CHOICES)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is already taken.")
        return username

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"]).strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("That email is already registered.")
        return email

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def save(self):
        data = self.cleaned_data
        return User.objects.create_user(
            username=data["username"],
            email=data["email"],
            password=data["password"],
            role=data["role"],
        )


class TicketCreateForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["title", "description", "category", "priority"]
        labels = {
            "title": "Title",
            "description": "Description",
            "category": "Category",
            "priority": "Priority",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.all()
        self.fields["category"].empty_label = "Select a category"


class TicketUpdateForm(forms.ModelForm):
    note = forms.CharField(
        label="Note",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "data-status-note": "true"}),
        help_text="Saved on Status_History when Status changes.",
    )

    class Meta:
        model = Ticket
        fields = [
            "title",
            "description",
            "category",
            "priority",
            "status",
            "assigned_technician",
        ]
        labels = {
            "title": "Title",
            "description": "Description",
            "category": "Category",
            "priority": "Priority",
            "status": "Status",
            "assigned_technician": "Assigned technician",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.all()
        self.fields["assigned_technician"].queryset = User.objects.filter(
            role=ROLE_TECHNICIAN,
            is_active=True,
        )
        self.fields["assigned_technician"].empty_label = "Unassigned"
        self.fields["status"].widget.attrs["data-status-select"] = "true"
        self.fields["status"].widget.attrs["data-original"] = self.instance.status or ""


class CommentForm(forms.Form):
    body = forms.CharField(
        label="Body",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Write an update for this ticket"}),
    )
