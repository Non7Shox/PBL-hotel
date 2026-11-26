from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import StaffProfile

SIDEBAR = 'class="panel-side"'


class PanelSidebarOnStaffPagesTests(TestCase):
    def _login(self, role):
        user = User.objects.create_user(role, password='test-pass-123')
        StaffProfile.objects.create(user=user, role=role)
        self.client.force_login(user)

    def test_hotel_admin_keeps_sidebar_with_active_item(self):
        self._login(StaffProfile.ROLE_MANAGER)
        for name in ('grid', 'analytics', 'dashboard', 'rooms_board', 'desk_booking'):
            with self.subTest(page=name):
                response = self.client.get(reverse(f'staff:{name}'))
                self.assertContains(response, SIDEBAR)
                self.assertContains(response, 'class="active"', count=1)

    def test_receptionist_gets_no_admin_sidebar(self):
        self._login(StaffProfile.ROLE_RECEPTIONIST)
        for name in ('grid', 'dashboard', 'rooms_board', 'desk_booking'):
            with self.subTest(page=name):
                response = self.client.get(reverse(f'staff:{name}'))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, SIDEBAR)
