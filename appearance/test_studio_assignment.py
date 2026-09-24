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
