from __future__ import annotations

import re
from collections.abc import Callable

from .core import ChangedFile, Finding


def _finding(file: ChangedFile, category: str, severity: str, evidence: str, explanation: str, recommendation: str, scenario: str = "The changed path is exercised with boundary or attacker-controlled input.") -> Finding:
    line = file.proposed[:file.proposed.find(evidence)].count("\n") + 1 if evidence in file.proposed else 1
    return Finding(severity, category, file.path, line, evidence.strip(), scenario, explanation, recommendation, source="deterministic", classification="verified", confidence="high")


def _matches(pattern: str, text: str, flags=re.M|re.S):
    """Return matches beginning in code, not inside quoted fixture/data strings."""
    masked = _string_mask(text)
    return [match for match in re.finditer(pattern, text, flags) if not masked[match.start()]]


def _string_mask(text: str) -> list[bool]:
    """A small language-neutral lexer marking quoted strings while preserving offsets."""
    mask = [False] * max(1, len(text))
    i = 0
    while i < len(text):
        quote = None
        if text.startswith(('"""', "'''"), i): quote = text[i:i+3]
        elif text[i] in "'\"`": quote = text[i]
        if not quote:
            i += 1; continue
        start = i; i += len(quote)
        while i < len(text):
            if text[i] == "\\": i += 2; continue
            if text.startswith(quote, i): i += len(quote); break
            i += 1
        for pos in range(start, min(i, len(mask))): mask[pos] = True
    return mask


def detect(file: ChangedFile) -> list[Finding]:
    s = file.proposed; out: list[Finding] = []
    rules: list[tuple[str,str,str,str,str]] = [
      (r"\.forEach\s*\(\s*async\s*(?:\([^)]*\)|\w+)\s*=>", "async", "high", "Async forEach callbacks are not awaited; the enclosing operation can finish before their work.", "Use for…of with await, or await Promise.all(map(...))."),
      (r"\.slice\s*\([^,]+,\s*[^)]*\.length\s*-\s*1\s*\)", "boundary", "medium", "slice has an exclusive end, so subtracting one drops an additional element.", "Use the intended exclusive end directly."),
      (r"(?:redirect|location|returnUrl|nextUrl)[^\n]{0,100}(?:startsWith\(['\"]\/['\"]\)|^/)", "open_redirect", "high", "A leading-slash URL check also accepts protocol-relative URLs such as //evil.example.", "Parse the URL and reject values beginning with // or with a foreign origin."),
      (r"(?m)^\s*(?!await\b|return\b)(?:(?:db|repo(?:sitory)?|model|record|entity|store)\.\w+\.(?:save|create|update|delete|insert|persist)|(?:db|repo(?:sitory)?|model|record|entity|store)\.(?:save|create|update|delete|insert|persist)|\w+\.save)\s*\([^;\n]*\)\s*;", "async", "high", "A persistence-like call is not awaited or returned, so failures and ordering are lost.", "Await or return the persistence promise."),
      (r"(?:role|isAdmin|admin)[^\n]{0,80}\|\|[^\n]{0,80}(?:tenant|workspace|owner|organi[sz]ation|project)", "authorization", "critical", "OR permits either privilege or resource scope alone where both appear required.", "Require both independent authorization conditions with &&."),
      (r"(?:reserved|forbidden|blocked)(?:Names?)?\.(?:includes|has)\s*\(\s*\w+\s*\)", "validation", "medium", "Reserved-name lookup uses raw input without visible normalization.", "Normalize both input and reserved values consistently before comparison."),
      (r"dangerouslySetInnerHTML\s*=\s*\{\s*\{\s*__html:\s*(?:props\.|\w*(?:input|content|html|message|description))", "xss", "critical", "User-controlled content reaches dangerouslySetInnerHTML without visible sanitization.", "Render as text or sanitize with a strict allowlist."),
      (r"(?:create|update|assign)\s*\([^\n]*(?:req\.body|request\.body|input|payload)\s*\)", "mass_assignment", "critical", "An entire caller-controlled object is passed into persistence, allowing privileged fields.", "Allowlist assignable fields explicitly."),
      (r"\b(?:enabled|active|visible|disabled|is[A-Z]\w*)\s*:\s*[^,\n]+\s*\|\|", "boolean_default", "medium", "Boolean update uses ||, so an explicit false is replaced.", "Use ?? for optional boolean defaults."),
      (r"(?:Date\.now\(\)|getTime\(\))\s*-\s*\w+\s*[<>]=?\s*\w*(?:ttl|timeout|age|expiry|expires)\w*(?!\s*\*\s*1000)", "time_units", "high", "Millisecond timestamps are compared with a duration that appears to be seconds.", "Convert values to the same documented unit."),
      (r"\.sort\s*\(\s*\([^)]*\)\s*=>\s*[^?\n]+\?\s*(?:0|1)\s*:\s*(?:0|1)\s*\)", "comparator", "high", "Comparator never returns a negative value and cannot define a valid ordering.", "Return negative, zero, or positive values consistently."),
      (r"new\s+RegExp\s*\(\s*(?:req\.|request\.|input|query|pattern|search)", "regex_injection", "high", "Caller input is interpreted as a regular expression.", "Escape literal input or validate a deliberately supported regex syntax."),
      (r"(?:\bpath\.(?:join|resolve)|\bos\.path\.join|\.joinpath)\s*\([^\n]*(?:req\.|request\.|input|params|query|filename|userPath)", "path_traversal", "critical", "Caller-controlled path data is resolved without a visible containment check.", "Resolve canonically and verify the result remains beneath the allowed root."),
      (r"(?:escape|quote)[A-Za-z]*\s*\([^)]*\)(?![^\n]*(?:^[=+@-]|formula|neutral))", "csv_injection", "high", "CSV quoting does not neutralize spreadsheet formula prefixes.", "Prefix cells beginning with =, +, -, or @ before CSV quoting."),
      (r"addEventListener\s*\([^,]+,\s*\([^)]*\)\s*=>[\s\S]{0,300}removeEventListener\s*\([^,]+,\s*\([^)]*\)\s*=>", "cleanup", "high", "Removal uses a different callback object, so the listener remains installed.", "Store one callback reference and pass it to both calls."),
      (r"(\w+)\.forEach\s*\([^)]*=>[\s\S]{0,250}\1\.splice\s*\(", "mutation", "high", "The array is spliced while being traversed forward by forEach, which skips elements.", "Filter into a new array or iterate backwards."),
      (r"for\s*\([^;]*;\s*\w+\s*<=\s*(?:max)?(?:Attempts|Retries|attempts|retries)", "retry_budget", "medium", "Inclusive retry bound performs one more attempt than the configured count.", "Use a strict less-than bound or rename the configuration to retries."),
    ]
    for pattern, category, severity, explanation, recommendation in rules:
        for m in _matches(pattern, s): out.append(_finding(file,category,severity,m.group(0),explanation,recommendation))

    # Scope-sensitive cache detector.
    params = re.search(r"(?:function\s+\w+|\([^)]*\)\s*=>|\w+)\s*\(([^)]*(?:tenant|workspace|organization|project)[^)]*)\)", s, re.I)
    for m in _matches(r"(?:cache\.(?:get|set)|redis\.(?:get|set))\s*\(([^,\n]+)", s):
        if params and not re.search(r"tenant|workspace|organization|project", m.group(1), re.I):
            out.append(_finding(file,"cache_scope","high",m.group(0),"Cache key omits an available resource-scope parameter and can collide across tenants.","Include the tenant/workspace/organization/project identifier in the key."))
    # Normalization mismatch and common semantic reversals.
    if re.search(r"toLowerCase\(\)|toUpperCase\(\)", file.base) and not re.search(r"toLowerCase\(\)|toUpperCase\(\)", s):
        out.append(_finding(file,"contract","high",next((ln for ln in s.splitlines() if "name" in ln.lower()), s[:80]),"Normalization present in the base contract was removed on one side.","Apply the same normalization at client and server boundaries."))
    reversals = [("Math.min", "Math.max"), (".some(", ".every("), (" / ", " * "), (" && ", " || "), ("[0]", "[1]"), (" < ", " > ")]
    patch_added = "\n".join(x[1:] for x in file.patch.splitlines() if x.startswith("+") and not x.startswith("+++"))
    patch_removed = "\n".join(x[1:] for x in file.patch.splitlines() if x.startswith("-") and not x.startswith("---"))
    for old,new in reversals:
        if old in patch_removed and new in patch_added:
            evidence = next((ln.strip() for ln in patch_added.splitlines() if new in ln), new)
            out.append(_finding(file,"semantic_reversal","high",evidence,f"The diff reverses {old} to {new}, changing boundary semantics.","Confirm the intended invariant and restore the original operator if accidental."))
    return out


def detect_group(files: list[ChangedFile], contract_files: list[ChangedFile] | None = None) -> list[Finding]:
    """Cross-file detector where tests are necessary contract evidence."""
    out = [finding for file in files for finding in detect(file)]
    contracts = contract_files if contract_files is not None else files
    rejection_contract = any(_matches(r"\.rejects\b|rejects\.to", f.proposed) for f in contracts if "test" in f.path.lower() or "spec" in f.path.lower())
    if rejection_contract:
        for file in files:
            if "test" in file.path.lower() or "spec" in file.path.lower(): continue
            matches = _matches(r'catch\s*\([^)]*\)\s*\{[^}]*return\s+(?:true|\{|\")[^;]*', file.proposed)
            if matches:
                match = matches[0]
                out.append(_finding(file,"error_propagation","high",match.group(0),"A caught failure is converted into fallback success while a related changed test expects rejection.","Propagate the caught failure to preserve the rejection contract."))
    return out
