"""Regression tests for bounded public download discovery."""

import unittest
from unittest.mock import patch

from flask import Flask

from Ligases import routes


class PublicDownloadManifestTests(unittest.TestCase):
    def _query_db(self, sql, args=(), one=False):
        normalized = " ".join(sql.split())
        if "SELECT DISTINCT Ligase FROM Recruiter_Instance_Catalog" in normalized:
            return [{"Ligase": "KEAP1"}, {"Ligase": "RNF146"}]
        if "FROM Recruiter_Instance_Catalog AS i" in normalized:
            ligases = [args[0]] if args else ["KEAP1", "RNF146"]
            return [{
                "Recruiter_ID": "LR00089",
                "Recruiter_Instance_ID": "LR00089-01",
                "Ligase": ligase,
                "pdb_id": "5FNU",
                "Ligand": "L6I",
                "Variant": 1,
            } for ligase in ligases]
        raise AssertionError(f"Unexpected query: {normalized}")

    def test_remote_manifest_uses_catalog_filenames_without_randy_probes(self):
        with patch.object(routes.randy_client, "remote_enabled", return_value=True), \
             patch.object(routes.randy_client, "file_exists", side_effect=AssertionError("no probes")), \
             patch.object(routes, "_active_release_is_r2", return_value=True), \
             patch.object(routes, "query_db", side_effect=self._query_db):
            manifest = routes.build_download_manifest()
            self.assertEqual(manifest["ligase_count"], 2)
            self.assertEqual(manifest["ligases"][0]["pdb_count"], 1)

            exact = routes.build_download_manifest(recruiter_code="LR00089")
            self.assertEqual(exact["entries"][0]["pdb_file"], "5FNU_L6I_1.pdb")
            self.assertTrue(exact["entries"][0]["sdf_download"].endswith("5FNU_L6I_1.sdf"))

    def test_remote_code_index_uses_catalog_filenames_without_randy_probes(self):
        app = Flask(__name__)
        with app.test_request_context("/?ligase=KEAP1&limit=25"), \
             patch.object(routes.randy_client, "remote_enabled", return_value=True), \
             patch.object(routes.randy_client, "file_exists", side_effect=AssertionError("no probes")), \
             patch.object(routes, "_active_release_is_r2", return_value=True), \
             patch.object(routes, "query_db", side_effect=self._query_db):
            response = routes.download_recruiter_code_index()
            body = response.get_json()
            self.assertEqual(body["count"], 1)
            self.assertEqual(body["results"][0]["pdb_file"], "5FNU_L6I_1.pdb")

    def test_remote_table_exports_stream_the_release_csv(self):
        app = Flask(__name__)
        with app.test_request_context("/"), \
             patch.object(routes.randy_client, "remote_enabled", return_value=True), \
             patch.object(routes.randy_client, "proxy_file", return_value="streamed") as proxy, \
             patch.object(routes, "query_db", side_effect=AssertionError("no SQL materialization")):
            self.assertEqual(routes.download_table_csv("Ligase_Ligand_SASA_atoms"), "streamed")
            proxy.assert_called_once_with(
                "download/table/Ligase_Ligand_SASA_atoms.csv",
                download_name="E3Ligandalyzer_Ligase_Ligand_SASA_atoms.csv",
                mimetype="text/csv",
            )

    def test_remote_table_export_falls_back_only_when_csv_is_not_published(self):
        app = Flask(__name__)
        with app.test_request_context("/"), \
             patch.object(routes.randy_client, "remote_enabled", return_value=True), \
             patch.object(routes.randy_client, "proxy_file", side_effect=routes.randy_client.RemoteServiceError("missing", status_code=404)), \
             patch.object(routes, "query_db", return_value=[{"Recruiter_ID": "LR00001"}]):
            response = routes.download_table_csv("Recruiter_Instance_Catalog")
            self.assertEqual(response.status_code, 200)
            self.assertIn("LR00001", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
