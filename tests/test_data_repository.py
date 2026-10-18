import tempfile
import unittest
from pathlib import Path

from crisismap.data_repository import bundled_dataset, load_geojson, pune_dataset, procedural_dataset


class DataRepositoryTests(unittest.TestCase):
    def test_bundled_dataset_has_searchable_places(self):
        dataset = bundled_dataset()
        self.assertGreaterEqual(len(dataset.locations), 5)
        self.assertEqual(dataset.name, "Rivermark Offline Demo")

    def test_pune_dataset_loads_real_wards(self):
        dataset = pune_dataset()
        # 58 wards + 1 MIT-WPU Kothrud point feature
        self.assertEqual(len(dataset.features), 59)
        self.assertGreaterEqual(len(dataset.locations), 50)
        self.assertIn("Pune", dataset.name)
        names = [loc.name for loc in dataset.locations]
        self.assertIn("Dhanori - Vishrantwadi", names)
        self.assertIn("Katraj - Gokulnagar", names)
        self.assertIn("MIT-WPU Kothrud", names)

    def test_procedural_dataset_is_deterministic(self):
        first = procedural_dataset(seed=123, size=3)
        second = procedural_dataset(seed=123, size=3)
        self.assertEqual(first.features, second.features)
        self.assertEqual(len(first.features), 9)

    def test_invalid_geojson_is_rejected(self):
        # Keep test artifacts in the project so this also works in an air-gapped
        # or filesystem-sandboxed classroom environment.
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / "bad.json"
            path.write_text('{"type":"Point"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_geojson(path)


if __name__ == "__main__":
    unittest.main()
