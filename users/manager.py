from django.contrib.auth.models import BaseUserManager


# It is used to overvide the default django User Model
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, active=False, admin=False, staff=False):
        if email is None:
            raise TypeError("User should have an Email")

        if email is None:
            raise TypeError("User should have an Email")

        user = self.model(email=self.normalize_email(email))
        user.admin = admin
        user.active = active
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None):
        if password is None:
            raise TypeError("Password should not be none")

        user = self.create_user(email, password)
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save()
        return user
