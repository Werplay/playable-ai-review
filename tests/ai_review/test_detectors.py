import unittest

from tools.ai_review.core import ChangedFile
from tools.ai_review.detectors import detect, detect_group

PATTERNS = {
 "async":"items.forEach(async (x) => { await save(x); });",
 "boundary":"const x = items.slice(0, items.length - 1);",
 "open_redirect":"if (redirect.startsWith('/')) location.href = redirect;",
 "authorization":"if (isAdmin || tenant === user.tenant) allow();",
 "validation":"if (reservedNames.includes(name)) fail();",
 "xss":"return <div dangerouslySetInnerHTML={{__html: props.content}} />;",
 "mass_assignment":"model.update(req.body)",
 "boolean_default":"const x = { enabled: input.enabled || true };",
 "time_units":"if (Date.now() - createdAt > timeout) expire();",
 "comparator":"items.sort((a,b) => a.x > b.x ? 1 : 0);",
 "regex_injection":"const r = new RegExp(input);",
 "path_traversal":"const p = path.resolve(root, request.params.path);",
 "csv_injection":"const cell = quoteCsv(input);",
 "cleanup":"addEventListener('x', () => go()); removeEventListener('x', () => go());",
 "mutation":"items.forEach(x => { items.splice(0, 1); });",
 "retry_budget":"for (let i=0; i <= maxAttempts; i++) run();",
}

class DetectorTests(unittest.TestCase):
    def test_major_patterns(self):
        for category,code in PATTERNS.items():
            with self.subTest(category=category):
                found=detect(ChangedFile("x.ts","M",proposed=code,patch="+"+code))
                self.assertTrue(any(f.category==category for f in found),[(f.category,f.evidence) for f in found])

    def test_cache_scope(self):
        code="function load(tenantId, id) { return cache.get(id); }"
        self.assertTrue(any(f.category=="cache_scope" for f in detect(ChangedFile("x.ts","M",proposed=code))))

    def test_error_fallback(self):
        code='try { await work(); } catch (e) { return {ok: true}; }'
        impl=ChangedFile("x.ts","M",proposed=code)
        test=ChangedFile("x.test.ts","M",proposed="await expect(run()).rejects.toThrow()")
        self.assertTrue(any(f.category=="error_propagation" for f in detect_group([impl,test])))
        self.assertFalse(any(f.category=="error_propagation" for f in detect(impl)))

    def test_semantic_reversals(self):
        f=ChangedFile("x.ts","M",proposed="const x=Math.max(a,b);",patch="-const x=Math.min(a,b);\n+const x=Math.max(a,b);")
        self.assertTrue(any(x.category=="semantic_reversal" for x in detect(f)))

    def test_correct_controls(self):
        correct="await Promise.all(items.map(async x => save(x))); items.sort((a,b)=>a.x-b.x); const enabled=input.enabled ?? true;"
        self.assertEqual(detect(ChangedFile("x.ts","M",proposed=correct)),[])

    def test_patterns_inside_fixture_strings_are_not_reported(self):
        fixture='PATTERNS = {"async": "items.forEach(async (x) => save(x))", "xss": "dangerouslySetInnerHTML={{__html: props.content}}"}'
        self.assertEqual(detect(ChangedFile("fixture.py","M",proposed=fixture)),[])

    def test_non_persistence_update_and_string_join_are_not_reported(self):
        code='values.update(kw); text = " ".join(path for path in paths)'
        self.assertEqual(detect(ChangedFile("helper.py","M",proposed=code)),[])


if __name__ == "__main__": unittest.main()
