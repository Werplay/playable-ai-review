import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.ai_review.core import SCHEMA_VERSION
from tools.ai_review.index import RepositoryIndex


class Embedder:
    embedding_model="fake-embed"
    def __init__(self): self.calls=[]
    def embed(self,texts):
        self.calls.extend(texts)
        return [[float(len(x)),float(x.count("a")+1),1.0] for x in texts]


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        subprocess.run(["git","init","-q"],cwd=self.root,check=True)
        (self.root/"a.py").write_text("def alpha():\n    return 1\n")
        (self.root/"delete.py").write_text("gone=True\n")
        subprocess.run(["git","add","."],cwd=self.root,check=True)
        self.embed=Embedder(); self.db=self.root/"cache.sqlite3"; self.index=RepositoryIndex(self.root,self.db,self.embed.embed)
    def tearDown(self): self.tmp.cleanup()

    def test_initial_schema_and_incremental_reuse(self):
        first=self.index.update(); self.assertEqual(first.files,2); self.assertEqual(first.embedded,2)
        calls=len(self.embed.calls); second=self.index.update()
        self.assertEqual(second.embedded,0); self.assertEqual(second.reused,2); self.assertEqual(len(self.embed.calls),calls)
        with sqlite3.connect(self.db) as con:
            self.assertEqual(int(con.execute("select value from metadata where key='schema_version'").fetchone()[0]),SCHEMA_VERSION)
            text,model,dims=con.execute("select text,embedding_model,dimensions from chunks limit 1").fetchone()
            self.assertTrue(text); self.assertEqual(model,"fake-embed"); self.assertEqual(dims,3)

    def test_changed_and_deleted_reindex(self):
        self.index.update(); (self.root/"a.py").write_text("def alpha():\n    return 2\n"); (self.root/"delete.py").unlink()
        subprocess.run(["git","rm","--cached","delete.py"],cwd=self.root,check=True,stdout=subprocess.DEVNULL)
        stats=self.index.update(); self.assertEqual(stats.embedded,1); self.assertEqual(stats.deleted,1)
        with sqlite3.connect(self.db) as con: self.assertEqual(con.execute("select count(*) from chunks where path='delete.py'").fetchone()[0],0)

    def test_retrieval(self):
        self.index.update(); results=self.index.retrieve("alpha",[10,2,1],{"other.py"})
        self.assertEqual(results[0]["path"],"a.py")


if __name__ == "__main__": unittest.main()
