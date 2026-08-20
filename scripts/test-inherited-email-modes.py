#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Force the three inherited modes to fire, and force the two checks to disagree.

WHY THIS EXISTS
---------------
pdoom-data fixed its redactor on 2026-08-09 (12c0455) after ten records in its
public zone were found still carrying academics' addresses eight months after a
pass reported clean. THIS REPO NEVER INHERITED THAT FIX. Its EMAIL_PATTERN
carried the same three blind spots until 2026-08-15, and the only reason nothing
was being served in the meantime is luck: the daily sync happened to pull an
upstream corpus that had already been cleaned at source on 2026-08-10.

"Nothing is leaking right now" is not the same as "nothing can leak", and the
distance between them was one upstream regression.

The three modes, all consequences of the text being EXTRACTED FROM PDFs:

  (e) BRACE-GROUP NOTATION -- "{aaa,bbb,ccc}@institution.edu", several data
      subjects in ONE address. This was the highest-volume mode upstream and the
      one that actually shipped here. The old local part contained neither '{'
      nor ',', so no substring could reach the '@': the match failed SILENTLY.
  (f) WHITESPACE INSIDE THE DOMAIN -- "institution. edu", "cbs .dk",
      "uni -example.de", where the extractor broke a token.
  (g) WHITESPACE BEFORE THE '@' -- "{aaa, bbb} @institution.edu".

THE SECOND HALF, which is the part worth reading
------------------------------------------------
Widening a regex fixes three modes. It does not fix the reason those three modes
survived six days of green checks, which is that this repo had exactly ONE
definition of "what an address looks like" and used it for BOTH detection and
verification. redact_pii() removed what EMAIL_PATTERN matched, then
find_published_emails() verified with EMAIL_PATTERN, then
check-published-emails.py imported EMAIL_PATTERN, then count_emails() logged with
EMAIL_PATTERN. Four green results, one blind spot, and no way to see it from
inside.

So residue_scan() is built on a DIFFERENT PRINCIPLE -- it walks '@' CHARACTERS
and classifies their neighbourhoods -- and a disagreement REFUSES THE WRITE. The
decisive test below is not "does the new pattern match brace groups"; it is
"WITH THE OLD PATTERN RESTORED, does the independent scanner still see what the
pattern misses". If it does, the guard would have caught this class of defect
without anyone knowing the specific mode in advance. That is the property worth
having, and it is the only one that generalises to mode (h).

No real address appears in this file. Every fixture is fabricated.

Run: python scripts/test-inherited-email-modes.py
"""
import importlib.util
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_SYNC = os.path.join(_HERE, "sync", "sync-events.py")

_spec = importlib.util.spec_from_file_location("sync_events", _SYNC)
sync_events = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_events)

EMAIL_PATTERN = sync_events.EMAIL_PATTERN
residue_scan = sync_events.residue_scan
redact = sync_events.redact_emails_in_text
MARKER = sync_events.REDACTION_MARKER

# The pattern EXACTLY as it stood before this fix, so the regression test below
# is against the real historical artefact rather than a paraphrase of it.
OLD_EMAIL_PATTERN = re.compile(
    r"(?:mailto:)?"
    r"[A-Za-z0-9._%+\-]+"
    r"@"
    r"[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*"
    r"\.[A-Za-z][a-z]{1,23}"
)

failures = []


def check(label, condition):
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        failures.append(label)


# ---------------------------------------------------------------------------
print("\n[1] MODE (e): brace-group notation -- several people in one address")
# ---------------------------------------------------------------------------
BRACE = "{alpha,bravo,charlie}@example.edu"
check("the OLD pattern could not see it (this is the bug being fixed)",
      not OLD_EMAIL_PATTERN.search(BRACE))
check("the widened pattern matches it", bool(EMAIL_PATTERN.search(BRACE)))
check("redaction removes the whole group, leaving no fragment of a name",
      "alpha" not in redact(BRACE) and MARKER in redact(BRACE))
check("a line-wrapped group is still one match (the extractor wraps long lists)",
      bool(EMAIL_PATTERN.search("{alpha,bravo,\ncharlie}@example.edu")))

# ---------------------------------------------------------------------------
print("\n[2] MODE (f): whitespace inside the domain")
# ---------------------------------------------------------------------------
for label, s in [
    ("space after the dot", "firstname.lastname@example. edu"),
    ("space before the dot", "firstname.lastname@cbs .dk"),
    ("space around a hyphen", "firstname.lastname@uni -example.de"),
]:
    check(f"{label}: old pattern blind", not OLD_EMAIL_PATTERN.fullmatch(s))
    check(f"{label}: widened pattern matches", bool(EMAIL_PATTERN.search(s)))

# ---------------------------------------------------------------------------
print("\n[3] MODE (g): whitespace before the '@'")
# ---------------------------------------------------------------------------
G = "{alpha, bravo} @example.edu"
check("old pattern blind", not OLD_EMAIL_PATTERN.search(G))
check("widened pattern matches", bool(EMAIL_PATTERN.search(G)))

# ---------------------------------------------------------------------------
print("\n[4] THE LOWERCASE-TLD RULE IS PRESERVED -- ported, not copied")
# ---------------------------------------------------------------------------
# pdoom-data's rule ends [A-Za-z]{2,24}. Transplanting it here would eat the
# capitalised given name the PDF extractor glues onto the TLD, silently deleting
# a person's name from the page.
GLUED = "firstname.lastname@example.eduAleksandar"
m = EMAIL_PATTERN.search(GLUED)
check("the match stops at the capital, so the glued-on name survives",
      m is not None and m.group(0).endswith(".edu"))
check("and the name is still on the page after redaction",
      "Aleksandar" in redact(GLUED))

# The same rule is what keeps mode (f) from eating ordinary sentence breaks.
# Without it, our own footer address matches as "team@pdoom1.com. It", which the
# anchored allowlist rejects -- the guard would fire on the site's own contact
# address and no page could ever be written again.
SENTENCE = "Questions go to team@pdoom1.com. It usually replies within a day."
m2 = EMAIL_PATTERN.search(SENTENCE)
check("a sentence break is not swallowed into the domain",
      m2 is not None and m2.group(0) == "team@pdoom1.com")

# ---------------------------------------------------------------------------
print("\n[5] THE INDEPENDENT SCANNER STAYS SILENT ON EVERY NOTATION FAMILY")
# ---------------------------------------------------------------------------
# Measured against this repo's own published tree. A guard that fires on these
# is one a human mutes within a week, and a muted guard is worse than none.
for label, s in [
    ("BibTeX entry type", "@article{Smith2024, doi = {10.1234/x.y.z}}"),
    ("metric notation pass@k", "we report pass@k and Acc@100"),
    ("hardware string", "Intel Xeon @ 2.20GHz"),
    ("CSS at-rule", "@media (min-width: 40em) { .a { color: red } }"),
    ("bare social handle", "follow @someone for updates"),
    ("prose containing 'at'", "a paper aimed at arxiv.org readers"),
    ("our own contact address", "team@pdoom1.com"),
]:
    check(f"silent on {label}", residue_scan(s) == 0)

# ---------------------------------------------------------------------------
print("\n[6] THE DECISIVE ONE: the two checks are able to DISAGREE")
# ---------------------------------------------------------------------------
# This is the property that generalises. Widening a regex fixes the modes we
# already know about; an independent verifier is what catches the mode nobody
# has written down yet. Simulated by putting the OLD pattern back and asking
# whether the independent route still sees the leak.
for label, s in [
    ("brace group", BRACE),
    ("brace group, spaced '@'", G),
    ("broken domain", "firstname.lastname@example. edu"),
]:
    explained_by_old = len(OLD_EMAIL_PATTERN.findall(s))
    seen_independently = residue_scan(s)
    check(f"{label}: independent scanner sees what the old pattern missed "
          f"(residue={seen_independently} > explained={explained_by_old})",
          seen_independently > explained_by_old)

# And the converse: with the pattern FIXED, the two agree, so the gate does not
# block a clean corpus. A check that cannot go green is a check that gets removed.
for label, s in [
    ("brace group", BRACE),
    ("broken domain", "firstname.lastname@example. edu"),
    ("ordinary address", "firstname.lastname@example.edu"),
]:
    check(f"{label}: with the fix in place the two checks agree",
          residue_scan(s) - len(EMAIL_PATTERN.findall(s)) <= 0)

# ---------------------------------------------------------------------------
print("\n[7] THE DISAGREEMENT CANNOT BE MUTED BY ALLOWED ADDRESSES")
# ---------------------------------------------------------------------------
# The first version of this check compared TOTALS: residue_scan(text) minus
# len(EMAIL_PATTERN.findall(text)). That is silently broken, and it took a
# planted brace group that the guard FAILED TO FLAG to notice.
#
# residue_scan() deliberately ignores short locals, so it does not count the
# "team@" in the site footer. EMAIL_PATTERN counts every one of them. On a real
# page -- which carries two footer addresses -- the arithmetic for one genuine
# leak reads 1 - 2 = -1, and the leak reports as no disagreement at all.
#
# A guard that is switched off by the presence of the site's own contact address
# is worse than no guard, because it reads as coverage. The comparison is
# POSITIONAL for this reason, and this is the case that pins it.
PAGE_WITH_FOOTER = (
    "<p>Correspondence: {alpha,bravo,charlie}@example.edu</p>\n"
    "<footer>Contact <a href='mailto:team@pdoom1.com'>team@pdoom1.com</a></footer>"
)
old_totals_verdict = residue_scan(PAGE_WITH_FOOTER) - len(OLD_EMAIL_PATTERN.findall(PAGE_WITH_FOOTER))
check("the old TOTALS comparison would have reported no disagreement "
      f"(verdict={old_totals_verdict}, i.e. muted by the footer)",
      old_totals_verdict <= 0)

# The positional comparison, simulating the pattern still being blind.
residue_at = sync_events.residue_positions(PAGE_WITH_FOOTER)
explained_by_old_at = set()
for _m in OLD_EMAIL_PATTERN.finditer(PAGE_WITH_FOOTER):
    for _k in range(_m.start(), _m.end()):
        if PAGE_WITH_FOOTER[_k] == "@":
            explained_by_old_at.add(_k)
check("the POSITIONAL comparison still catches the leak past the footer",
      len(residue_at - explained_by_old_at) == 1)

# And with the pattern fixed, the same page is clean -- no false alarm.
check("with the widened pattern the same page raises nothing",
      sync_events.unexplained_residue(PAGE_WITH_FOOTER) == 0)

# ---------------------------------------------------------------------------
print("\n[8] NESTED STRUCTURES -- a field added upstream cannot hide a group")
# ---------------------------------------------------------------------------
nested = {"a": [{"b": "contact {alpha,bravo}@example.edu now"}]}
out = sync_events.redact_pii(nested)
check("redact_pii reaches the whole record", MARKER in out["a"][0]["b"])
check("and no name survives", "alpha" not in out["a"][0]["b"])
check("count_emails counts the group as one address",
      sync_events.count_emails(nested) == 1)

# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
if failures:
    print(f"FAIL: {len(failures)} check(s) failed")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("PASS: the three inherited modes fire, the lowercase-TLD rule survives, "
      "every notation family stays silent, and the two checks can disagree.")
