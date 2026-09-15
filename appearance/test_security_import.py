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
    "48961",
    "1024598156",
    "Mackleyn",
    "Abril Camargo",
    "3118350602",
    "O+",
    "Moto",
    "Pulsar",
    "180",
    "Blanco Azul",
    "CBL22E",
    "Operations Direct",
    "Game Presenter with Spanish",
    "167586-11151051820-1",
    "36514",
    "1761",
    "14090",
    "SI",
    "Aliansalud",
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
        self.assertEqual(record.employee_id, "48961")
        self.assertEqual(record.document, "1024598156")
        self.assertEqual(record.first_name, "Mackleyn")
        self.assertEqual(record.card_number, "167586-11151051820-1")

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
