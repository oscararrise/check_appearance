from django.test import SimpleTestCase

from .studio_assignment import parse_studio_assignment


class StudioAssignmentParserTests(SimpleTestCase):
    def test_extracts_nearest_header_and_game(self):
        payload = {
            "hibob_id": "91004",
            "table_found": "Table4",
            "data": [
                {
                    "Column1": " ID ",
                    "Column2": "8.5 Spanish Top Card (LIVE) (NO VISIBLE TATTOOS) Dedicated",
                },
                {
                    "Column1": "91001",
                    "Column2": "Synthetic Employee One BJ/VIP BJ/TOP CARD/MW",
                },
                {
                    "Column1": "91002",
                    "Column2": "Synthetic Employee Two BJ/VIP BJ/ONE BJ/TOP CARD",
                },
                {
                    "Column1": "91004",
                    "Column2": "Synthetic Employee Three BJ/VIP BJ/ONE BJ/TOP CARD",
                },
            ],
        }

        result = parse_studio_assignment(
            payload,
            "91004",
            "Synthetic Employee Three",
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
            "hibob_id": "91004",
            "table_found": "Table4",
            "data": [
                {"Column1": " ID ", "Column2": "9.1 BJ Dedicated"},
                {"Column1": "91005", "Column2": "Synthetic Employee Five BJ/SP BJ/FBJ"},
            ],
        }

        result = parse_studio_assignment(payload, "91004", "Synthetic Employee Three")

        self.assertFalse(result["found"])


    def test_supports_dynamic_excel_column_names(self):
        payload = {
            "hibob_id": "92002",
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
                    "ID": "92001",
                    "7_x002e_1 Spanish (LIVE) Generic": "Synthetic Employee Six BJ/SP BJ/FBJ",
                    "TEAM": "",
                    "Appereance Check": "",
                    "Not Ready/Declined": "",
                    "Comment": "",
                    "Comment Update (Final Check)": "",
                    "Tattoo policy": "",
                },
                {
                    "ID": "92002",
                    "7_x002e_1 Spanish (LIVE) Generic": "Synthetic Employee Seven BJ/SP BJ/SPEED BR/RW",
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
            "92002",
            "Synthetic Employee Seven",
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
            "hibob_id": "92003",
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
                    "ID": "92003",
                    "7_x002e_1 Spanish (LIVE) Generic": "Synthetic Employee Eight BJ/TP/RW/VIP/MW",
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
            "92003",
            "Synthetic Employee Eight",
        )

        self.assertTrue(result["found"])
        self.assertEqual(result["studio"], "7.10")
        self.assertEqual(result["assignment_type"], "Generic")
        self.assertEqual(result["game"], "BJ/TP/RW/VIP/MW")
