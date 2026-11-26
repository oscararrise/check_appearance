import json
from datetime import datetime, timezone as datetime_timezone
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from .models import AppearanceCheck, PowerAutomateDelivery
from .power_automate import build_appearance_check_payload, publish_appearance_check


class PowerAutomateResponseParsingTests(SimpleTestCase):
    def test_not_found_from_400_response(self):
        from .power_automate import parse_workforce_result
        result = parse_workforce_result(
            400,
            '{"success": false, "code": "NOT_FOUND", "message": "Employee not found in Workforce."}',
        )
        self.assertEqual(result["code"], "NOT_FOUND")

    def test_duplicate_from_409_response(self):
        from .power_automate import parse_workforce_result
        result = parse_workforce_result(
            409,
            '{"success": false, "code": "DUPLICATE", "message": "Duplicate employee ID."}',
        )
        self.assertEqual(result["code"], "DUPLICATE")

    def test_business_error_in_200_response(self):
        from .power_automate import parse_workforce_result
        result = parse_workforce_result(
            200,
            '{"success": false, "code": "NOT_FOUND", "message": "Employee not found."}',
        )
        self.assertEqual(result["code"], "NOT_FOUND")

    def test_view_feedback_accepts_http_400_not_found(self):
        from types import SimpleNamespace
        from .models import PowerAutomateDelivery
        from .views import _workforce_feedback
        delivery = SimpleNamespace(
            status=PowerAutomateDelivery.Status.FAILED,
            response_status=400,
            last_error='HTTP 400: {"success": false, "code": "NOT_FOUND", "message": "Employee not found in Workforce."}',
        )
        self.assertEqual(_workforce_feedback(delivery)["code"], "NOT_FOUND")

    def test_unrelated_errors_not_mislabeled(self):
        from .power_automate import parse_workforce_result
        self.assertIsNone(parse_workforce_result(504, "Gateway Timeout"))
        self.assertIsNone(parse_workforce_result(400, '{"error":"Bad Request"}'))


    def test_abs_requires_explicit_success_and_http_200(self):
        from .power_automate import parse_workforce_success
        body = '{"success": true, "code": "ABS_REGISTERED", "message": "Saved in ABS."}'
        self.assertEqual(parse_workforce_success(200, body), {
            "code": "ABS_REGISTERED", "message": "Saved in ABS.",
        })
        self.assertIsNone(parse_workforce_success(404, body))
        self.assertIsNone(parse_workforce_success(200, '{"success": false, "code": "ABS_REGISTERED"}'))
        self.assertIsNone(parse_workforce_success(200, '{"success": true}'))
        self.assertIsNone(parse_workforce_success(200, 'not JSON'))


class PowerAutomateIntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="operator@arrise.com",
            password="test-password",
        )
        self.check = AppearanceCheck.objects.create(
            employee_id="49105",
            employee_name="Julio Cesar Tovar Rodriguez",
            role="Game Presenter",
            shift="AFTERNOON",
            status=AppearanceCheck.Status.NOT_READY,
            is_late=True,
            late_marked_at=datetime(2026, 10, 14, 18, 25, 30, tzinfo=datetime_timezone.utc),
            comment="Hair correction required.",
            recorded_by=self.user,
        )

    def test_payload_maps_excel_fields(self):
        payload = build_appearance_check_payload(self.check)

        self.assertEqual(payload["employee_id"], "49105")
        self.assertEqual(payload["appearance_check"], "Not Ready")
        self.assertEqual(payload["appearance_check_code"], "NOT_READY")
        self.assertFalse(payload["is_ready"])
        self.assertEqual(payload["not_ready_declined"], "Not Ready")
        self.assertEqual(payload["comment"], "Late - 13:25:30 | Hair correction required.")
        self.assertNotIn("late", payload)
        self.assertNotIn("late_label", payload)
        self.assertNotIn("late_marked_at", payload)
        self.assertNotIn("late_marked_time", payload)
        self.assertEqual(payload["fs_input"], "")
        self.assertEqual(payload["comment_update_final_check"], "")

    def test_late_without_manual_comment_sends_only_late_comment(self):
        self.check.comment = ""
        payload = build_appearance_check_payload(self.check)

        self.assertEqual(payload["comment"], "Late - 13:25:30")

    def test_late_time_falls_back_to_record_timestamp(self):
        self.check.late_marked_at = None
        self.check.recorded_at = datetime(2026, 10, 14, 12, 10, 9, tzinfo=datetime_timezone.utc)
        self.assertEqual(build_appearance_check_payload(self.check)["comment"], "Late - 07:10:09 | Hair correction required.")

    def test_on_time_preserves_manual_comment(self):
        self.check.is_late = False
        self.check.late_marked_at = None
        payload = build_appearance_check_payload(self.check)

        self.assertEqual(payload["comment"], "Hair correction required.")

    @override_settings(POWER_AUTOMATE_ENABLED=False, POWER_AUTOMATE_FLOW_URL="")
    def test_disabled_integration_is_audited_without_network_call(self):
        delivery = publish_appearance_check(self.check)

        self.assertEqual(delivery.status, PowerAutomateDelivery.Status.DISABLED)
        self.assertEqual(delivery.attempts, 0)
        self.assertEqual(delivery.payload["employee_id"], "49105")

    @override_settings(
        POWER_AUTOMATE_ENABLED=True,
        POWER_AUTOMATE_FLOW_URL="https://example.invalid/power-automate",
        POWER_AUTOMATE_API_KEY="",
        POWER_AUTOMATE_TIMEOUT_SECONDS=5,
    )
    @patch("appearance.power_automate.urlopen")
    def test_successful_delivery_marks_sent(self, mocked_urlopen):
        response = MagicMock()
        response.getcode.return_value = 202
        mocked_urlopen.return_value.__enter__.return_value = response

        delivery = publish_appearance_check(self.check)

        self.assertEqual(delivery.status, PowerAutomateDelivery.Status.SENT)
        self.assertEqual(delivery.response_status, 202)
        self.assertEqual(delivery.attempts, 1)
        self.assertIsNotNone(delivery.sent_at)

        request = mocked_urlopen.call_args.args[0]
        sent_payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(sent_payload["employee_id"], "49105")
        self.assertEqual(sent_payload["not_ready_declined"], "Not Ready")
        self.assertEqual(sent_payload["comment"], "Late - 13:25:30 | Hair correction required.")


    @override_settings(
        POWER_AUTOMATE_ENABLED=True,
        POWER_AUTOMATE_FLOW_URL="https://example.invalid/power-automate",
        POWER_AUTOMATE_API_KEY="",
        POWER_AUTOMATE_TIMEOUT_SECONDS=5,
    )
    @patch("appearance.power_automate.urlopen")
    def test_workforce_not_found_is_exposed_as_structured_feedback(self, mocked_urlopen):
        from io import BytesIO
        from urllib.error import HTTPError
        from .views import _workforce_feedback
        body = b'{"success": false, "code": "NOT_FOUND", "message": "Employee not found in Workforce."}'
        mocked_urlopen.side_effect = HTTPError("https://example.invalid", 404, "Not Found", {}, BytesIO(body))
        delivery = publish_appearance_check(self.check)
        self.assertEqual(delivery.response_status, 404)
        self.assertEqual(_workforce_feedback(delivery)["code"], "NOT_FOUND")

    @override_settings(
        POWER_AUTOMATE_ENABLED=True,
        POWER_AUTOMATE_FLOW_URL="https://example.invalid/power-automate",
        POWER_AUTOMATE_API_KEY="",
        POWER_AUTOMATE_TIMEOUT_SECONDS=5,
    )
    @patch("appearance.power_automate.urlopen")
    def test_workforce_duplicate_is_exposed_as_structured_feedback(self, mocked_urlopen):
        from io import BytesIO
        from urllib.error import HTTPError
        from .views import _workforce_feedback
        body = b'{"success": false, "code": "DUPLICATE", "message": "Employee ID found in multiple Workforce records."}'
        mocked_urlopen.side_effect = HTTPError("https://example.invalid", 409, "Conflict", {}, BytesIO(body))
        delivery = publish_appearance_check(self.check)
        self.assertEqual(delivery.response_status, 409)
        self.assertEqual(_workforce_feedback(delivery)["code"], "DUPLICATE")

    @override_settings(
        POWER_AUTOMATE_ENABLED=True,
        POWER_AUTOMATE_FLOW_URL="https://example.invalid/power-automate",
        POWER_AUTOMATE_API_KEY="",
        POWER_AUTOMATE_TIMEOUT_SECONDS=5,
    )
    @patch("appearance.power_automate.urlopen")
    def test_generic_404_does_not_claim_employee_not_found(self, mocked_urlopen):
        from io import BytesIO
        from urllib.error import HTTPError
        from .views import _workforce_feedback
        mocked_urlopen.side_effect = HTTPError("https://example.invalid", 404, "Not Found", {}, BytesIO(b"Route not found"))
        delivery = publish_appearance_check(self.check)
        self.assertIsNone(_workforce_feedback(delivery))


    @override_settings(
        POWER_AUTOMATE_ENABLED=True,
        POWER_AUTOMATE_FLOW_URL="https://example.invalid/power-automate",
        POWER_AUTOMATE_API_KEY="",
        POWER_AUTOMATE_TIMEOUT_SECONDS=5,
    )
    @patch("appearance.power_automate.urlopen")
    def test_abs_registration_is_sent_and_exposed_to_ui(self, mocked_urlopen):
        from .views import _workforce_feedback
        response = MagicMock()
        response.getcode.return_value = 200
        response.read.return_value = b'{"success": true, "code": "ABS_REGISTERED", "message": "Saved in ABS."}'
        mocked_urlopen.return_value.__enter__.return_value = response
        delivery = publish_appearance_check(self.check)
        self.assertEqual(delivery.status, PowerAutomateDelivery.Status.SENT)
        self.assertEqual(delivery.last_error, "")
        self.assertEqual(_workforce_feedback(delivery), {
            "code": "ABS_REGISTERED", "message": "Saved in ABS.",
        })
        self.check.refresh_from_db()
        self.assertEqual(self.check.status, AppearanceCheck.Status.NOT_READY)


class AppearanceCheckLateFieldTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="late-operator", password="test-password")

    def test_late_yes_keeps_audit_timestamp(self):
        marked_at = timezone.now()
        check = AppearanceCheck.objects.create(
            employee_id="10001",
            employee_name="Late Employee",
            role="Game Presenter",
            shift="MORNING",
            status=AppearanceCheck.Status.READY,
            is_late=True,
            late_marked_at=marked_at,
            recorded_by=self.user,
        )
        self.assertTrue(check.is_late)
        self.assertEqual(check.late_marked_at, marked_at)

    def test_late_no_has_no_late_timestamp(self):
        check = AppearanceCheck.objects.create(
            employee_id="10002",
            employee_name="On Time Employee",
            role="Game Presenter",
            shift="MORNING",
            status=AppearanceCheck.Status.READY,
            is_late=False,
            late_marked_at=None,
            recorded_by=self.user,
        )
        self.assertFalse(check.is_late)
        self.assertIsNone(check.late_marked_at)


class CardRegistrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="card-operator", password="test-password")
        self.url = "/api/cards/register/"

    @patch("appearance.views.register_card")
    def test_authenticated_operator_can_register_without_hibob_lookup(self, mocked_register):
        mocked_register.return_value = {"status": "created", "hibob_id": "43052"}
        self.client.force_login(self.user)
        response = self.client.post(self.url, data=json.dumps({"card_raw": "37744611008", "hibob_id": "43052"}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 200)
        mocked_register.assert_called_once_with("37744611008", "43052")

    @patch("appearance.views.register_card")
    def test_unauthenticated_operator_cannot_register(self, mocked_register):
        response = self.client.post(self.url, data=json.dumps({"card_raw": "37744611008", "hibob_id": "43052"}),
                                    content_type="application/json")
        self.assertNotEqual(response.status_code, 200)
        mocked_register.assert_not_called()

    @patch("appearance.views.register_card")
    def test_invalid_id_is_blocked(self, mocked_register):
        self.client.force_login(self.user)
        response = self.client.post(self.url, data=json.dumps({"card_raw": "37744611008", "hibob_id": "ABC"}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 400)
        mocked_register.assert_not_called()

    @patch("appearance.views.resolve_card")
    def test_unknown_card_produces_distinct_code(self, mocked_resolve):
        from .card_resolver import CardNotFoundError
        mocked_resolve.side_effect = CardNotFoundError("Card not found.")
        self.client.force_login(self.user)
        response = self.client.post("/api/employee/lookup/",
                                    data=json.dumps({"lookup_mode": "card", "card_raw": "37744611008"}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "CARD_NOT_FOUND")
