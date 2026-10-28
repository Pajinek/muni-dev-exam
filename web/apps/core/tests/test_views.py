from django.test import Client, TestCase


class HomePageTest(TestCase):
    def setUp(self):
        self.cli = Client()

    def test_root_redirects_to_admin_login(self):
        """Kořen mapuje na admin.site.urls — nepřihlášený uživatel dostane redirect."""
        response = self.cli.get("/")
        self.assertEqual(302, response.status_code)
        self.assertIn("/login/", response["Location"])
