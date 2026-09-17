import json
import os
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from tools.ai_review.cli import main
from tools.ai_review.core import Usage


class FakeClient:
    model="fake-review"; embedding_model="fake-embed"
    def verify_models(self): pass
    def embed(self,texts): return [[float(len(x)%13+1),2.0,3.0] for x in texts]
    def generate_json(self,prompt,num_predict=4096):
        if "skeptical verifier" in prompt: return {"results":[]},Usage(10,2,100)
        return {"findings":[]},Usage(20,3,100)

@contextmanager
def cd(path):
    old=os.getcwd(); os.chdir(path)
    try: yield
    finally: os.chdir(old)

class DryRunTests(unittest.TestCase):
    def test_mocked_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); subprocess.run(["git","init","-q"],cwd=root,check=True)
            subprocess.run(["git","config","user.email","test@example.test"],cwd=root,check=True); subprocess.run(["git","config","user.name","Test"],cwd=root,check=True)
            (root/"app.ts").write_text("export const value = 1;\n"); subprocess.run(["git","add","."],cwd=root,check=True); subprocess.run(["git","commit","-qm","base"],cwd=root,check=True)
            (root/"app.ts").write_text("export const value = 2;\n")
            old=os.environ.get("AI_REVIEW_INDEX_DIR"); os.environ["AI_REVIEW_INDEX_DIR"]=str(root/"cache")
            try:
                with cd(root): code=main(["--base","HEAD","--output",str(root/"report")],client_factory=FakeClient)
            finally:
                if old is None: os.environ.pop("AI_REVIEW_INDEX_DIR",None)
                else: os.environ["AI_REVIEW_INDEX_DIR"]=old
            self.assertEqual(code,0); self.assertTrue((root/"report/report.md").exists())
            data=json.loads((root/"report/report.json").read_text()); self.assertEqual(data["coverage"]["reviewed"],1)

if __name__ == "__main__": unittest.main()
