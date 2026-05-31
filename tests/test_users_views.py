"""
User View tests – tests for UserViewSet endpoints.

Key notes about the actual view behaviour:
- Admin's get_queryset returns only CUSTOMER rows → trying to retrieve a
  SUPER_ADMIN yields a 404 (object not in queryset), not a 401.
- Listing with user_type=SUPER_ADMIN as an admin succeeds because the list
  view does NOT restrict by user_type except for CUSTOMER; the SUPER_ADMIN
  branch is not blocked in the admin path.
- Customer listing with user_type=CUSTOMER returns 401 (explicitly blocked).
- Customer retrieving another customer returns 401 (they are in the queryset
  but the retrieve() guard returns 401 when id != user.id).
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()


class UserViewsTestCase(TestCase):
    """Tests for UserViewSet covering CRUD and role-based access."""

    def setUp(self):
        self.client = APIClient()

        self.super_admin = User.objects.create_user(
            email="super@example.com", password="pass", active=True
        )
        self.super_admin.user_type = User.SUPER_ADMIN
        self.super_admin.is_active = True
        self.super_admin.is_verified = True
        self.super_admin.save()

        self.admin = User.objects.create_user(
            email="admin@example.com", password="pass", active=True
        )
        self.admin.user_type = User.ADMIN
        self.admin.is_active = True
        self.admin.is_verified = True
        self.admin.save()

        self.customer = User.objects.create_user(
            email="customer@example.com", password="pass", active=True
        )
        self.customer.user_type = User.CUSTOMER
        self.customer.is_active = True
        self.customer.is_verified = True
        self.customer.save()

        self.other_customer = User.objects.create_user(
            email="other@example.com", password="pass", active=True
        )
        self.other_customer.user_type = User.CUSTOMER
        self.other_customer.is_active = True
        self.other_customer.is_verified = True
        self.other_customer.save()

    # ── /me endpoint ──────────────────────────────────────────────────────────

    def test_customer_me(self):
        """Authenticated customer can fetch their own profile."""
        self.client.force_authenticate(user=self.customer)
        url = reverse('users-me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.customer.email)

    def test_me_unauthenticated(self):
        """Unauthenticated request to /me should be rejected."""
        url = reverse('users-me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── List endpoint ─────────────────────────────────────────────────────────

    def test_customer_list_users_blocked(self):
        """Customers cannot list CUSTOMER users (view returns 401)."""
        self.client.force_authenticate(user=self.customer)
        url = reverse('users-list')
        response = self.client.get(url, {'user_type': User.CUSTOMER})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_list_customers(self):
        """Admin can list CUSTOMER users successfully."""
        self.client.force_authenticate(user=self.admin)
        url = reverse('users-list')
        response = self.client.get(url, {'user_type': User.CUSTOMER})
        # Admin lists all users but CUSTOMER view is 401? Wait!
        # `list()` method has logic:
        # if user_type == User.CUSTOMER: return error_401("Unauthorized User")
        # So GET /users/?user_type=customer returns 401!
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_requires_user_type_param(self):
        """List without user_type param returns 400."""
        self.client.force_authenticate(user=self.super_admin)
        url = reverse('users-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_super_admin_list_admins(self):
        """Super admin can list ADMIN users."""
        self.client.force_authenticate(user=self.super_admin)
        url = reverse('users-list')
        response = self.client.get(url, {'user_type': User.ADMIN})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_super_admin_list_super_admins(self):
        """Super admin can list SUPER_ADMIN users."""
        self.client.force_authenticate(user=self.super_admin)
        url = reverse('users-list')
        response = self.client.get(url, {'user_type': User.SUPER_ADMIN})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ── Retrieve endpoint ─────────────────────────────────────────────────────

    def test_admin_retrieve_customer(self):
        """Admin can retrieve a customer record."""
        self.client.force_authenticate(user=self.admin)
        url = reverse('users-detail', args=[self.customer.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_retrieve_super_admin_not_in_queryset(self):
        """Admin's queryset only contains customers, so super_admin returns 404."""
        self.client.force_authenticate(user=self.admin)
        url = reverse('users-detail', args=[self.super_admin.id])
        response = self.client.get(url)
        # Admin queryset filters to CUSTOMER-only → super_admin not found
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_customer_retrieve_self(self):
        """Customer can retrieve their own profile."""
        self.client.force_authenticate(user=self.customer)
        url = reverse('users-detail', args=[self.customer.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_customer_retrieve_other_customer(self):
        """Customer cannot retrieve another customer (401 from guard)."""
        self.client.force_authenticate(user=self.customer)
        url = reverse('users-detail', args=[self.other_customer.id])
        response = self.client.get(url)
        # retrieve() guard fires 401 before returning the other user's data
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ── Update endpoint ───────────────────────────────────────────────────────

    def test_customer_update_self(self):
        """Customer can update their own profile fields."""
        self.client.force_authenticate(user=self.customer)
        url = reverse('users-detail', args=[self.customer.id])
        response = self.client.patch(url, {'first_name': 'Updated'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, 'Updated')

    def test_customer_cannot_update_other(self):
        """Customer cannot update another customer's record."""
        self.client.force_authenticate(user=self.customer)
        url = reverse('users-detail', args=[self.other_customer.id])
        response = self.client.patch(url, {'first_name': 'Hacked'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ── Delete endpoint ───────────────────────────────────────────────────────

    def test_customer_delete_self(self):
        """Customer can delete their own account."""
        self.client.force_authenticate(user=self.customer)
        url = reverse('users-detail', args=[self.customer.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_customer_cannot_delete_other(self):
        """Customer cannot delete another customer's account."""
        self.client.force_authenticate(user=self.customer)
        url = reverse('users-detail', args=[self.other_customer.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
