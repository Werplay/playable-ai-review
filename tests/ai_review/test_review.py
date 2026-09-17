import unittest
from tools.ai_review.core import ChangedFile, Finding
from tools.ai_review.review import dedupe, evidence_gate
from tools.ai_review.report import verdict

def finding(**kw):
    values=dict(severity="high",category="async",file="src/a.ts",line=1,evidence="save(x);",scenario="fails",explanation="promise is lost",recommendation="await it")
    values.update(kw); return Finding(**values)

class ReviewTests(unittest.TestCase):
    def test_gate_rejects_invention_and_contradiction(self):
        files={"src/a.ts":ChangedFile("src/a.ts","M",proposed="save(x);")}
        kept,rejected=evidence_gate([finding(),finding(evidence="fake()"),finding(explanation="already awaited; no change needed")],files)
        self.assertEqual(len(kept),1); self.assertEqual(len(rejected),2)

    def test_dedupe_prefers_deterministic(self):
        a=finding(source="model"); b=finding(source="deterministic")
        values,count=dedupe([a,b]); self.assertEqual(count,1); self.assertEqual(values[0].source,"deterministic")

    def test_implementation_test_pair_dedupe(self):
        a=finding(evidence="save tenant record failed")
        b=finding(file="tests/a.test.ts",evidence="expect save tenant record failed")
        values,count=dedupe([a,b]); self.assertEqual(count,1); self.assertEqual(len(values),1)

    def test_unverified_candidate_does_not_claim_confirmed_risk(self):
        item=finding(severity="critical",classification="needs_human_review")
        self.assertEqual(verdict([item]),"human review required (critical candidate)")

if __name__ == "__main__": unittest.main()
