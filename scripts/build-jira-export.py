#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build docs/jira/export_2026-08-10.jsonl for the coordination seat.

A SCRIPT, not a heredoc -- coordination's rule 1, and this weekend's evidence for
it. Every open issue is classified explicitly; there is no default branch, because
a default would silently mislabel the issues I understand least, which are exactly
the ones a human most needs flagged.
"""
import io
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        try:
            if _s is sys.stdout:
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        except Exception:
            pass

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])
REPO = "pdoom1-website"

# number -> (epic, tier, external_deadline, blocked_by, why)
C = {
297: ("board-and-league", 2, None, [], "The blessing changed from a decision into a ratification and the governing ledger still describes a ceremony that no longer happens."),
296: ("site-design-and-copy", 2, None, [], "The game is free, so every categorising signal a visitor gets comes from collateral we control and have not decided."),
293: ("board-and-league", 1, None, ["pdoom1-website#294"], "The probe composed a board key from two files of different ages and reported nine real scores as orphaned."),
290: ("release-pipeline", 1, None, [], "A GITHUB_TOKEN push produces zero check runs, so every bot commit into public/ is invisible to the push-triggered deploy."),
287: ("release-pipeline", 1, None, [], "The release-time sync writes a path the site never reads, so it has never once changed what a visitor sees."),
286: ("release-pipeline", 1, None, ["pdoom1-website#299"], "Four workflows run rsync --delete against one document root with nothing coordinating them; two overlapped by 13 seconds on 2026-08-07."),
285: ("release-pipeline", 1, None, ["pdoom1-website#289"], "A release published between cron runs leaves the site advertising the previous version for up to seven hours, green throughout."),
282: ("content-honesty", 2, None, ["pdoom-data#68"], "Two event titles are served as mojibake and the upstream repair cannot reach the pages that carry them."),
277: ("content-honesty", 1, None, [], "A blocking honesty job is red on a schedule nobody is watching, which is how a red square stops meaning anything."),
275: ("rulings-inbox", 2, None, [], "Pip's rulings from 2026-08-06 breakfast, including that Tor/I2P is an accessibility call, are recorded and not yet applied."),
273: ("content-honesty", 1, None, [], "Data contract validation is red on a schedule and has been since 2026-08-06."),
268: ("architecture-and-adrs", 2, None, [], "The estate has no place to record a near miss, so the right question asked with the wrong instrument leaves no trace."),
267: ("content-honesty", 2, None, [], "Nothing on the site marks which text a human wrote, which is the provenance claim that will matter first."),
265: ("rulings-inbox", 2, None, [], "Pip ruled the 'why' paragraph over-claims and wants verbatim source lines; the redraft is his and is not done."),
263: ("rulings-inbox", 2, None, [], "A GO ruling listing approved PRs to apply, at least one of which is still open."),
262: ("rulings-inbox", 2, None, [], "Eleven rulings taken off paper on 2026-08-05 that have not been individually closed out."),
259: ("site-design-and-copy", 2, None, [], "Agents read this site and there is no stated policy or machine-readable entry point for them."),
258: ("site-design-and-copy", 2, None, [], "The risk graph conflates our baseline claim with the net sum of player runs, which are different assertions."),
254: ("content-honesty", 1, None, [], "Eighteen places decline, pass or succeed without checking anything, and one of them is a live falsehood."),
249: ("architecture-and-adrs", 2, None, [], "What this repo pulls from the game's image pipeline is undecided and needs Pip's push-versus-pull ruling."),
248: ("content-honesty", 2, None, [], "A thousand generated pages still assert impact magnitudes nobody has verified."),
247: ("architecture-and-adrs", 3, None, [], "Architecture notes from pdoom1 recorded as context; explicitly plans not commitments, so nothing here is owed."),
246: ("content-honesty", 1, None, [], "Third parties' names are in publicly fetchable filenames on production right now."),
240: ("content-honesty", 2, None, [], "The PII guard could not run on the sync's own output, and two orphan pages carry the superseded redaction marker."),
238: ("rulings-inbox", 2, None, [], "In-flight plan asks 1-5 from 2026-08-02 that were never individually closed."),
229: ("board-and-league", 1, None, ["pdoom1-website#298"], "The probe cannot discover a newly drawn seed, so it reports OK about last week's board on league night."),
220: ("architecture-and-adrs", 2, None, [], "pdoom-data's ADR-007/008 propose a contribution loop and consent UX this site would have to implement."),
214: ("architecture-and-adrs", 2, None, [], "Decisions here are scattered across issue comments instead of an ADR set anyone can read in order."),
213: ("site-design-and-copy", 2, None, [], "The site explains seeds and ladder epochs in words the game does not use, which is how players learn the wrong model."),
194: ("grant-readiness", 1, "2026-09-09", [], "The Manifund application is live with a hard close and the site does not point at it."),
177: ("content-honesty", 2, None, [], "calculate-game-stats will need an honesty audit the moment real data channels replace the pending nulls."),
160: ("site-design-and-copy", 2, None, [], "There is no voice guide, so every copy change is a fresh argument about tone."),
156: ("content-honesty", 2, None, [], "The events pipeline has no human promotion stage, so nothing curates what reaches the monthly update."),
154: ("site-design-and-copy", 3, None, [], "A reminder to revisit the homepage Follow-along block whose own date passed on 2026-08-06."),
151: ("board-and-league", 3, None, [], "The v0.13 epoch cut it tracks happened, closed, and has since been superseded twice; I would close this."),
144: ("community-and-comms", 2, None, [], "Auto-posting release updates needs an architecture ruling before any of the campaign machinery is worth building."),
87:  ("community-and-comms", 2, None, [], "There is no public update cadence, and the press strategy that would set one has never been executed."),
86:  ("grant-readiness", 2, None, [], "Testimonials for a funder page that does not exist yet."),
84:  ("grant-readiness", 2, None, [], "A budget page with low/medium/high outcomes, needed if the Manifund push wants depth behind it."),
83:  ("grant-readiness", 2, None, [], "A team and hiring page with roles and rates, which a funder will look for."),
82:  ("grant-readiness", 2, None, [], "A safety and responsibility statement, which for this project in particular is table stakes."),
80:  ("grant-readiness", 2, None, [], "A gameplay clip and curated screenshots; the assets exist and have never been published."),
79:  ("grant-readiness", 2, None, [], "A press kit page, already linked from navigation on some pages."),
78:  ("grant-readiness", 2, None, [], "A donor landing page answering why fund this, which the Manifund deadline makes concrete."),
71:  ("community-and-comms", 3, None, [], "Displaying GitHub issues on a forum, when /issues/ already renders them on the site; I would close this."),
68:  ("infra-and-security", 2, None, [], "No security review has ever been run across the repos, and one seat found a live credential leak elsewhere this weekend."),
63:  ("community-and-comms", 3, None, ["pdoom1-website#60"], "A webhook into a forum that has no DNS record and therefore no users."),
60:  ("community-and-comms", 3, None, [], "NodeBB is live on the VPS but forum.pdoom1.com has no DNS record, so this has been stalled at the last step for months."),
59:  ("infra-and-security", 3, None, [], "An investigation into a legacy origin/master reference that affects nothing; I would close this."),
52:  ("infra-and-security", 3, None, [], "Tor/I2P hosting, which Pip has since ruled is an accessibility question rather than a privacy one (see #275)."),
14:  ("infra-and-security", 3, None, [], "Search Console and Bing verification meta tags, unstarted since the site launched."),
}

issues = json.loads(SRC.read_text(encoding="utf-8"))
missing = [i["number"] for i in issues if i["number"] not in C]
if missing:
    sys.exit("REFUSING: no classification for %s. Classify them or the export lies "
             "by omission." % missing)

OUT.parent.mkdir(parents=True, exist_ok=True)
rows = []
for i in sorted(issues, key=lambda x: x["number"]):
    epic, tier, deadline, blocked, why = C[i["number"]]
    rows.append({
        "repo": REPO,
        "number": i["number"],
        "title": i["title"],
        "url": i["url"],
        "labels": [l["name"] for l in i.get("labels") or []],
        "epic": epic,
        "tier": tier,
        "external_deadline": deadline,
        "blocked_by": blocked,
        "why": why,
    })

with OUT.open("w", encoding="utf-8", newline="\n") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

from collections import Counter
print("wrote %s" % OUT)
print("lines: %d   issues: %d   match: %s" % (len(rows), len(issues), len(rows) == len(issues)))
print("tiers:", dict(sorted(Counter(r["tier"] for r in rows).items())))
print("epics:")
for e, n in sorted(Counter(r["epic"] for r in rows).items()):
    print("   %-24s %d" % (e, n))
print("with external deadline:", [r["number"] for r in rows if r["external_deadline"]])
print("with blocked_by      :", [r["number"] for r in rows if r["blocked_by"]])
