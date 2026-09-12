import hashlib
import unittest
from pathlib import Path

from e3_database import E3Database, configured_database_path
from Ligase_app import flask_app


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class V1DatabaseMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = E3Database()
        cls.client = flask_app.test_client()

    def test_v1_database_opens_and_has_release_metadata(self):
        metadata = self.database.release_metadata()
        self.assertEqual(metadata["Release_Version"], "1.0")
        self.assertEqual(metadata["Release_Date"], "2026-09-09")
        self.assertEqual(metadata["Database_Cutoff_Date"], "2026-05-08")

    def test_release_counts_match_v1_contract(self):
        self.assertEqual(self.database.release_counts(), {
            "recruiter_entities": 345,
            "recruiter_instances": 820,
            "scaffolds": 244,
            "ligase_recruiter_rows": 353,
            "ligase_scaffold_rows": 254,
            "ligases": 32,
            "distinct_pdbs": 371,
            "sasa_atoms": 33047,
            "mapped_atoms": 26716,
            "source_crosswalk_rows": 345,
            "source_ambiguity_rows": 0,
        })

    def test_real_multi_instance_recruiter_keeps_all_instances(self):
        instances = self.database.recruiter_instances("LR00172")
        self.assertGreater(len(instances), 1)
        self.assertTrue(all(row["Recruiter_ID"] == "LR00172" for row in instances))
        self.assertEqual(len({row["Recruiter_Instance_ID"] for row in instances}), len(instances))

    def test_exact_instance_links_only_to_its_entity(self):
        instance = self.database.recruiter_instance("LR00172-01")
        self.assertIsNotNone(instance)
        self.assertEqual(instance["Recruiter_ID"], "LR00172")
        self.assertEqual(instance["Recruiter_Instance_ID"], "LR00172-01")
        self.assertEqual(
            self.database.recruiter_entity(instance["Recruiter_ID"])["Recruiter_ID"],
            "LR00172",
        )

    def test_entity_relationships_scaffold_sasa_and_mapping_are_available(self):
        entity = self.database.recruiter_entity("LR00172")
        self.assertTrue(self.database.entity_ligases(entity["Recruiter_ID"]))
        self.assertIsNotNone(self.database.scaffold(entity["Scaffold_ID"]))
        self.assertIsNotNone(self.database.instance_sasa_summary("LR00172-01"))
        self.assertTrue(self.database.instance_sasa_atoms("LR00172-01"))
        self.assertTrue(self.database.instance_atom_mapping("LR00172-01"))

    def test_search_distinguishes_entities_from_instances_and_pdbs(self):
        entity_search = self.database.search_recruiters("LR00172")
        self.assertTrue(any(r["Recruiter_ID"] == "LR00172" for r in entity_search["entities"]))
        instance_search = self.database.search_recruiters("LR00172-01")
        self.assertTrue(any(r["Recruiter_Instance_ID"] == "LR00172-01" for r in instance_search["instances"]))
        pdb_search = self.database.search_recruiters("4W9E")
        self.assertTrue(pdb_search["instances"])

    def test_core_routes_render_and_return_v1_results(self):
        for path in [
            "/api/release-info",
            "/api/recruiters/LR00172",
            "/api/recruiters/LR00172/instances",
            "/api/recruiters/LR00172/render-2d",
            "/api/instances/LR00172-01",
            "/api/instances/LR00172-01/sasa",
            "/api/instances/LR00172-01/sasa-atoms",
            "/api/instances/LR00172-01/mapped-atoms",
            "/api/instances/LR00172-01/visual",
            "/api/instances/LR00172-01/pdb",
            "/api/instances/LR00172-01/sdf",
            "/api/instances/LR00172-01/render-2d-sasa",
            "/api/search/recruiters?q=4W9E",
            "/recruiter/LR00172",
            "/scaffolds/SCF00001",
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                try:
                    self.assertEqual(response.status_code, 200)
                finally:
                    response.close()
        redirect = self.client.get("/ligand/LR00172", follow_redirects=False)
        self.assertEqual(redirect.status_code, 302)
        self.assertEqual(redirect.headers["Location"], "/recruiter/LR00172")

        instance_redirect = self.client.get("/instance/LR00172-01", follow_redirects=False)
        self.assertEqual(instance_redirect.status_code, 302)
        self.assertEqual(instance_redirect.headers["Location"], "/ligand/LR00172-01")

        exact = self.client.get("/ligand/LR00172-01")
        self.assertEqual(exact.status_code, 200)
        self.assertIn(b"instance-selector", exact.data)

    def test_exact_visual_payload_keeps_suffixed_instance_assets(self):
        payload = self.client.get("/api/instances/LR00001-03/visual").get_json()
        self.assertEqual(payload["recruiter"]["Recruiter_ID"], "LR00001")
        self.assertEqual(payload["instance"]["Recruiter_Instance_ID"], "LR00001-03")
        self.assertEqual(payload["assets"]["pdb"]["filename"], "4W9E_3JT_3.pdb")
        self.assertEqual(payload["assets"]["sdf"]["filename"], "4W9E_3JT_3.sdf")
        self.assertTrue(payload["assets"]["pdb"]["url"].endswith("/LR00001-03/pdb"))
        self.assertTrue(payload["assets"]["sdf"]["url"].endswith("/LR00001-03/sdf"))

        # Even generic local compatibility paths no longer substitute _1 or a
        # sibling when an exact V1 filename is absent.
        self.assertEqual(
            self.client.get("/api/Ligases/VHL/PDB/4W9E_3JT_99.pdb").status_code,
            404,
        )
        self.assertEqual(
            self.client.get("/api/render-sdf/VHL/4W9E_3JT_99.sdf").status_code,
            404,
        )

    def test_multi_ligase_entity_exposes_each_exact_sibling(self):
        payload = self.client.get("/api/instances/LR00026-01/visual").get_json()
        siblings = payload["siblings"]
        self.assertEqual({row["Recruiter_Instance_ID"] for row in siblings}, {"LR00026-01", "LR00026-02", "LR00026-03"})
        self.assertEqual({row["Ligase"] for row in siblings}, {"cIAP1", "LIVIN"})

    def test_problematic_sasa_payloads_have_one_exact_overlay_atom_per_mapping(self):
        """Reported bad pages have clean V1 rows and a deterministic overlay contract."""
        for instance_id, expected_count in (("LR00220-01", 37), ("LR00215-02", 34)):
            with self.subTest(instance=instance_id):
                payload = self.client.get(f"/api/instances/{instance_id}/visual").get_json()
                self.assertEqual(payload["instance"]["Recruiter_Instance_ID"], instance_id)
                self.assertEqual(len(payload["sasa_atoms"]), expected_count)
                self.assertEqual(len(payload["mapped_atoms"]), expected_count)
                self.assertEqual(len(payload["sasa_overlay_atoms"]), expected_count)
                diagnostics = payload["sasa_overlay_diagnostics"]
                self.assertEqual(diagnostics["unmapped_sasa_atom_ids"], [])
                self.assertEqual(diagnostics["duplicate_mapping_keys"], [])
                keys = [
                    (row["atom_id"], row["instance_sdf_atom_index"])
                    for row in payload["sasa_overlay_atoms"]
                ]
                self.assertEqual(len(keys), len(set(keys)))

    def test_recruiter_page_has_entity_level_2d_depiction(self):
        page = self.client.get("/recruiter/LR00319")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'id="recruiter-2d-depiction"', page.data)
        self.assertIn(b"/api/recruiters/LR00319/render-2d", page.data)

        depiction = self.client.get("/api/recruiters/LR00319/render-2d")
        self.assertEqual(depiction.status_code, 200)
        self.assertEqual(depiction.mimetype, "image/svg+xml")
        self.assertIn(b"<svg", depiction.data)
        # Heteroatom labels use the readable dark-theme scientific palette.
        self.assertIn(b"#21D3ED", depiction.data.upper())
        self.assertIn(b"#F77070", depiction.data.upper())

    def test_entity_ligand_url_redirects_to_overview_without_selecting_an_instance(self):
        response = self.client.get("/ligand/LR00215", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/recruiter/LR00215")

    def test_viewer_source_has_render_generation_and_overlay_deduplication(self):
        source = (ROOT / "templates" / "ligand.html").read_text()
        self.assertIn("renderGeneration = ++current3D.renderGeneration", source)
        self.assertIn("const renderedAtomKeys = new Set()", source)
        self.assertIn("sasa_overlay_atoms", source)

    def test_random_recruiter_returns_a_real_exact_v1_instance(self):
        response = self.client.get("/api/random-recruiter")
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        instance_id = result["recruiter_instance_id"]
        self.assertTrue(instance_id.startswith("LR"))
        self.assertIn("-", instance_id)
        self.assertEqual(result["url"], f"/ligand/{instance_id}")
        self.assertIsNotNone(self.database.recruiter_instance(instance_id))

        navbar = (ROOT / "static" / "components" / "navbar.js").read_text()
        self.assertIn('fetch("/api/random-recruiter")', navbar)
        self.assertNotIn('const num = Math.floor(Math.random() * 603)', navbar)

    def test_all_v1_instance_assets_are_served_by_exact_instance_routes(self):
        """Guard against reintroducing basename/variant fallback in the viewer API."""
        instances = self.database.execute_read(
            "SELECT Recruiter_Instance_ID, Ligase, Step4_PDB, Source_SDF "
            "FROM Recruiter_Instance_Catalog ORDER BY Recruiter_Instance_ID"
        )
        self.assertEqual(len(instances), 820)
        for row in instances:
            for kind, column, folder in (
                ("pdb", "Step4_PDB", "PDB"),
                ("sdf", "Source_SDF", "SDF_4Download"),
            ):
                expected = ROOT / "Ligases" / row["Ligase"] / folder / Path(row[column]).name
                with self.subTest(instance=row["Recruiter_Instance_ID"], asset=kind):
                    self.assertTrue(expected.is_file())
                    response = self.client.get(
                        f"/api/instances/{row['Recruiter_Instance_ID']}/{kind}"
                    )
                    try:
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(sha256(expected), hashlib.sha256(response.data).hexdigest())
                    finally:
                        response.close()

    def test_migrated_data_layer_never_mentions_obsolete_instance_alias(self):
        for path in [ROOT / "e3_database.py", ROOT / "Ligase_app.py", ROOT / "Ligases/routes.py"]:
            self.assertNotIn("RECRUITER_INSTANCE_ID", path.read_text())

    def test_normal_requests_do_not_mutate_release_database(self):
        database_path = configured_database_path()
        before = sha256(database_path)
        for path in ["/api/release-info", "/api/ligases", "/api/recruiters/LR00172"]:
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(sha256(database_path), before)


if __name__ == "__main__":
    unittest.main()
