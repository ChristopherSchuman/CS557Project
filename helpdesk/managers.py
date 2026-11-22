from django.contrib.auth.base_user import BaseUserManager

from .roles import ROLE_TECHNICIAN


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError("Username is required.")
        if not email:
            raise ValueError("Email is required.")
        user = self.model(
            username=username.strip(),
            email=self.normalize_email(email),
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("role", ROLE_TECHNICIAN)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("role") != ROLE_TECHNICIAN:
            raise ValueError("A superuser must have the Technician role.")
        if extra_fields.get("is_active") is not True:
            raise ValueError("A superuser must be active.")
        return self.create_user(username, email, password, **extra_fields)
