import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .models import AppearanceCheck, PowerAutomateDelivery
from .power_automate import build_appearance_check_payload, publish_appearance_check


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
        self.assertEqual(payload["comment"], "Hair correction required.")
        self.assertEqual(payload["fs_input"], "")
        self.assertEqual(payload["comment_update_final_check"], "")

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
