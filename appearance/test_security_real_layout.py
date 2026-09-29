from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase

from .import_services import import_workbook
from .models import ImportBatch, SecurityInfoRecord


class SecurityRealLayoutImportTests(TestCase):
    def test_cp1252_csv_with_blank_employee_id_header_and_trailing_number_rows(self):
        headers = [
            "Nro ",
            "",
            "DOCUMENTO",
            "NOMBRE",
            "APELLIDOS",
            "NUMERO CONTACTO",
            "RH",
            "TIPO",
            "MARCA",
            "MODELO",
            "COLOR",
            "PLACAS VEHICULO ",
            "DEPARTAMENTO",
            "CARGO",
            "No TARJETA",
            "No TARJETA SEC",
            "Facility Code WFM",
            "Facility Code SE",
            "FOTO Y DATOS ",
            "EPS",
            "No Tarjeta (6 Digitos)",
            "REPOSICIÓN ",
            "Fecha 1era Reposicion ",
            "SEGUNDA REPOSICIÓN ",
            "Fecha 2da Reposicion ",
            "Unnamed: 25",
            "Unnamed: 26",
        ]
        rows = [
            [
                "1",
                "93001",
                "0000000001",
                "Synthetic",
                "Employee One",
                "3000000001",
                "O+",
                "Moto",
                "Test Motorcycle",
                "Test Model",
                "Test Color",
                "TEST01",
                "Operations Direct",
                "Game Presenter with Spanish",
                "TEST-CARD-0001",
                "60001",
                "1001",
                "2001",
                "SI",
                "Test EPS",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ],
            [
                "2",
                "93002",
                "0000000002",
                "Synthetic José",
                "Employee Two Peña",
                "3000000002",
                "A+",
                "",
                "",
                "",
                "",
                "",
                "Security",
                "Security Officer",
                "CARD-002",
                "",
                "1001",
                "2001",
                "SÍ",
                "Test EPS Two",
                "",
                "Reposición",
                "15/09/2026",
                "",
                "",
                "",
                "",
            ],
            ["3"] + [""] * 26,
            ["4"] + [""] * 26,
        ]

        def csv_line(values):
            escaped = []
            for value in values:
                value = str(value)
                if any(char in value for char in [",", '"', "\n"]):
                    value = '"' + value.replace('"', '""') + '"'
                escaped.append(value)
            return ",".join(escaped)

        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "renamed_by_security_team_2026.csv"
            content = "\n".join([csv_line(headers), *(csv_line(row) for row in rows)]) + "\n"
            path.write_bytes(content.encode("cp1252"))

            batch = import_workbook(path, source_type="AUTO")

        self.assertEqual(batch.source_type, ImportBatch.SourceType.SECURITY_GENERAL)
        self.assertEqual(batch.status, ImportBatch.Status.SUCCESS)
        self.assertEqual(batch.rows_received, 2)
        self.assertEqual(batch.rows_imported, 2)
        self.assertEqual(batch.rows_rejected, 0)

        records = SecurityInfoRecord.objects.filter(is_active=True).order_by("employee_id")
        self.assertEqual(records.count(), 2)

        first = records.get(employee_id="93001")
        self.assertEqual(first.document, "0000000001")
        self.assertEqual(first.card_number, "TEST-CARD-0001")
        self.assertEqual(first.facility_code_se, "2001")

        second = records.get(employee_id="93002")
        self.assertEqual(second.first_name, "Synthetic José")
        self.assertEqual(second.last_name, "Employee Two Peña")
        self.assertEqual(second.first_replacement, "Reposición")

    def test_filename_does_not_determine_security_source_type(self):
        headers = "Nro ,,DOCUMENTO,NOMBRE,APELLIDOS,DEPARTAMENTO,CARGO,No TARJETA\n"
        row = "1,12345,900100200,Ana,Pérez,Operations Direct,Game Presenter,CARD-1\n"

        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "totally_different_name.csv"
            path.write_bytes((headers + row).encode("cp1252"))
            batch = import_workbook(path, source_type="AUTO")

        self.assertEqual(batch.source_type, ImportBatch.SourceType.SECURITY_GENERAL)
        self.assertEqual(SecurityInfoRecord.objects.filter(is_active=True).count(), 1)
