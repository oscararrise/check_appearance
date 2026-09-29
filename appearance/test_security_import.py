from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase
from openpyxl import Workbook

from .import_services import import_workbook
from .models import ImportBatch, SecurityInfoRecord


SECURITY_HEADERS = [
    "Nro",
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
    "PLACAS VEHICULO",
    "DEPARTAMENTO",
    "CARGO",
    "No TARJETA",
    "No TARJETA SEC",
    "Facility Code WFM",
    "Facility Code SE",
    "FOTO Y DATOS",
    "EPS",
    "No Tarjeta (6 Digitos)",
    "REPOSICIÓN",
    "Fecha 1era Reposicion",
    "SEGUNDA REPOSICIÓN",
    "Fecha 2da Reposicion",
]

SECURITY_ROW = [
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
]


class SecurityGeneralImportTests(TestCase):
    def test_csv_is_detected_and_imported_regardless_of_filename(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "anything_the_team_wants.csv"
            path.write_text(
                ",".join(SECURITY_HEADERS) + "\n" + ",".join(SECURITY_ROW) + "\n",
                encoding="utf-8",
            )

            batch = import_workbook(path, source_type="AUTO")

        self.assertEqual(batch.source_type, ImportBatch.SourceType.SECURITY_GENERAL)
        self.assertEqual(batch.status, ImportBatch.Status.SUCCESS)
        self.assertEqual(batch.rows_received, 1)
        self.assertEqual(batch.rows_imported, 1)

        record = SecurityInfoRecord.objects.get(is_active=True)
        self.assertEqual(record.employee_id, "93001")
        self.assertEqual(record.document, "0000000001")
        self.assertEqual(record.first_name, "Synthetic")
        self.assertEqual(record.card_number, "TEST-CARD-0001")

    def test_xlsx_security_base_is_auto_detected(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "renamed_security_file.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "BASE GENERAL"
            sheet.append(SECURITY_HEADERS)
            sheet.append(SECURITY_ROW)
            workbook.save(path)
            workbook.close()

            batch = import_workbook(path, source_type="AUTO")

        self.assertEqual(batch.source_type, ImportBatch.SourceType.SECURITY_GENERAL)
        self.assertEqual(batch.status, ImportBatch.Status.SUCCESS)
        self.assertEqual(SecurityInfoRecord.objects.filter(is_active=True).count(), 1)
