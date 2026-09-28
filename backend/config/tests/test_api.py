from django.test import SimpleTestCase

from config.api import safe_exception_handler


class SafeApiExceptionHandlerTests(SimpleTestCase):
    def test_unhandled_errors_have_a_generic_response(self):
        response = safe_exception_handler(RuntimeError("sensitive provider detail"), {})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data, {"detail": "The request could not be completed."})
