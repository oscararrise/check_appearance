import io
import json
import uuid
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from .card_resolver import CardResolution, CardResolverError, resolve_card
from .import_services import ImportServiceError, import_workbook
from .models import AppearanceCheck, DataUpload, PowerAutomateDelivery
from .power_automate import publish_appearance_check
from .services import EmployeeProfile
from .studio_assignment import (
    AUTH_ERROR,
    INVALID_RESPONSE,
    NOT_FOUND,
    UNAVAILABLE,
    fetch_studio_assignment,
    parse_studio_assignment,
)


class CardResolverHardeningTests(SimpleTestCase):
    resolver_settings = {
        "CARD_RESOLVER_ENABLED": True,
        "CARD_RESOLVER_URL": "https://resolver.example/api/v1/cards/resolve",
        "CARD_RESOLVER_SERVICE_TOKEN": "test-service-token",
        "CARD_RESOLVER_TIMEOUT_SECONDS": 2,
        "CARD_RESOLVER_MAX_RESPONSE_BYTES": 4096,
    }

    @override_settings(**resolver_settings)
    @patch("appearance.card_resolver.urlopen")
    def test_not_found_is_typed_404(self, mocked_urlopen):
        mocked_urlopen.side_effect = HTTPError(
            "https://resolver.example",
            404,
            "not found",
            None,
            None,
        )

        with self.assertRaises(CardResolverError) as ctx:
            resolve_card("123456")

        self.assertEqual(ctx.exception.code, "CARD_NOT_FOUND")
        self.assertEqual(ctx.exception.http_status, 404)
        self.assertFalse(ctx.exception.retryable)

    @override_settings(**resolver_settings)
    @patch("appearance.card_resolver.urlopen")
    def test_dependency_timeout_is_retryable(self, mocked_urlopen):
        mocked_urlopen.side_effect = URLError("timeout")

        with self.assertRaises(CardResolverError) as ctx:
            resolve_card("123456")

        self.assertEqual(ctx.exception.code, "CARD_RESOLVER_UNAVAILABLE")
        self.assertEqual(ctx.exception.http_status, 503)
        self.assertTrue(ctx.exception.retryable)

    @override_settings(**resolver_settings)
    @patch("appearance.card_resolver.urlopen")
    def test_invalid_json_is_502_not_a_fake_not_found(self, mocked_urlopen):
        response = MagicMock()
        response.read.return_value = b"<html>bad gateway</html>"
        mocked_urlopen.return_value.__enter__.return_value = response

        with self.assertRaises(CardResolverError) as ctx:
            resolve_card("123456")

        self.assertEqual(ctx.exception.code, "CARD_RESOLVER_INVALID_RESPONSE")
        self.assertEqual(ctx.exception.http_status, 502)


class WorkforceHardeningTests(SimpleTestCase):
    @override_settings(
        POWER_AUTOMATE_LOOKUP_ENABLED=True,
        POWER_AUTOMATE_LOOKUP_FLOW_URL="https://flow.example/workforce",
        POWER_AUTOMATE_LOOKUP_API_KEY="",
        POWER_AUTOMATE_LOOKUP_TIMEOUT_SECONDS=2,
        POWER_AUTOMATE_LOOKUP_MAX_RESPONSE_BYTES=4096,
    )
    @patch("appearance.studio_assignment.urlopen")
    def test_network_failure_is_unavailable(self, mocked_urlopen):
        mocked_urlopen.side_effect = URLError("network down")
        result = fetch_studio_assignment("47827", "Sara Espitia")

        self.assertEqual(result["status"], UNAVAILABLE)
        self.assertTrue(result["retryable"])
        self.assertFalse(result["found"])

    @override_settings(
        POWER_AUTOMATE_LOOKUP_ENABLED=True,
        POWER_AUTOMATE_LOOKUP_FLOW_URL="https://flow.example/workforce",
        POWER_AUTOMATE_LOOKUP_API_KEY="",
        POWER_AUTOMATE_LOOKUP_TIMEOUT_SECONDS=2,
        POWER_AUTOMATE_LOOKUP_MAX_RESPONSE_BYTES=4096,
    )
    @patch("appearance.studio_assignment.urlopen")
    def test_auth_failure_is_not_reported_as_employee_missing(self, mocked_urlopen):
        mocked_urlopen.side_effect = HTTPError(
            "https://flow.example/workforce",
            401,
            "unauthorized",
            None,
            None,
        )
        result = fetch_studio_assignment("47827", "Sara Espitia")

        self.assertEqual(result["status"], AUTH_ERROR)
        self.assertEqual(result["error_code"], "WORKFORCE_AUTH_ERROR")
        self.assertFalse(result["found"])

    def test_missing_data_shape_is_invalid_response(self):
        result = parse_studio_assignment(
            {"table_found": "Table2"},
            "47827",
            "Sara Espitia",
        )
        self.assertEqual(result["status"], INVALID_RESPONSE)

    def test_empty_valid_dataset_is_real_not_found(self):
        result = parse_studio_assignment(
            {"table_found": "Table2", "data": []},
            "47827",
            "Sara Espitia",
        )
        self.assertEqual(result["status"], NOT_FOUND)
        self.assertEqual(result["error_code"], "WORKFORCE_EMPLOYEE_NOT_FOUND")

    def test_empty_dataset_without_table_confirmation_is_invalid(self):
        result = parse_studio_assignment(
            {"data": []},
            "47827",
            "Sara Espitia",
        )
        self.assertEqual(result["status"], INVALID_RESPONSE)
        self.assertEqual(result["error_code"], "WORKFORCE_INVALID_RESPONSE")

    def test_excel_numeric_employee_id_with_dot_zero_matches(self):
        payload = {
            "table_found": "Table2",
            "data": [
                {
                    "Column1": "ID",
                    "Column2": "7.3 Portuguese (LIVE) Generic",
                },
                {
                    "Column1": "47827.0",
                    "Column2": "Sara Espitia Alonso BJ/SP BJ/SPEED",
                },
            ],
        }

        result = parse_studio_assignment(
            payload,
            "47827",
            "Sara Espitia Alonso",
        )

        self.assertTrue(result["found"])
        self.assertEqual(result["status"], "FOUND")
        self.assertEqual(result["studio"], "7.3")

    def test_employee_row_without_assignment_text_column_is_invalid(self):
        result = parse_studio_assignment(
            {
                "table_found": "Table2",
                "data": [{"ID": "47827"}],
            },
            "47827",
            "Sara Espitia",
        )
        self.assertEqual(result["status"], INVALID_RESPONSE)


class PowerAutomateSanitizationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="operator",
            password="test-password",
        )
        self.check = AppearanceCheck.objects.create(
            employee_id="49105",
            employee_name="Test Employee",
            role="Game Presenter",
            shift="MORNING",
            status=AppearanceCheck.Status.READY,
            is_late=False,
            recorded_by=self.user,
        )

    @override_settings(
        POWER_AUTOMATE_ENABLED=True,
        POWER_AUTOMATE_FLOW_URL="https://flow.example/private-signed-url",
        POWER_AUTOMATE_API_KEY="super-secret-api-key",
        POWER_AUTOMATE_TIMEOUT_SECONDS=2,
    )
    @patch("appearance.power_automate.urlopen")
    def test_http_error_body_is_never_persisted(self, mocked_urlopen):
        mocked_urlopen.side_effect = HTTPError(
            "https://flow.example/private-signed-url",
            500,
            "error",
            None,
            io.BytesIO(b"secret-token-that-must-not-be-stored"),
        )

        delivery = publish_appearance_check(self.check)

        self.assertEqual(delivery.status, PowerAutomateDelivery.Status.FAILED)
        self.assertEqual(delivery.last_error, "HTTP_500")
        self.assertNotIn("secret", delivery.last_error.lower())


class OperationalApiHardeningTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="operator@arrise.com",
            password="test-password",
        )
        self.client.force_login(self.user)
        self.profile = EmployeeProfile(
            employee_id="47827",
            full_name="Sara Espitia Alonso",
            role="Game Presenter",
            tattoo_records=[],
            appearance_approval_records=[],
        )

    def test_malformed_json_returns_stable_error_contract(self):
        response = self.client.post(
            "/api/employee/lookup/",
            data="{",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "INVALID_JSON")

    @patch("appearance.views.get_employee_profile", return_value=None)
    @patch(
        "appearance.views.resolve_card",
        return_value=CardResolution(
            employee_id="47827",
            employee_name="Sara Espitia",
            facility_code="1",
            card_number="2",
        ),
    )
    def test_card_to_hibob_mismatch_is_explicit(self, _resolver, _profile):
        response = self.client.post(
            "/api/employee/lookup/",
            data=json.dumps({
                "lookup_mode": "card",
                "card_raw": "123456",
                "process": "CHECK",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error_code"],
            "CARD_HIBOB_MAPPING_MISMATCH",
        )

    @override_settings(POWER_AUTOMATE_ENABLED=False)
    @patch("appearance.views.get_employee_profile")
    def test_check_post_is_idempotent(self, get_profile):
        get_profile.return_value = self.profile
        request_id = str(uuid.uuid4())
        body = {
            "employee_id": "47827",
            "status": "READY",
            "late": False,
            "comment": "",
            "request_id": request_id,
        }

        first = self.client.post(
            "/api/check/record/",
            data=json.dumps(body),
            content_type="application/json",
        )
        second = self.client.post(
            "/api/check/record/",
            data=json.dumps(body),
            content_type="application/json",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(first.json()["idempotent_replay"])
        self.assertTrue(second.json()["idempotent_replay"])
        self.assertEqual(AppearanceCheck.objects.count(), 1)

    @override_settings(POWER_AUTOMATE_ENABLED=False)
    @patch("appearance.views.get_employee_profile")
    def test_reused_request_id_with_different_operation_is_rejected(self, get_profile):
        get_profile.return_value = self.profile
        request_id = str(uuid.uuid4())

        first_body = {
            "employee_id": "47827",
            "status": "READY",
            "late": False,
            "comment": "",
            "request_id": request_id,
        }
        second_body = {
            **first_body,
            "status": "DECLINED",
        }

        self.client.post(
            "/api/check/record/",
            data=json.dumps(first_body),
            content_type="application/json",
        )
        response = self.client.post(
            "/api/check/record/",
            data=json.dumps(second_body),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error_code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(AppearanceCheck.objects.count(), 1)

    def test_export_requires_supervisor_role(self):
        denied = self.client.get("/reports/export/?process=CHECK")
        self.assertEqual(denied.status_code, 403)

        supervisor_group = Group.objects.create(name="Appearance Supervisors")
        self.user.groups.add(supervisor_group)
        allowed = self.client.get("/reports/export/?process=CHECK")
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(
            allowed["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


class UploadHardeningTests(SimpleTestCase):
    @override_settings(APPEARANCE_MAX_UPLOAD_BYTES=10)
    def test_model_rejects_oversized_admin_upload(self):
        upload = DataUpload(
            file=SimpleUploadedFile("security.csv", b"01234567890"),
            source_type=DataUpload.SourceType.SECURITY_GENERAL,
            uploaded_by_id=1,
        )
        with self.assertRaises(ValidationError) as ctx:
            upload.full_clean()
        self.assertIn("file", ctx.exception.error_dict)

    @override_settings(
        APPEARANCE_MAX_UPLOAD_BYTES=1024 * 1024,
        APPEARANCE_MAX_UNCOMPRESSED_UPLOAD_BYTES=50,
        APPEARANCE_MAX_UPLOAD_ROWS=200000,
    )
    def test_workbook_zip_expansion_limit_is_enforced(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "oversized.xlsx"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("xl/worksheets/sheet1.xml", "x" * 100)

            with self.assertRaises(ImportServiceError) as ctx:
                import_workbook(path)

        self.assertIn("safe processing limit", str(ctx.exception))
