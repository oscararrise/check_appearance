from django.test import SimpleTestCase

from .studio_assignment import parse_studio_assignment


class StudioAssignmentParserTests(SimpleTestCase):
    def test_extracts_nearest_header_and_game(self):
        payload = {
            "hibob_id": "48444",
            "table_found": "Table4",
            "data": [
                {
                    "Column1": " ID ",
                    "Column2": "8.5 Spanish Top Card (LIVE) (NO VISIBLE TATTOOS) Dedicated",
                },
                {
                    "Column1": "48281",
                    "Column2": "Daniel Molina BJ/VIP BJ/TOP CARD/MW",
                },
                {
                    "Column1": "47260",
                    "Column2": "Cristian Leonardo Diaz Barbosa BJ/VIP BJ/ONE BJ/TOP CARD",
                },
                {
                    "Column1": "48444",
                    "Column2": "Johan Andrés Valderrama López BJ/VIP BJ/ONE BJ/TOP CARD",
                },
            ],
        }

        result = parse_studio_assignment(
            payload,
            "48444",
            "Johan Andrés Valderrama López",
        )

        self.assertTrue(result["found"])
        self.assertEqual(result["studio"], "8.5")
        self.assertEqual(result["assignment_type"], "Dedicated")
        self.assertEqual(result["game"], "BJ/VIP BJ/ONE BJ/TOP CARD")
        self.assertEqual(
            result["studio_title"],
            "8.5 Spanish Top Card (LIVE) (NO VISIBLE TATTOOS) Dedicated",
        )

    def test_returns_not_found_when_id_is_missing_from_data(self):
        payload = {
            "hibob_id": "48444",
            "table_found": "Table4",
            "data": [
                {"Column1": " ID ", "Column2": "9.1 BJ Dedicated"},
                {"Column1": "49105", "Column2": "Julio Cesar Tovar Rodriguez BJ/SP BJ/FBJ"},
            ],
        }

        result = parse_studio_assignment(payload, "48444", "Johan Valderrama")

        self.assertFalse(result["found"])


    def test_supports_dynamic_excel_column_names(self):
        payload = {
            "hibob_id": "47827",
            "table_found": "Table2",
            "data": [
                {
                    "ID": "ID",
                    "7_x002e_1 Spanish (LIVE) Generic": "7.3 Portuguese (LIVE) Generic (NO VISIBLE TATTOOS)",
                    "TEAM": "TEAM",
                    "Appereance Check": "Appereance Check",
                    "Not Ready/Declined": "Not Ready/Declined",
                    "Comment": "Comment",
                    "Comment Update (Final Check)": "Comment",
                    "Tattoo policy": "Tattoo policy",
                },
                {
                    "ID": "46332",
                    "7_x002e_1 Spanish (LIVE) Generic": "Hernan Tello BJ/SP BJ/FBJ",
                    "TEAM": "",
                    "Appereance Check": "",
                    "Not Ready/Declined": "",
                    "Comment": "",
                    "Comment Update (Final Check)": "",
                    "Tattoo policy": "",
                },
                {
                    "ID": "47827",
                    "7_x002e_1 Spanish (LIVE) Generic": "Sara Espitia Alonso BJ/SP BJ/SPEED BR/RW",
                    "TEAM": "",
                    "Appereance Check": "",
                    "Not Ready/Declined": "",
                    "Comment": "",
                    "Comment Update (Final Check)": "",
                    "Tattoo policy": "YES",
                },
            ],
        }

        result = parse_studio_assignment(
            payload,
            "47827",
            "Sara Espitia Alonso",
        )

        self.assertTrue(result["found"])
        self.assertEqual(result["studio"], "7.3")
        self.assertEqual(result["assignment_type"], "Generic")
        self.assertEqual(result["game"], "BJ/SP BJ/SPEED BR/RW")
        self.assertEqual(
            result["studio_title"],
            "7.3 Portuguese (LIVE) Generic (NO VISIBLE TATTOOS)",
        )

    def test_uses_dynamic_column_header_for_first_studio_section(self):
        payload = {
            "hibob_id": "99999",
            "table_found": "Table2",
            "data": [
                {
                    "ID": "99999",
                    "7_x002e_1 Spanish (LIVE) Generic": "Test User BJ/SP BJ/FBJ",
                    "TEAM": "",
                    "Appereance Check": "",
                    "Not Ready/Declined": "",
                    "Comment": "",
                    "Comment Update (Final Check)": "",
                    "Tattoo policy": "",
                },
            ],
        }

        result = parse_studio_assignment(payload, "99999", "Test User")

        self.assertTrue(result["found"])
        self.assertEqual(result["studio"], "7.1")
        self.assertEqual(result["assignment_type"], "Generic")
        self.assertEqual(result["game"], "BJ/SP BJ/FBJ")


    def test_assignment_type_falls_back_to_dynamic_column_name(self):
        payload = {
            "hibob_id": "46228",
            "table_found": "Table2",
            "data": [
                {
                    "ID": "ID",
                    "7_x002e_1 Spanish (LIVE) Generic": "7.10 Portuguese (LIVE)",
                    "TEAM": "TEAM",
                    "Appereance Check": "Appereance Check",
                    "Not Ready/Declined": "Not Ready/Declined",
                    "Comment": "Comment",
                    "Comment Update (Final Check)": "Comment",
                    "Tattoo policy": "Tattoo policy",
                },
                {
                    "ID": "46228",
                    "7_x002e_1 Spanish (LIVE) Generic": "Patricia Targino Romero BJ/TP/RW/VIP/MW",
                    "TEAM": "",
                    "Appereance Check": "",
                    "Not Ready/Declined": "",
                    "Comment": "",
                    "Comment Update (Final Check)": "",
                    "Tattoo policy": "",
                },
            ],
        }

        result = parse_studio_assignment(
            payload,
            "46228",
            "Patricia Targino Romero",
        )

        self.assertTrue(result["found"])
        self.assertEqual(result["studio"], "7.10")
        self.assertEqual(result["assignment_type"], "Generic")
        self.assertEqual(result["game"], "BJ/TP/RW/VIP/MW")
