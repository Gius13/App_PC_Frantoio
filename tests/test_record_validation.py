"""Test di regressione per le modifiche alle moliture.

Esecuzione dalla directory padre di app_frantoio:
python -m unittest discover -s app_frantoio/tests -v
"""
import unittest
from app_frantoio.core.record_validation import validate_record_changes


class RecordValidationTests(unittest.TestCase):
    def setUp(self):
        self.original = {
            "id": "-firebase-push-id",
            "_source": "firebase",
            "name": "Mario Rossi",
            "weight": 200.0,
            "abbuono": 2.0,
            "pagamento": "POS",
            "dataOra": 1793952000000,
        }

    def test_partial_change(self):
        self.assertEqual(
            validate_record_changes(self.original, {"name": "Mario Bianchi"}),
            {"name": "Mario Bianchi"},
        )

    def test_no_changes(self):
        self.assertEqual(validate_record_changes(self.original, {
            "name": "Mario Rossi", "weight": 200, "pagamento": "POS"
        }), {})

    def test_decimal_comma(self):
        self.assertEqual(
            validate_record_changes(self.original, {"weight": "240,5"}),
            {"weight": 240.5},
        )

    def test_invalid_weight(self):
        for value in [-2, 0, float("nan"), float("inf"), "testo"]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_record_changes(self.original, {"weight": value})

    def test_id_is_not_editable(self):
        with self.assertRaises(ValueError):
            validate_record_changes(self.original, {"id": "different"})

    def test_invalid_discount(self):
        with self.assertRaises(ValueError):
            validate_record_changes(self.original, {"abbuono": -1})

    def test_invalid_timestamp(self):
        with self.assertRaises(ValueError):
            validate_record_changes(self.original, {"dataOra": -1})

    def test_alias_fields(self):
        aliased = {"nome": "Luigi", "peso": 30.0}
        self.assertEqual(validate_record_changes(aliased, {"name": "Luigi"}), {})
        self.assertEqual(validate_record_changes(aliased, {"weight": 31}), {"weight": 31.0})


if __name__ == "__main__":
    unittest.main()
