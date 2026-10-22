
import unittest

from barrioiq_pipeline.quality import (
    DataQualityError,
    profile_bronze,
    validate_silver,
    summarize_gold,
)


VALID_ROWS = [
    {
        "codigo_area": "001",
        "distrito": "Centro",
        "populacao": 100,
        "renda_media": 3000,
    },
    {
        "codigo_area": "002",
        "distrito": "Centro",
        "populacao": 200,
        "renda_media": 4000,
    },
    {
        "codigo_area": "003",
        "distrito": "Norte",
        "populacao": 150,
        "renda_media": 2500,
    },
]


class TestBarrioIQQuality(unittest.TestCase):

    def test_bronze_profiles_invalid_records(self):
        rows = VALID_ROWS + [
            {"codigo_area": "001"},
            {"codigo_area": None},
        ]
        result = profile_bronze(rows)

        self.assertEqual(result["total_records"], 5)
        self.assertEqual(result["missing_keys"], 1)
        self.assertEqual(result["duplicate_keys"], 1)

    def test_silver_accepts_valid_data(self):
        result = validate_silver(VALID_ROWS)
        self.assertEqual(len(result), 3)

    def test_silver_rejects_null_key(self):
        rows = [dict(VALID_ROWS[0], codigo_area=None)]
        with self.assertRaises(DataQualityError):
            validate_silver(rows)

    def test_silver_rejects_duplicates(self):
        rows = VALID_ROWS + [VALID_ROWS[0].copy()]
        with self.assertRaises(DataQualityError):
            validate_silver(rows)

    def test_silver_rejects_negative_population(self):
        rows = [dict(VALID_ROWS[0], populacao=-10)]
        with self.assertRaises(DataQualityError):
            validate_silver(rows)

    def test_silver_rejects_invalid_income(self):
        rows = [dict(VALID_ROWS[0], renda_media=-100)]
        with self.assertRaises(DataQualityError):
            validate_silver(rows)

    def test_gold_preserves_population_totals(self):
        gold = summarize_gold(VALID_ROWS)

        self.assertEqual(gold["Centro"]["areas"], 2)
        self.assertEqual(gold["Centro"]["population"], 300)

        total_gold = sum(
            item["population"] for item in gold.values()
        )
        total_silver = sum(
            row["populacao"] for row in VALID_ROWS
        )

        self.assertEqual(total_gold, total_silver)


if __name__ == "__main__":
    unittest.main()
