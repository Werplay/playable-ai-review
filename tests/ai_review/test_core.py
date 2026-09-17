import json
import tempfile
import unittest
from pathlib import Path

from tools.ai_review.core import (cosine, deserialize_vector, evidence_occurs,
    json_objects, normalize_evidence, redact, serialize_vector)
from tools.ai_review.git import collect


class CoreTests(unittest.TestCase):
    def test_vector_round_trip_and_similarity(self):
        v=[1.0,2.0,3.0]
        self.assertEqual(deserialize_vector(serialize_vector(v),3),v)
        self.assertAlmostEqual(cosine(v,v),1.0)
        self.assertEqual(cosine(v,[0,0,0]),0)

    def test_evidence_normalizes_whitespace(self):
        self.assertTrue(evidence_occurs("foo( a, b )", "x\n foo(  a,\n b )\n"))
        self.assertFalse(evidence_occurs("invented()", "real()"))

    def test_secret_redaction(self):
        value="api_key = super-secret-value token: abcdefghijklmnopqrstuvwxyz"
        output=redact(value)
        self.assertNotIn("super-secret-value",output)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz",output)

    def test_json_plain_fenced_and_incomplete(self):
        self.assertEqual(json_objects('{"findings":[]}'),{"findings":[]})
        self.assertEqual(json_objects('```json\n{"findings":[]}\n```'),{"findings":[]})
        self.assertEqual(json_objects('prefix [{"x":1}'),[{"x":1}])
        with self.assertRaises(ValueError): json_objects("not json")

    def test_diff_modes_and_spaces(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); subprocess.run(["git","init","-q"],cwd=root,check=True)
            subprocess.run(["git","config","user.email","test@example.test"],cwd=root,check=True)
            subprocess.run(["git","config","user.name","Test"],cwd=root,check=True)
            (root/"a file.py").write_text("x=1\n")
            subprocess.run(["git","add","."],cwd=root,check=True); subprocess.run(["git","commit","-qm","base"],cwd=root,check=True)
            (root/"a file.py").write_text("x=2\n")
            files=collect(root,"HEAD",False,None)
            self.assertEqual(files[0].path,"a file.py"); self.assertIn("x=2",files[0].proposed)
            subprocess.run(["git","add","."],cwd=root,check=True)
            (root/"a file.py").write_text("x=3\n")
            self.assertIn("x=2",collect(root,None,True,None)[0].proposed)

    def test_binary_marker_inside_source_is_not_binary(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); subprocess.run(["git","init","-q"],cwd=root,check=True)
            subprocess.run(["git","config","user.email","test@example.test"],cwd=root,check=True)
            subprocess.run(["git","config","user.name","Test"],cwd=root,check=True)
            (root/"marker.py").write_text('marker = "GIT binary patch"\n')
            subprocess.run(["git","add","."],cwd=root,check=True)
            files=collect(root,None,True,None)
            self.assertEqual(len(files),1); self.assertFalse(files[0].binary)


if __name__ == "__main__": unittest.main()
