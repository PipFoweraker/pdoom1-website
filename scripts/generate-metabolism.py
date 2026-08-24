#!/usr/bin/env python
"""Generate /metabolism/ -- the map of every recurring cycle this project runs.

WHY THIS IS A GENERATOR AND NOT A PAGE
--------------------------------------
A hand-written page listing cadences is worse than no page at all. It is right on
the day it is written and confidently wrong a month later, and nothing about it
looks wrong in the meantime. This repository's first rule is never to lie to a
visitor, so the only honest way to publish "here is our rhythm" is to derive every
number on the page from the thing that actually runs.

So: every cadence here is read at build time from a source of truth in the repo --
the cron expressions in .github/workflows/, the league config the manager loads,
the seed ledger, clocks.json. Nothing is typed into the template. The two classes
of fact that genuinely cannot be derived (a rule that lives in the pdoom1 repo, and
a maintainer observation with no in-repo measurement) live in public/data/
metabolism.json, each carrying an explicit `source` and `derived_from`, and are
rendered as declared rather than as measured.

Where a cadence is unknown, the page says unknown. It never rounds a gap to a
plausible-looking number to make the picture complete.

THE GUARD
---------
`--check` regenerates the page in memory and exits non-zero if the committed HTML
differs by a single byte. Wired into CI (.github/workflows/metabolism-map.yml), so
changing a cron and forgetting to regenerate fails the pull request instead of
silently publishing a stale rhythm. This is the same idiom as
`scripts/generate-feeds.py --check` and `scripts/snapshot-copy.py --check`.

Because provenance is rendered as file:line, ANY edit that shifts a cited line
fails the check. That is the bargain: the page cannot drift, and the cost is
re-running this script. The failure message says exactly that.

Determinism: nothing in the output depends on the wall clock. There is no
"generated at" stamp, because a timestamp would make --check impossible and would
tell the reader nothing about whether the page is still true.

Usage:
    python scripts/generate-metabolism.py           # write the page
    python scripts/generate-metabolism.py --check   # exit 1 if it is stale (CI)
"""

import argparse
import datetime as dt
import html
import json
import math
import re
import sys
from pathlib import Path

import yaml

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
CLOCKS_JSON = REPO_ROOT / "public" / "data" / "clocks.json"
METABOLISM_JSON = REPO_ROOT / "public" / "data" / "metabolism.json"
LEAGUE_CONFIG = REPO_ROOT / "scripts" / "weekly-league-config.json"
LEAGUE_MANAGER = REPO_ROOT / "scripts" / "weekly-league-manager.py"
SEED_LEDGER = REPO_ROOT / "docs" / "LEAGUE_SEED_LEDGER.md"
OUT = REPO_ROOT / "public" / "metabolism" / "index.html"

BLOB = "https://github.com/PipFoweraker/pdoom1-website/blob/main/"

DOW_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

# A workflow that carries one of these markers in the comments around its `on:`
# block has been deliberately reduced to manual dispatch. It must render as
# parked, with its stated reason -- never as a live cadence, and never silently
# dropped. See CLAUDE.md, "Workflow authoring traps" #4.
PARK_MARKERS = (
    "PARKED",
    "SCHEDULE REMOVED",
    "TRIGGER REMOVED",
    "Manual only",
    "manual only",
    "(disabled)",
)


class SourceError(RuntimeError):
    """A source of truth changed shape or vanished. Fail loudly, never guess."""


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

class Cite:
    """A file:line pointer, resolved at build time.

    The point of resolving line numbers rather than typing them is that a
    citation cannot rot into pointing at the wrong line: if the needle is gone,
    or appears more than once, this raises and the build fails. A provenance
    link a reader cannot trust is worse than none.
    """

    __slots__ = ("path", "line")

    def __init__(self, path, line=0):
        self.path = path
        self.line = line

    @property
    def rel(self):
        return self.path.relative_to(REPO_ROOT).as_posix()

    @property
    def label(self):
        return "%s:%d" % (self.rel, self.line) if self.line else self.rel

    @property
    def url(self):
        return BLOB + self.rel + ("#L%d" % self.line if self.line else "")


def cite(path, needle, occurrence="unique", render_line=True):
    """Locate `needle` in `path` and return a Cite.

    occurrence="unique" -> exactly one line must contain it (strongest guard).
    occurrence="first"  -> the first matching line (for values that legitimately
                           repeat, e.g. a cron expression shared by workflows).

    render_line=False still REQUIRES the needle to be present -- so the claim
    cannot outlive the sentence it came from -- but prints only the file name.
    That is the right trade for a prose file several branches edit at once:
    coupling the page byte-for-byte to a churning document would turn the CI
    guard red for reasons a reader of the page would not recognise, and a guard
    that cries wolf is one people learn to ignore.
    """
    if not path.exists():
        raise SourceError("cited file is missing: %s" % path)
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [i + 1 for i, ln in enumerate(lines) if needle in ln]
    if not hits:
        raise SourceError(
            "citation needle not found in %s: %r\n"
            "The source moved or was reworded. Fix the needle or the claim -- "
            "do not delete the citation." % (path, needle))
    if occurrence == "unique" and len(hits) > 1:
        raise SourceError(
            "citation needle is ambiguous in %s (%d matches): %r"
            % (path, len(hits), needle))
    return Cite(path, hits[0] if render_line else 0)


def cite_file(path):
    return Cite(path, 0)


# ---------------------------------------------------------------------------
# Cron
# ---------------------------------------------------------------------------

def parse_cron(expr):
    """Return {period, phase, phase_label, origin} for a cron we understand.

    `phase` is the fraction of the period at which the job fires, measured from
    the period's own origin (midnight UTC for sub-daily and daily periods,
    Monday 00:00 UTC for weekly ones). That is what lets the diagram place a
    marker: two jobs at the same phase on the same ring literally collide.

    Returns None for any expression this parser does not fully understand. An
    unparsed cron is rendered verbatim as "not interpreted" rather than being
    approximated -- guessing here would put a wrong time on the page.
    """
    parts = expr.split()
    if len(parts) != 5:
        return None
    minute, hour, dom, mon, dow = parts
    if dom != "*" or mon != "*" or not minute.isdigit():
        return None
    m = int(minute)

    if dow == "*":
        if hour == "*":
            period = 3600
            phase = (m * 60) / period
            label = ":%02d past each hour, UTC" % m
            origin = "the top of each hour, UTC"
        elif hour.startswith("*/") and hour[2:].isdigit():
            step = int(hour[2:])
            if step <= 0 or 24 % step:
                return None
            period = step * 3600
            phase = (m * 60) / period
            label = ":%02d past each %d-hour block, UTC" % (m, step)
            origin = "00:00 UTC, then every %dh" % step
        elif "," in hour and all(h.isdigit() for h in hour.split(",")):
            hs = sorted(int(h) for h in hour.split(","))
            gaps = {hs[i + 1] - hs[i] for i in range(len(hs) - 1)}
            gaps.add(hs[0] + 24 - hs[-1])
            if len(gaps) != 1:
                return None
            period = gaps.pop() * 3600
            phase = ((hs[0] * 3600 + m * 60) % period) / period
            label = "%s UTC" % ", ".join("%02d:%02d" % (h, m) for h in hs)
            origin = "00:00 UTC, then every %dh" % (period // 3600)
        elif hour.isdigit():
            period = 86400
            phase = (int(hour) * 3600 + m * 60) / period
            label = "%02d:%02d UTC daily" % (int(hour), m)
            origin = "00:00 UTC"
        else:
            return None
    else:
        if not hour.isdigit() or not dow.isdigit():
            return None
        d = int(dow) % 7
        period = 604800
        phase = (((d - 1) % 7) * 86400 + int(hour) * 3600 + m * 60) / period
        label = "%s %02d:%02d UTC weekly" % (DOW_NAMES[d], int(hour), m)
        origin = "Monday 00:00 UTC"

    return {"period": period, "phase": phase, "phase_label": label,
            "origin": origin}


# Named periods, loaded from metabolism.json at build time. A calendar month is
# not a whole number of anything, so it can only ever be a named approximation --
# naming it here keeps the approximation visible instead of printing
# "every 2629746 seconds" and pretending that is a fact about calendars.
PERIOD_NAMES = {}


def humanise_period(seconds):
    if seconds is None:
        return "unknown"
    if seconds in PERIOD_NAMES:
        return PERIOD_NAMES[seconds]
    if seconds % 604800 == 0:
        n = seconds // 604800
        return "weekly" if n == 1 else "every %d weeks" % n
    if seconds % 86400 == 0:
        n = seconds // 86400
        return "daily" if n == 1 else "every %d days" % n
    if seconds % 3600 == 0:
        n = seconds // 3600
        return "hourly" if n == 1 else "every %d hours" % n
    if seconds % 60 == 0:
        return "every %d minutes" % (seconds // 60)
    return "every %d seconds" % seconds


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------

def trigger_comments(text):
    """Every comment line before `jobs:`.

    Park notices live either above `on:` (extract-analytics) or inside the `on:`
    block itself (weekly-deployment), so both regions have to be read.
    """
    out = []
    for ln in text.splitlines():
        if ln.startswith("jobs:"):
            break
        s = ln.strip()
        if s.startswith("#"):
            out.append(s.lstrip("#").strip())
        elif not s:
            out.append("")
    return out


def park_reason(comments, name):
    """Return (marker, reason) if this workflow is parked, else None."""
    marker = next((mk for mk in PARK_MARKERS if mk in name), None)
    idx = None
    if marker is None:
        for i, c in enumerate(comments):
            hit = next((mk for mk in PARK_MARKERS if mk in c), None)
            if hit:
                marker, idx = hit, i
                break
    if marker is None:
        return None
    if idx is None:
        # The marker is in the workflow's own name and nowhere else. Say that,
        # rather than echoing the name back as if it were an explanation.
        return marker, ("The workflow's name says so. No reason is recorded in "
                        "the file -- read it before re-enabling anything.")
    chunk = []
    for c in comments[idx:]:
        if not c:
            break
        chunk.append(c)
    reason = " ".join(chunk)
    # First few sentences is enough to say why; the file has the rest.
    bits = re.split(r"(?<=[.!?])\s+", reason)
    reason = " ".join(bits[:3]).strip()
    if len(reason) > 320:
        reason = reason[:317].rstrip() + "..."
    return marker, reason


def _grants(node, scope, level):
    """True if any `permissions:` block anywhere in the file grants scope:level.

    GitHub resolves permissions per job, with the job-level block replacing the
    workflow-level one, so the question "can this file commit" is answered by
    whether ANY level grants it -- not by the top-level block alone.
    health-checks.yml declares `contents: read` at the top and overrides it to
    write on the job, and reading only the top block would have called it a
    non-committer.
    """
    if isinstance(node, dict):
        perms = node.get("permissions")
        if perms == "write-all":
            return True
        if isinstance(perms, dict) and perms.get(scope) == level:
            return True
        return any(_grants(v, scope, level) for v in node.values())
    if isinstance(node, list):
        return any(_grants(v, scope, level) for v in node)
    return False


def _grants_contents_write(node):
    return _grants(node, "contents", "write")


def load_workflows():
    """Parse every workflow into a uniform record.

    PyYAML resolves the bare key `on:` to the boolean True (YAML 1.1), which is
    the classic trap when reading Actions files with a YAML parser -- hence the
    two-key lookup below.
    """
    if not WORKFLOW_DIR.is_dir():
        raise SourceError("no .github/workflows directory at %s" % WORKFLOW_DIR)
    records = []
    for path in sorted(WORKFLOW_DIR.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        doc = yaml.safe_load(text) or {}
        if not isinstance(doc, dict):
            raise SourceError("workflow is not a mapping: %s" % path)
        on = doc.get(True, doc.get("on"))
        if on is None:
            raise SourceError("workflow has no `on:` block: %s" % path)
        if isinstance(on, str):
            on = {on: None}
        if isinstance(on, list):
            on = {k: None for k in on}
        name = str(doc.get("name") or path.stem)

        crons = []
        sched = on.get("schedule") or []
        if isinstance(sched, list):
            for entry in sched:
                if isinstance(entry, dict) and "cron" in entry:
                    expr = str(entry["cron"]).strip()
                    crons.append({
                        "expr": expr,
                        "parsed": parse_cron(expr),
                        "cite": cite(path, expr, occurrence="first"),
                    })

        # A `git commit` step only actually commits if some level of the file
        # grants contents: write. health-checks.yml declares contents: read at
        # the top and overrides it to write on the job, so only walking the
        # top-level block would have called it a non-committer.
        may_write = _grants_contents_write(doc)

        park = park_reason(trigger_comments(text), name)
        if park and crons:
            raise SourceError(
                "%s carries the park marker %r but still has a schedule. One of "
                "the two is a lie; fix the workflow before regenerating."
                % (path.name, park[0]))

        records.append({
            "file": path,
            "name": name,
            "triggers": sorted(str(k) for k in on.keys()),
            "crons": crons,
            "park": park,
            "deploys": "rsync" in text and "DH_HOST" in text,
            "commits": "git commit" in text and may_write,
            "commit_step_without_write": "git commit" in text and not may_write,
            "issues": _grants(doc, "issues", "write"),
            "cite_name": cite(path, "name:", occurrence="first"),
        })
    return records


# ---------------------------------------------------------------------------
# League
# ---------------------------------------------------------------------------

def derive_rollover_phase(cron_expr):
    """Replay weekly-league-manager's week arithmetic at the cron's firing time.

    get_current_week_info() calls datetime.now() (naive, so UTC on a GitHub
    runner), takes the Monday of *that* moment's week, and ends the week the
    following Sunday 23:59:59. Whether the workflow therefore opens the week
    that is about to start or the one that is about to end is a property of the
    cron alone, identical every week -- so it can be computed from a fixed
    reference instant and stays byte-stable in the output.

    This is why the finding survives PR #187: change the cron, and this number
    recomputes rather than needing an edit.
    """
    parsed = parse_cron(cron_expr)
    if not parsed or parsed["period"] != 604800:
        return None
    # Fixed reference: a Monday 00:00 UTC. Which Monday is irrelevant -- the
    # offset being measured repeats every week.
    ref = dt.datetime(2024, 1, 1)
    assert ref.weekday() == 0
    fire = ref + dt.timedelta(seconds=parsed["phase"] * 604800)
    week_start = (fire - dt.timedelta(days=fire.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + dt.timedelta(days=6, hours=23, minutes=59, seconds=59)
    return {
        "fires_at": parsed["phase_label"],
        "hours_into_week": (fire - week_start).total_seconds() / 3600.0,
        "hours_to_week_end": (week_end - fire).total_seconds() / 3600.0,
    }


def hobart_offsets(probes):
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Australia/Hobart")
    out = {}
    for key, iso in sorted(probes.items()):
        if key.startswith("_"):
            continue
        moment = dt.datetime.fromisoformat(iso)
        local = moment.astimezone(tz)
        out[key] = {
            "abbrev": local.tzname(),
            "offset_hours": local.utcoffset().total_seconds() / 3600.0,
        }
    return out


def parse_ledger(path):
    """Read the epoch rows out of the seed ledger's first markdown table."""
    if not path.exists():
        raise SourceError("seed ledger missing: %s" % path)
    rows = []
    header_seen = False
    for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        s = ln.strip()
        if not s.startswith("|"):
            if header_seen and rows:
                break
            continue
        # The ledger is markdown; strip its emphasis so the values render as
        # values. Anything left is the literal seed/ladder string.
        cells = [re.sub(r"[`*]", "", c).strip() for c in s.strip("|").split("|")]
        if not header_seen:
            if cells and cells[0].lower() == "epoch":
                header_seen = True
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if len(cells) < 6:
            continue
        rows.append({
            "epoch": cells[0], "seed": cells[1], "ladder": cells[2],
            "board": cells[3], "blessed": cells[4], "by": cells[5],
            "cite": Cite(path, i),
        })
    if not header_seen:
        raise SourceError("no epoch table found in %s" % path)
    return rows


def next_epoch_label(rows):
    """L2 -> L3. Purely a label for 'the row that does not exist yet'."""
    for row in reversed(rows):
        m = re.fullmatch(r"L(\d+)", row["epoch"])
        if m:
            return "L%d" % (int(m.group(1)) + 1)
    return None


# ---------------------------------------------------------------------------
# Cycle assembly
# ---------------------------------------------------------------------------

def build_cycles(workflows, clocks, meta):
    """One flat list of every recurring beat, each with its provenance.

    `period` None means the cadence is genuinely unknown; those never reach the
    diagram and are listed separately so a reader can see the holes.
    """
    periods = meta["period_seconds"]
    cycles = []

    for wf in workflows:
        if wf["park"]:
            continue
        for cron in wf["crons"]:
            p = cron["parsed"]
            cycles.append({
                "id": "wf-%s-%s" % (wf["file"].stem, cron["expr"].replace(" ", "_").replace("*", "x").replace("/", "-")),
                "title": wf["name"],
                "kind": "repo automation",
                "period": p["period"] if p else None,
                "phase": p["phase"] if p else None,
                "when": p["phase_label"] if p else "cron not interpreted: %s" % cron["expr"],
                "origin": p["origin"] if p else None,
                "cite": cron["cite"],
                "note": workflow_effect(wf),
                "unknown_reason": (None if p else
                                   "This generator does not interpret the cron expression "
                                   "%r. It is shown verbatim rather than approximated."
                                   % cron["expr"]),
            })

    for mc in meta["mirrored_cycles"]:
        secs = periods.get(mc["period"]) if mc.get("period") else None
        # A phase WINDOW, not a phase. Both mirrored cycles are known to a day
        # or to a week, never to an hour, and the window is declared in the JSON
        # with its own justification rather than inferred from the prose.
        win = mc.get("phase_window")
        span = None
        if win and secs:
            span = ((win["from_days"] * 86400) / secs,
                    (win["to_days"] * 86400) / secs, win["why"])
        cycles.append({
            "id": "mirror-%s" % mc["id"],
            "title": mc["title"],
            "kind": "upstream (mirrored)",
            "period": secs,
            "phase": None,
            "span": span,
            "when": mc["when"] + (" (%s, days %d-%d)"
                                  % (win["origin"], win["from_days"],
                                     win["to_days"]) if win else ""),
            "origin": win["origin"] if win else None,
            "cite": cite(METABOLISM_JSON, '"id": "%s"' % mc["id"]),
            "note": "%s; %s" % (mc["version_effect"],
                                "forks the board" if mc["forks_board"]
                                else ("does not fork the board"
                                      if mc["forks_board"] is False
                                      else "board effect not applicable")),
            "unknown_reason": mc.get("period_unknown_reason"),
            "source": mc["source"],
            "derived_from": mc["derived_from"],
        })

    for clock in clocks["clocks"]:
        cad = clock.get("cadence")
        if not cad:
            continue
        secs = None
        phase = None
        when = "declared cadence: %s" % cad["type"]
        unknown = None
        if cad["type"] == "weekly" and cad.get("anchor_utc"):
            secs = periods["weekly"]
            m = re.match(r"([A-Za-z]{3})\s+(\d{1,2}):(\d{2})", cad["anchor_utc"])
            if not m:
                raise SourceError("clocks.json anchor_utc not understood: %r"
                                  % cad["anchor_utc"])
            d = DOW_NAMES.index(m.group(1))
            phase = (((d - 1) % 7) * 86400 + int(m.group(2)) * 3600
                     + int(m.group(3)) * 60) / secs
            when = "%s UTC (declared anchor)" % cad["anchor_utc"]
        elif cad["type"] == "monthly":
            secs = periods["monthly"]
            when = "monthly, no anchor declared"
            unknown = ("clocks.json declares the period but no anchor, so the "
                       "next date cannot be computed. The clock renders as a "
                       "cadence, not a date.")
        else:
            unknown = ("cadence type %r defers to an upstream provider that "
                       "publishes no schedule this repo can read."
                       % cad["type"])
        cycles.append({
            "id": "clock-%s" % clock["id"],
            "title": "%s (clocks.json)" % clock["title"],
            "kind": "declared clock",
            "period": secs,
            "phase": phase,
            "when": when,
            "origin": "Monday 00:00 UTC" if phase is not None else None,
            "cite": cite(CLOCKS_JSON, '"id": "%s"' % clock["id"]),
            "note": clock.get("note", ""),
            "unknown_reason": unknown,
            # A clock with a resolvable period restates a beat the diagram
            # already draws from the thing that actually runs it, so drawing it
            # again would double-count. A clock with NO period is the only
            # record that cycle exists, so it does belong on the outer ring.
            "diagram": secs is None,
        })

    for hop in meta["cross_repo"]["hops"]:
        # Where a hop names a real in-repo source for its cadence, cite THAT
        # rather than the declaration -- a published ADR beats a hand-held copy.
        if hop.get("cadence_source_file"):
            hop_cite = cite(REPO_ROOT / hop["cadence_source_file"],
                            hop["cadence_source_needle"])
        else:
            hop_cite = cite(METABOLISM_JSON, '"id": "%s"' % hop["id"])
        cycles.append({
            "id": "cross-%s" % hop["id"],
            "title": "%s (%s)" % (hop["name"], meta["cross_repo"]["title"]),
            "kind": "cross-repo",
            "period": periods[hop["cadence"]] if hop.get("cadence") else None,
            "phase": None,
            "when": hop["trigger"],
            "origin": None,
            "cite": hop_cite,
            "note": ("fires by %s" % hop["fires_by"]) if hop.get("fires_by")
                    else "state: %s" % hop["our_state"],
            "unknown_reason": hop.get("cadence_unknown_reason"),
        })

    return cycles


# ---------------------------------------------------------------------------
# Diagram
# ---------------------------------------------------------------------------

R_MIN, R_MAX, R_UNKNOWN = 76.0, 250.0, 292.0
R_CORE = 34.0
KIND_COLOUR = {
    "repo automation": "var(--teal)",
    "upstream (mirrored)": "var(--amber)",
    "declared clock": "var(--ink-3)",
    "cross-repo": "var(--phosphor)",
}


def ring_radii(periods):
    """Log-spaced radii. Fastest ring innermost -- that is the whole reading."""
    if not periods:
        return {}
    if len(periods) == 1:
        return {periods[0]: (R_MIN + R_MAX) / 2}
    lo, hi = math.log10(periods[0]), math.log10(periods[-1])
    return {p: R_MIN + (R_MAX - R_MIN) * (math.log10(p) - lo) / (hi - lo)
            for p in periods}


def polar(r, phase):
    """phase 0 at 12 o'clock, increasing clockwise."""
    a = phase * 2 * math.pi - math.pi / 2
    return r * math.cos(a), r * math.sin(a)


def largest_gap_phase(phases):
    """Where on a ring is there most room for its label?"""
    if not phases:
        return 0.5
    ps = sorted(phases)
    best, best_gap = 0.5, -1.0
    for i, p in enumerate(ps):
        nxt = ps[(i + 1) % len(ps)] + (1.0 if i + 1 == len(ps) else 0.0)
        gap = nxt - p
        if gap > best_gap:
            best_gap, best = gap, (p + gap / 2) % 1.0
    return best


def render_svg(cycles, deploy_fact):
    on_diagram = [c for c in cycles
                  if c["period"] and c.get("diagram", True)]
    unquantified = sorted([c for c in cycles
                           if not c["period"] and c.get("diagram", True)],
                          key=lambda c: c["title"])
    periods = sorted({c["period"] for c in on_diagram})
    radii = ring_radii(periods)

    p = ['<svg viewBox="-330 -330 660 660" role="img" '
         'aria-labelledby="mapTitle mapDesc" class="epi">',
         '<title id="mapTitle">Nested cycle map</title>',
         '<desc id="mapDesc">Concentric rings, one per distinct period. The '
         'innermost ring is the fastest cycle and the outermost the slowest. '
         'Each marker is one recurring job, placed at the point in its period '
         'when it fires. Markers stacked along one radius are jobs that fire at '
         'the same moment.</desc>']

    # Core: the deploy path. A latency, not a period -- drawn as a disc, not a
    # ring, so it cannot be misread as a cadence.
    p.append('<circle class="core" cx="0" cy="0" r="%.1f"/>' % R_CORE)
    p.append('<text class="corelabel" x="0" y="-4">deploy</text>')
    p.append('<text class="coreval" x="0" y="12">%s</text>'
             % html.escape(deploy_fact["value"]))

    for period in periods:
        r = radii[period]
        members = sorted([c for c in on_diagram if c["period"] == period],
                         key=lambda c: c["title"])
        p.append('<circle class="ring" cx="0" cy="0" r="%.1f"/>' % r)

        # Everything already committed to a position on this ring, so the
        # hollow markers and the ring's own label can be steered into whatever
        # arc is still empty instead of landing on top of a dot.
        occupied = []
        dots = [c for c in members if c["phase"] is not None]
        spans = [c for c in members if c.get("span")]
        hollows = [c for c in members
                   if c["phase"] is None and not c.get("span")]

        # Jobs at the same phase are a real collision -- three of them fire on
        # the same second here. Stacking them outward along one radius makes
        # that visible AND keeps every one of them clickable; drawing them on
        # top of each other would hide the finding and the links.
        seen = {}
        for c in dots:
            key = round(c["phase"], 6)
            depth = seen.get(key, 0)
            seen[key] = depth + 1
            # Stack inward: outward would push the third dot into the next ring
            # out, and the innermost ring has clear space to the core.
            x, y = polar(r - depth * 9, c["phase"])
            occupied.append(c["phase"])
            tip = "%s -- %s" % (c["title"], c["when"])
            if depth:
                tip += " (fires at the same moment as %d other job(s))" % depth
            p.append('<a href="#%s"><title>%s</title>'
                     '<circle class="dot" cx="%.1f" cy="%.1f" r="5.5" '
                     'fill="%s"/></a>'
                     % (c["id"], html.escape(tip), x, y,
                        KIND_COLOUR.get(c["kind"], "var(--ink-2)")))

        for c in spans:
            # A window, not an instant. The arc covers every moment the event
            # could land on; a dot would assert a precision nobody published.
            start, end, why = c["span"]
            x0, y0 = polar(r, start)
            x1, y1 = polar(r, end)
            large = 1 if (end - start) > 0.5 else 0
            occupied += [start, (start + end) / 2, end]
            p.append('<a href="#%s"><title>%s -- %s. %s</title>'
                     '<path class="arc" stroke="%s" '
                     'd="M %.1f %.1f A %.1f %.1f 0 %d 1 %.1f %.1f"/></a>'
                     % (c["id"], html.escape(c["title"]),
                        html.escape(c["when"]), html.escape(why),
                        KIND_COLOUR.get(c["kind"], "var(--ink-2)"),
                        x0, y0, r, r, large, x1, y1))

        for c in hollows:
            # Period known, firing time not. A hollow marker in empty space, so
            # the cycle is visible without being given a time we do not have.
            ph = largest_gap_phase(occupied)
            occupied.append(ph)
            x, y = polar(r, ph)
            p.append('<a href="#%s"><title>%s -- %s (period known, phase not '
                     'published)</title><circle class="dot hollow" cx="%.1f" '
                     'cy="%.1f" r="5.5" stroke="%s"/></a>'
                     % (c["id"], html.escape(c["title"]), html.escape(c["when"]),
                        x, y, KIND_COLOUR.get(c["kind"], "var(--ink-2)")))

        lp = largest_gap_phase(occupied)
        lx, ly = polar(r - 9, lp)
        cosv = math.cos(lp * 2 * math.pi - math.pi / 2)
        anchor = "middle" if abs(cosv) < 0.35 else ("start" if cosv > 0 else "end")
        p.append('<text class="ringlabel" x="%.1f" y="%.1f" '
                 'text-anchor="%s">%s</text>'
                 % (lx, ly, anchor, html.escape(humanise_period(period))))

    # The outer dashed ring is where cycles go when nobody has published how
    # long they are. It is drawn beyond everything known and is explicitly not
    # to scale, because there is no scale to place them on.
    if unquantified:
        p.append('<circle class="ring unknownring" cx="0" cy="0" r="%.1f"/>'
                 % R_UNKNOWN)
        step = 1.0 / (len(unquantified) + 1)
        for i, c in enumerate(unquantified, start=1):
            ph = 0.08 + step * i * 0.6
            x, y = polar(R_UNKNOWN, ph)
            p.append('<a href="#%s"><title>%s -- %s (no published length)'
                     '</title><circle class="dot hollow" cx="%.1f" cy="%.1f" '
                     'r="5.5" stroke="%s"/></a>'
                     % (c["id"], html.escape(c["title"]), html.escape(c["when"]),
                        x, y, KIND_COLOUR.get(c["kind"], "var(--ink-2)")))
        p.append('<text class="ringlabel unknownlabel" x="0" y="%.1f" '
                 'text-anchor="middle">unquantified &mdash; not to scale</text>'
                 % (R_UNKNOWN - 9))

    p.append('<line class="spoke" x1="0" y1="%.1f" x2="0" y2="%.1f"/>'
             % (-R_CORE, -(R_MAX + 12)))
    p.append('<text class="spokelabel" x="6" y="%.1f">start of period</text>'
             % (-(R_MAX + 16)))
    p.append("</svg>")
    return "\n".join(p)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

CSS = """
	/* Scoped to this page. Nothing here touches css/site.css -- a light-theme
	   literal in that file once whited out cards across the whole site. */
	:root{
		--bg:#12100F; --panel:#1C1917; --panel-2:#262220; --hair:#3A342E; --hair-2:#2a2622;
		--ink:#E9F2F2; --ink-2:#CFC7BB; --ink-3:#A79E92;
		--amber:#F6A800; --teal:#2FD4C2; --doom:#E2524A; --phosphor:#5BE87A;
		--mono:ui-monospace,"SFMono-Regular",Menlo,"Courier New",monospace;
	}
	*{margin:0;padding:0;box-sizing:border-box}
	html{color-scheme:dark}
	body{background:var(--bg); color:var(--ink); font-family:var(--mono); line-height:1.6;
		-webkit-font-smoothing:antialiased;
		background-image:radial-gradient(60rem 40rem at 50% -10%, rgba(47,212,194,.05), transparent 60%);
		background-attachment:fixed;}
	main{max-width:min(980px,92vw); margin:0 auto; padding:2rem 0 4rem}
	.intro h1{font-size:clamp(1.7rem,5vw,2.5rem); letter-spacing:.01em; text-wrap:balance}
	.intro h1 b{color:var(--teal)}
	.intro p{color:var(--ink-2); max-width:52rem; margin-top:.7rem; text-wrap:pretty}
	.tag{display:inline-block; margin-top:.9rem; font-size:.7rem; letter-spacing:.14em;
		text-transform:uppercase; color:var(--ink-3); border:1px solid var(--hair);
		padding:.3rem .6rem; border-radius:999px}
	.rack{background:var(--panel); border:1px solid var(--hair); border-radius:14px;
		padding:1.3rem 1.4rem; margin-top:1.4rem}
	.rack > h2{font-size:.76rem; letter-spacing:.16em; text-transform:uppercase;
		color:var(--ink-3); margin-bottom:1rem; font-weight:700}
	.rack > p{color:var(--ink-2); font-size:.86rem; margin-bottom:.9rem; text-wrap:pretty}
	.scroll{overflow-x:auto}
	table{border-collapse:collapse; width:100%; font-size:.8rem; min-width:640px}
	th{text-align:left; font-size:.66rem; letter-spacing:.12em; text-transform:uppercase;
		color:var(--ink-3); padding:.4rem .6rem .5rem; border-bottom:1px solid var(--hair)}
	td{padding:.55rem .6rem; border-bottom:1px solid var(--hair-2); vertical-align:top;
		color:var(--ink-2)}
	td b{color:var(--ink)}
	tr:target td{background:rgba(47,212,194,.09)}
	tr:target td:first-child{box-shadow:inset 3px 0 0 var(--teal)}
	.prov a{color:var(--amber); text-decoration:none; font-size:.74rem;
		white-space:nowrap; border-bottom:1px dotted rgba(246,168,0,.5)}
	.prov a:hover{border-bottom-style:solid}
	.pill{display:inline-block; font-size:.62rem; letter-spacing:.1em; text-transform:uppercase;
		padding:.1rem .4rem; border-radius:4px; white-space:nowrap}
	.p-auto{color:var(--teal); border:1px solid rgba(47,212,194,.4)}
	.p-up{color:var(--amber); border:1px solid rgba(246,168,0,.45)}
	.p-cross{color:var(--phosphor); border:1px solid rgba(91,232,122,.4)}
	.p-clock{color:var(--ink-3); border:1px solid var(--hair)}
	.p-warn{color:var(--doom); border:1px solid rgba(226,82,74,.45)}
	.p-ok{color:var(--phosphor); border:1px solid rgba(91,232,122,.4)}
	.unknown{color:var(--ink-3); font-style:italic}
	.figwrap{display:grid; grid-template-columns:minmax(0,1fr) minmax(0,15rem); gap:1.2rem;
		align-items:start}
	@media (max-width:760px){.figwrap{grid-template-columns:minmax(0,1fr)}}
	.epi{width:100%; height:auto; display:block}
	.epi .ring{fill:none; stroke:var(--hair); stroke-width:1}
	.epi .unknownring{stroke:var(--hair-2); stroke-dasharray:6 7}
	.epi .core{fill:rgba(246,168,0,.10); stroke:var(--amber); stroke-width:1.2}
	.epi .corelabel{fill:var(--amber); font:600 10px var(--mono); text-anchor:middle;
		letter-spacing:.12em; text-transform:uppercase}
	.epi .coreval{fill:var(--ink-2); font:400 11px var(--mono); text-anchor:middle}
	.epi .dot{stroke:var(--bg); stroke-width:2}
	.epi .dot.hollow{fill:var(--bg); stroke-width:2}
	.epi .arc{fill:none; stroke-width:7; stroke-linecap:round; opacity:.85}
	.epi a:hover .dot{r:7.5}
	.epi a:focus-visible{outline:2px solid var(--amber); outline-offset:2px}
	.epi .ringlabel{fill:var(--ink-3); font:400 10px var(--mono);
		paint-order:stroke; stroke:var(--bg); stroke-width:4px; stroke-linejoin:round}
	.epi .unknownlabel{fill:var(--hair)}
	.epi .spoke{stroke:var(--hair-2); stroke-width:1; stroke-dasharray:3 5}
	.epi .spokelabel{fill:var(--hair); font:400 9px var(--mono);
		letter-spacing:.1em; text-transform:uppercase}
	.legend{font-size:.76rem; color:var(--ink-3)}
	.legend h3{font-size:.66rem; letter-spacing:.12em; text-transform:uppercase;
		color:var(--ink-3); margin:.2rem 0 .5rem}
	.legend ul{list-style:none; display:grid; gap:.4rem}
	.legend li{display:flex; gap:.5rem; align-items:baseline; text-wrap:pretty}
	.swatch{width:.62rem; height:.62rem; border-radius:50%; flex:0 0 auto;
		transform:translateY(.05rem)}
	.legend p{margin-top:.7rem; text-wrap:pretty}
	.note{margin-top:1.3rem; font-size:.8rem; color:var(--ink-3); text-wrap:pretty}
	.note b{color:var(--ink-2)}
	a{color:var(--amber)}
	a:focus-visible{outline:2px solid var(--amber); outline-offset:3px}
"""


def esc(value):
    return html.escape(str(value), quote=True)


def prov(c):
    return ('<span class="prov"><a href="%s" rel="noopener">%s</a></span>'
            % (esc(c.url), esc(c.label)))


def workflow_effect(w):
    if w["deploys"]:
        return "rsyncs public/ to production"
    if w["commits"]:
        return ("commits to the repo; the commit does not itself trigger a "
                "deploy")
    if w["commit_step_without_write"]:
        return ("has a git commit step but no contents: write anywhere in the "
                "file, so the commit cannot succeed")
    if w["issues"]:
        return "opens or comments on GitHub issues; touches no site content"
    return "checks only; writes nothing"


def pill(kind):
    cls = {"repo automation": "p-auto", "upstream (mirrored)": "p-up",
           "cross-repo": "p-cross", "declared clock": "p-clock"}.get(kind, "p-clock")
    return '<span class="pill %s">%s</span>' % (cls, esc(kind))


def render_html(data):
    wfs = data["workflows"]
    cycles = data["cycles"]
    meta = data["meta"]
    parts = []
    a = parts.append

    live = sorted([c for c in cycles if c["period"]],
                  key=lambda c: (c["period"], c["title"]))
    unknown = sorted([c for c in cycles if not c["period"]],
                     key=lambda c: c["title"])
    parked = sorted([w for w in wfs if w["park"]], key=lambda w: w["name"])
    eventy = sorted([w for w in wfs if not w["park"] and not w["crons"]],
                    key=lambda w: w["name"])

    a('<!DOCTYPE html>')
    a('<html lang="en-AU">')
    a('<head>')
    a('\t<meta charset="UTF-8">')
    a('\t<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    a('\t<title>Metabolism &mdash; p(Doom)1</title>')
    a('\t<meta name="description" content="Every recurring cycle this project '
      'runs, derived at build time from the files that actually run them.">')
    a('\t<meta name="robots" content="noindex, follow">')
    a('\t<link rel="canonical" href="https://pdoom1.com/metabolism/" />')
    a('\t<!-- Plausible Analytics - Privacy-first, self-hosted -->')
    a('\t<script defer data-domain="pdoom1.com" src="https://analytics.pdoom1.com/'
      'js/script.file-downloads.outbound-links.pageview-props.tagged-events.js"></script>')
    a('\t<script>window.plausible = window.plausible || function() { '
      '(window.plausible.q = window.plausible.q || []).push(arguments) }</script>')
    a('\t<!-- GENERATED FILE. Do not hand-edit: scripts/generate-metabolism.py '
      'rewrites it and CI fails if this file and its sources disagree. -->')
    a('\t<style>%s\t</style>' % CSS)
    a('</head>')
    a('<body>')
    a('\t<header></header>')
    a('\t<main>')

    # -- intro
    a('\t\t<div class="intro">')
    a('\t\t\t<h1>The <b>metabolism</b> of this project</h1>')
    a('\t\t\t<p>Every recurring beat we run, on one page: how fast it turns, when '
      'it fires, and &mdash; for every single number &mdash; which file it was '
      'read out of. Nothing here is typed in. This page is generated by '
      '<code>scripts/generate-metabolism.py</code> from the cron expressions, '
      'config files and ledgers that actually run, and a CI check fails the '
      'build if the page and its sources ever disagree.</p>')
    a('\t\t\t<p>Where a cadence is genuinely unknown, it says unknown. A gap in '
      'the picture is information; a plausible-looking guess would not be.</p>')
    a('\t\t\t<span class="tag">%d live cycles &middot; %d unquantified &middot; '
      '%d parked &middot; %d sources read</span>'
      % (len(live), len(unknown), len(parked), data["source_count"]))
    a('\t\t</div>')

    # -- diagram
    a('\t\t<section class="rack">')
    a('\t\t\t<h2>The epicycles</h2>')
    a('\t\t\t<p>One ring per distinct period, log-spaced: fastest innermost, '
      'slowest outermost. Every ring&rsquo;s radius is computed from its period, '
      'so the picture cannot drift from the table below it. Twelve o&rsquo;clock '
      'is the start of each ring&rsquo;s period; a marker sits at the point in '
      'the cycle when that job fires, which is why markers stacked along one '
      'radius are jobs that fire at the same instant. Click any marker to jump '
      'to its row.</p>')
    a('\t\t\t<div class="figwrap">')
    a('\t\t\t\t<div>%s</div>' % data["svg"])
    a('\t\t\t\t<div class="legend">')
    a('\t\t\t\t\t<h3>Reading the map</h3>')
    a('\t\t\t\t\t<ul>')
    for kind, colour in sorted(KIND_COLOUR.items()):
        a('\t\t\t\t\t\t<li><span class="swatch" style="background:%s"></span>'
          '<span>%s</span></li>' % (colour, esc(kind)))
    a('\t\t\t\t\t\t<li><span class="swatch" style="background:transparent;'
      'border:2px solid var(--ink-3)"></span><span>hollow: period known, '
      'firing time not published</span></li>')
    a('\t\t\t\t\t</ul>')
    a('\t\t\t\t\t<p>An arc instead of a dot is a <b>window</b>: the event lands '
      'somewhere inside it, and nobody has published where. The arc covers the '
      'whole window rather than asserting a moment.</p>')
    a('\t\t\t\t\t<p>Dots stacked outward along one radius fire at the <b>same '
      'instant</b>. That is a real collision, not a drawing artefact.</p>')
    a('\t\t\t\t\t<p>The amber disc at the centre is the deploy path. It is a '
      '<b>latency, not a period</b>, so it is drawn as a disc rather than a '
      'ring: pushing to <code>main</code> is what triggers it, not a clock.</p>')
    if unknown:
        a('\t\t\t\t\t<p>The dashed outer ring holds cycles whose length nobody '
          'has published. It is drawn outside everything known and is '
          'deliberately not to scale.</p>')
    a('\t\t\t\t\t<p>%s</p>' % esc(meta["period_seconds"]["_note"]))
    a('\t\t\t\t</div>')
    a('\t\t\t</div>')
    a('\t\t</section>')

    # -- live table
    a('\t\t<section class="rack">')
    a('\t\t\t<h2>Live cadences</h2>')
    a('\t\t\t<p>Sorted fastest to slowest. The provenance column is the point of '
      'this table: every cadence links to the exact line it was read from.</p>')
    a('\t\t\t<div class="scroll"><table>')
    a('\t\t\t\t<thead><tr><th>Cycle</th><th>Period</th><th>Fires</th>'
      '<th>Read from</th><th>Notes</th></tr></thead>')
    a('\t\t\t\t<tbody>')
    for c in live:
        # A row whose period is known but whose next date is not says so here,
        # rather than leaving a reader to assume the cadence implies a date.
        note = "; ".join(x for x in (c["note"], c.get("unknown_reason")) if x)
        a('\t\t\t\t\t<tr id="%s"><td><b>%s</b><br>%s</td><td>%s</td><td>%s</td>'
          '<td>%s</td><td>%s</td></tr>'
          % (esc(c["id"]), esc(c["title"]), pill(c["kind"]),
             esc(humanise_period(c["period"])), esc(c["when"]),
             prov(c["cite"]), esc(note) if note else '&mdash;'))
    a('\t\t\t\t</tbody>')
    a('\t\t\t</table></div>')
    a('\t\t</section>')

    # -- deploy / event-driven
    a('\t\t<section class="rack">')
    a('\t\t\t<h2>The event-driven beat</h2>')
    a('\t\t\t<p>These have no period at all. They fire when something happens, '
      'which is a different kind of rhythm and is shown separately so it cannot '
      'be misread as a schedule.</p>')
    a('\t\t\t<div class="scroll"><table>')
    a('\t\t\t\t<thead><tr><th>What</th><th>Triggered by</th><th>Read from</th>'
      '<th>Notes</th></tr></thead>')
    a('\t\t\t\t<tbody>')
    for f in data["deploy_facts"]:
        a('\t\t\t\t\t<tr id="%s"><td><b>%s</b><br>'
          '<span class="pill p-warn">%s</span></td><td>%s</td><td>%s</td>'
          '<td>%s</td></tr>'
          % (esc("fact-" + f["id"]), esc(f["claim"]), esc(f["confidence"]),
             esc(f["value"]), prov(f["cite"]), esc(f["caveat"])))
    for w in eventy:
        a('\t\t\t\t\t<tr><td><b>%s</b><br><span class="pill p-auto">workflow'
          '</span></td><td>%s</td><td>%s</td><td>%s</td></tr>'
          % (esc(w["name"]), esc(", ".join(w["triggers"])),
             prov(w["cite_name"]), esc(workflow_effect(w))))
    a('\t\t\t\t</tbody>')
    a('\t\t\t</table></div>')
    a('\t\t</section>')

    # -- parked
    a('\t\t<section class="rack">')
    a('\t\t\t<h2>Parked &mdash; not a cadence</h2>')
    a('\t\t\t<p>These workflows look like automation and are not. Each was '
      'deliberately reduced to manual dispatch, and each carries a comment '
      'saying why; that comment is quoted here rather than summarised. Showing '
      'them as live beats would be the exact lie this page exists to avoid. '
      'The generator refuses to build if any of them still carries a '
      'schedule.</p>')
    a('\t\t\t<div class="scroll"><table>')
    a('\t\t\t\t<thead><tr><th>Workflow</th><th>Marker</th>'
      '<th>Stated reason</th><th>Read from</th></tr></thead>')
    a('\t\t\t\t<tbody>')
    for w in parked:
        a('\t\t\t\t\t<tr><td><b>%s</b></td><td><span class="pill p-warn">%s'
          '</span></td><td>%s</td><td>%s</td></tr>'
          % (esc(w["name"]), esc(w["park"][0]), esc(w["park"][1]),
             prov(w["cite_name"])))
    a('\t\t\t\t</tbody>')
    a('\t\t\t</table></div>')
    a('\t\t</section>')

    # -- unknown
    a('\t\t<section class="rack">')
    a('\t\t\t<h2>Unquantified &mdash; the holes in the picture</h2>')
    a('\t\t\t<p>Cycles we know exist but whose length or timing nobody has '
      'published. They are listed rather than estimated.</p>')
    a('\t\t\t<div class="scroll"><table>')
    a('\t\t\t\t<thead><tr><th>Cycle</th><th>What we know</th>'
      '<th>Why there is no number</th><th>Read from</th></tr></thead>')
    a('\t\t\t\t<tbody>')
    for c in unknown:
        a('\t\t\t\t\t<tr id="%s"><td><b>%s</b><br>%s</td><td>%s</td>'
          '<td class="unknown">%s</td><td>%s</td></tr>'
          % (esc(c["id"]), esc(c["title"]), pill(c["kind"]), esc(c["when"]),
             esc(c["unknown_reason"] or "no source publishes a period"),
             prov(c["cite"])))
    a('\t\t\t\t</tbody>')
    a('\t\t\t</table></div>')
    a('\t\t</section>')

    # -- cross-repo
    cr = meta["cross_repo"]
    a('\t\t<section class="rack">')
    a('\t\t\t<h2>The cross-repo rhythm</h2>')
    a('\t\t\t<p><b>%s</b> &mdash; %s. This repository is the <b>publisher</b>, '
      'never the source: it reads pdoom1, never the reverse. Our leg is at '
      '<span class="pill p-ok">%s</span> on the ladder %s. The rule itself lives '
      'upstream at <code>%s</code>; this repo holds a declared mirror with a '
      'pointer, because pdoom1 publishes no artifact for it.</p>'
      % (esc(cr["title"]), esc(cr["shape"]), esc(cr["our_state"]),
         esc(" &rarr; ".join(cr["ratification_ladder"])).replace("&amp;", "&"),
         esc(cr["source"])))
    a('\t\t\t<div class="scroll"><table>')
    a('\t\t\t\t<thead><tr><th>Unit</th><th>When</th><th>Forks the board?</th>'
      '<th>Version effect</th><th>Read from</th></tr></thead>')
    a('\t\t\t\t<tbody>')
    for mc in meta["mirrored_cycles"]:
        forks = ("yes, by definition" if mc["forks_board"] else
                 ("no" if mc["forks_board"] is False else "n/a &mdash; a container"))
        a('\t\t\t\t\t<tr><td><b>%s</b><br><span class="pill p-up">mirrored from '
          '%s</span></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
          % (esc(mc["title"]), esc(mc["source"]), esc(mc["when"]), forks,
             esc(mc["version_effect"]),
             prov(cite(METABOLISM_JSON, '"id": "%s"' % mc["id"]))))
    a('\t\t\t\t</tbody>')
    a('\t\t\t</table></div>')
    hop = next(h for h in cr["hops"] if h["id"] == "hop-b")
    a('\t\t\t<p class="note"><b>Our leg (%s):</b> %s. It fires by <b>%s</b> &mdash; '
      '%s</p>' % (esc(hop["name"]), esc(hop["trigger"]), esc(hop["fires_by"]),
                  esc(hop["fires_by_note"])))
    for gap in hop["known_gaps"]:
        a('\t\t\t<p class="note">&mdash; %s</p>' % esc(gap))
    for edge in cr["extra_edges"]:
        a('\t\t\t<p class="note"><b>%s</b> (%s): %s</p>'
          % (esc(edge["name"]), esc(edge["status"]), esc(edge["note"])))
    a('\t\t</section>')

    # -- ledger
    a('\t\t<section class="rack">')
    a('\t\t\t<h2>League epochs, as blessed</h2>')
    a('\t\t\t<p>An epoch becomes real when Pip blesses a seed into the ledger. '
      'This table is read straight out of it, so a row that has not been blessed '
      'cannot appear here.</p>')
    a('\t\t\t<div class="scroll"><table>')
    a('\t\t\t\t<thead><tr><th>Epoch</th><th>Seed</th><th>Ladder</th>'
      '<th>Blessed (UTC)</th><th>By</th><th>Read from</th></tr></thead>')
    a('\t\t\t\t<tbody>')
    for row in data["ledger"]:
        a('\t\t\t\t\t<tr><td><b>%s</b></td><td><code>%s</code></td><td>%s</td>'
          '<td>%s</td><td>%s</td><td>%s</td></tr>'
          % (esc(row["epoch"]), esc(row["seed"]), esc(row["ladder"]),
             esc(row["blessed"]), esc(row["by"]), prov(row["cite"])))
    if data["next_epoch"]:
        a('\t\t\t\t\t<tr><td><b>%s</b></td><td colspan="4" class="unknown">'
          'not blessed yet &mdash; there is no %s row in the ledger, so this '
          'page has nothing to show. It appears here the moment one is '
          'added.</td><td>%s</td></tr>'
          % (esc(data["next_epoch"]), esc(data["next_epoch"]),
             prov(cite_file(SEED_LEDGER))))
    a('\t\t\t\t</tbody>')
    a('\t\t\t</table></div>')
    a('\t\t</section>')

    # -- derived checks
    a('\t\t<section class="rack">')
    a('\t\t\t<h2>Cross-checks the generator ran</h2>')
    a('\t\t\t<p>Several sources describe overlapping beats &mdash; three of them '
      'describe the weekly league alone. Rather than pick one and hope, the '
      'generator compares them and prints what it found, including when they '
      'disagree. A disagreement here is a real finding, not a rendering bug, '
      'and it recomputes on every build rather than being written down once.</p>')
    a('\t\t\t<div class="scroll"><table>')
    a('\t\t\t\t<thead><tr><th>Check</th><th>Result</th><th>Read from</th>'
      '</tr></thead>')
    a('\t\t\t\t<tbody>')
    for chk in data["checks"]:
        a('\t\t\t\t\t<tr><td><b>%s</b></td><td><span class="pill %s">%s</span> '
          '%s</td><td>%s</td></tr>'
          % (esc(chk["name"]), chk["cls"], esc(chk["verdict"]),
             esc(chk["detail"]),
             " ".join(prov(c) for c in chk["cites"])))
    a('\t\t\t\t</tbody>')
    a('\t\t\t</table></div>')
    a('\t\t</section>')

    # -- sources
    a('\t\t<section class="rack">')
    a('\t\t\t<h2>Everything this page was built from</h2>')
    a('\t\t\t<p>If a file is not on this list, nothing on this page came from '
      'it. Editing any of them and not re-running the generator fails CI.</p>')
    a('\t\t\t<div class="scroll"><table>')
    a('\t\t\t\t<thead><tr><th>Source</th><th>What was taken from it</th>'
      '</tr></thead>')
    a('\t\t\t\t<tbody>')
    for src, what in data["source_index"]:
        a('\t\t\t\t\t<tr><td>%s</td><td>%s</td></tr>'
          % (prov(cite_file(src)), esc(what)))
    a('\t\t\t\t</tbody>')
    a('\t\t\t</table></div>')
    a('\t\t</section>')

    a('\t\t<p class="note"><b>Why there is no &ldquo;last updated&rdquo; stamp '
      'on this page:</b> a timestamp would tell you when the file was written, '
      'not whether it is still true, and it would make the CI staleness check '
      'impossible &mdash; every run would produce a different file. The check '
      'is the freshness guarantee instead: this page cannot be more than one '
      'merged pull request away from its sources.</p>')
    a('\t\t<p class="note">Soft preview: this page is <code>noindex</code> and '
      'not linked from the navigation yet.</p>')
    a('\t</main>')
    a('\t<script src="/assets/js/navigation.js"></script>')
    a('</body>')
    a('</html>')
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build():
    meta = json.loads(METABOLISM_JSON.read_text(encoding="utf-8"))
    PERIOD_NAMES.clear()
    PERIOD_NAMES.update({v: k for k, v in meta["period_seconds"].items()
                         if isinstance(v, int)})
    clocks = json.loads(CLOCKS_JSON.read_text(encoding="utf-8"))
    league_cfg = json.loads(LEAGUE_CONFIG.read_text(encoding="utf-8"))
    workflows = load_workflows()
    cycles = build_cycles(workflows, clocks, meta)
    ledger = parse_ledger(SEED_LEDGER)

    deploy_facts = []
    for f in meta["documented_facts"]:
        deploy_facts.append(dict(
            f, cite=cite(REPO_ROOT / f["cite_file"], f["cite_needle"],
                         render_line=False)))

    # --- cross-checks -------------------------------------------------------
    checks = []

    reset = next((w for w in workflows
                  if w["file"].name == "weekly-league-reset.yml"), None)
    if reset is None:
        raise SourceError("weekly-league-reset.yml has vanished")

    # A PARKED league rollover is a legitimate state and a different one from a
    # schedule that silently disappeared. This used to raise on both, which meant
    # the page could not be regenerated at all while the rollover was parked --
    # and the pressure then is to un-park the workflow to get CI green, i.e. to
    # re-arm an unattended production publish for the sake of a build.
    #
    # The parked case is rendered, not skipped. Checks 1-3 below replay a cron
    # that is not currently firing, so running them would publish a cadence to a
    # visitor that no job is keeping. Instead this states the park, and states
    # that clocks.json still DECLARES an anchor -- because that is the thing a
    # reader could be misled by, and it is true whether or not anyone noticed.
    if not reset["crons"]:
        if not reset["park"]:
            raise SourceError(
                "weekly-league-reset.yml has no schedule and no park notice. A "
                "cadence vanished without anybody saying so -- add a park marker "
                "with a reason, or restore the schedule.")
        _declared = next((c for c in clocks["clocks"]
                          if (c.get("cadence") or {}).get("anchor_utc")), None)
        checks.append({
            "name": "The weekly league rollover is PARKED, not running",
            "verdict": "PARKED",
            "cls": "p-warn",
            "detail": ("%s carries the park marker %r and has no schedule, so "
                       "no league week rolls over on a clock right now; it runs "
                       "only when a person dispatches it. Reason recorded in the "
                       "workflow: %s%s"
                       % (reset["file"].name, reset["park"][0],
                          reset["park"][1],
                          (" clocks.json still declares an anchor of %s, which "
                           "is what the league WILL resume to -- it is not a "
                           "cadence anything is keeping today."
                           % _declared["cadence"]["anchor_utc"])
                          if _declared else "")),
            "cites": ([cite(CLOCKS_JSON, '"anchor_utc"')] if _declared else [])
                     + [reset["cite_name"]],
        })
        reset_cron = None
        reset_parsed = None
    else:
        reset_cron = reset["crons"][0]
        reset_parsed = reset_cron["parsed"]

    # 1. clocks.json's declared anchor vs the cron that actually runs.
    league_clock = next((c for c in clocks["clocks"]
                         if (c.get("cadence") or {}).get("anchor_utc")), None)
    # `and reset_cron` -- while the rollover is parked there is no cron to
    # compare the declared anchor against, and the parked state is already
    # reported above. Rendering an "agree" here would be agreeing with nothing.
    if league_clock and reset_cron:
        anchor = league_clock["cadence"]["anchor_utc"]
        m = re.match(r"([A-Za-z]{3})\s+(\d{1,2}):(\d{2})", anchor)
        declared = "%s %02d:%02d UTC weekly" % (m.group(1), int(m.group(2)),
                                                int(m.group(3)))
        agree = reset_parsed and declared == reset_parsed["phase_label"]
        checks.append({
            "name": "Declared league anchor matches the cron that runs",
            "verdict": "agree" if agree else "DISAGREE",
            "cls": "p-ok" if agree else "p-warn",
            "detail": ("clocks.json declares %s; %s fires %s."
                       % (declared, reset["file"].name,
                          reset_parsed["phase_label"] if reset_parsed
                          else reset_cron["expr"]))
            + ("" if agree else " The page a visitor reads and the job that runs "
                                "disagree; one of them is wrong."),
            "cites": [cite(CLOCKS_JSON, '"anchor_utc"'), reset_cron["cite"]],
        })

    # 2. The cron, converted to the league's own competition timezone, versus
    #    the reset day/time the league config declares.
    offsets = hobart_offsets(meta["dst_probe_instants"])
    if reset_parsed and reset_parsed["period"] == 604800:
        ref = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)  # a Monday
        fire = ref + dt.timedelta(seconds=reset_parsed["phase"] * 604800)
        locals_ = []
        for key in sorted(offsets):
            off = offsets[key]
            lt = fire + dt.timedelta(hours=off["offset_hours"])
            locals_.append("%s %02d:%02d %s (UTC%+g)"
                           % (["Mon", "Tue", "Wed", "Thu", "Fri", "Sat",
                               "Sun"][lt.weekday()], lt.hour, lt.minute,
                              off["abbrev"], off["offset_hours"]))
        want = "%s %s" % (league_cfg["league_reset_day"][:3],
                          league_cfg["league_reset_time"])
        hit = [s for s in locals_ if s.startswith(want[:3])
               and s[4:9] == league_cfg["league_reset_time"]]
        checks.append({
            "name": "Cron lands on the league's declared local reset time",
            "verdict": "half" if (hit and len(hit) < len(locals_))
                       else ("agree" if hit else "DISAGREE"),
            "cls": "p-warn" if len(hit) != len(locals_) else "p-ok",
            "detail": ("config wants %s %s in %s; the cron lands at %s. "
                       "Daylight saving moves it, so the declared time holds in "
                       "only %d of the %d offsets this timezone takes."
                       % (league_cfg["league_reset_day"],
                          league_cfg["league_reset_time"],
                          league_cfg["competition_timezone"],
                          " and ".join(locals_), len(hit), len(locals_))),
            "cites": [cite(LEAGUE_CONFIG, '"league_reset_day"'),
                      reset_cron["cite"]],
        })

    # 3. Which week does the rollover actually open? Replayed, not asserted.
    roll = derive_rollover_phase(reset_cron["expr"]) if reset_cron else None
    if roll:
        off_by_one = roll["hours_to_week_end"] < 24
        checks.append({
            "name": "The week the rollover opens is the week that is starting",
            "verdict": "OFF BY ONE" if off_by_one else "agree",
            "cls": "p-warn" if off_by_one else "p-ok",
            "detail": ("Replaying get_current_week_info()'s arithmetic at the "
                       "cron's firing moment (%s): the week it derives began "
                       "%.1f h earlier and ends %.1f h later. %s"
                       % (roll["fires_at"], roll["hours_into_week"],
                          roll["hours_to_week_end"],
                          "The rollover therefore creates the week that is "
                          "about to end, not the one about to begin."
                          if off_by_one else
                          "The week it opens is the one about to run.")),
            # The needle was "days_since_monday = now.weekday()" until 2026-07-31. PR #187
            # replaced Monday-anchored UTC arithmetic with a Friday/Hobart anchor and
            # renamed the line; PR #188 added this citation pointing at a line that #187
            # had ALREADY deleted. So --check has failed since the day it shipped, which
            # (a) blocked every PR touching the watched paths and (b) froze
            # public/metabolism/index.html at its pre-#187 state, leaving the page telling
            # readers the reset day is Monday while the config says Friday.
            #
            # The guard behaved correctly -- it refused to build rather than publish an
            # uncheckable claim. It was the citation that was wrong, not the mechanism.
            "cites": [cite(LEAGUE_MANAGER,
                           "days_since_anchor = (local.weekday() - ANCHOR_WEEKDAY) % 7"),
                      reset_cron["cite"]],
        })

    # 4. Does anything actually publish on the cross-repo beat?
    hop_b = next(h for h in meta["cross_repo"]["hops"] if h["id"] == "hop-b")
    dispatchers = sorted(w["name"] for w in workflows
                         if not w["park"] and "repository_dispatch" in w["triggers"])
    checks.append({
        "name": "A machine signal exists for the monthly cross-repo beat",
        "verdict": "NO",
        "cls": "p-warn",
        "detail": ("This repo can RECEIVE repository_dispatch on %d live "
                   "workflow(s) (%s), but nothing upstream sends one on Epoch "
                   "Friday, so the leg fires by %s."
                   % (len(dispatchers), ", ".join(dispatchers) or "none",
                      hop_b["fires_by"])),
        "cites": [cite(METABOLISM_JSON, '"fires_by"')],
    })

    # 5. Bot-committed artifacts vs the deploy trigger.
    #
    # CORRECTED 2026-08-04. This check used to render verdict NO -- "none of them
    # reaches pdoom1.com until the next human push". That was true when written and
    # is now false: auto-deploy-on-push.yml carries a `workflow_run` trigger on the
    # board-liveness workflow, which runs 6-hourly, so a full rsync --delete of
    # public/ fires ~4x/day whoever committed. Verified against production: bot
    # commits written 00:46Z were live by 00:57Z.
    #
    # The verdict flips to YES, but the CLASS stays a warning, because the risk
    # inverted rather than went away: `types: [completed]` carries no conclusion
    # filter and the deploy job runs no tests, so those ~4 daily unattended
    # production deploys are gated by nothing.
    committing = sorted(w["name"] for w in workflows if w["commits"] and not w["park"])
    checks.append({
        "name": "Automated commits reach production on their own",
        "verdict": "YES",
        "cls": "p-warn",
        "detail": ("%d live workflow(s) commit to the repository, and all of them "
                   "now reach pdoom1.com without a human: auto-deploy-on-push.yml "
                   "triggers on the 6-hourly board-liveness run, so public/ is "
                   "rsynced ~4x a day whoever committed. The flip side is that "
                   "those deploys are gated by nothing -- the trigger has no "
                   "conclusion filter and the deploy job runs no tests. "
                   "Committing workflows: %s."
                   % (len(committing), ", ".join(committing))),
        "cites": [cite(REPO_ROOT / "CLAUDE.md",
                       "bot commits DO reach production now", render_line=False)],
    })

    # 6. A commit step with no write permission is a beat that looks live and
    #    is not. Derived, because the permission can be overridden per job.
    toothless = sorted(w["name"] for w in workflows
                       if w["commit_step_without_write"] and not w["park"])
    checks.append({
        "name": "Every live workflow with a commit step can actually commit",
        "verdict": "yes" if not toothless else "NO",
        "cls": "p-ok" if not toothless else "p-warn",
        "detail": ("Checked each file for contents: write at any level, "
                   "workflow or job. %s"
                   % ("All commit steps are backed by write permission."
                      if not toothless else
                      "These have a git commit step and no write grant, so the "
                      "step fails silently: %s." % ", ".join(toothless))),
        "cites": [cite_file(WORKFLOW_DIR)],
    })

    # 7. Do any scheduled jobs fire at the identical instant? Cheap to see once
    #    every cron is parsed into (period, phase), and invisible otherwise.
    slots = {}
    for c in cycles:
        if c["period"] and c["phase"] is not None and c.get("diagram", True):
            slots.setdefault((c["period"], round(c["phase"], 6)), []).append(
                c["title"])
    clashes = sorted((sorted(v), k) for k, v in slots.items() if len(v) > 1)
    checks.append({
        "name": "Scheduled jobs are spread out rather than piled on one instant",
        "verdict": "no" if clashes else "yes",
        "cls": "p-warn" if clashes else "p-ok",
        "detail": ("Comparing every parsed cron as (period, phase). "
                   + ("; ".join("%d jobs share %s: %s"
                                % (len(names), humanise_period(k[0]),
                                   ", ".join(names))
                                for names, k in clashes)
                      + ". They contend for the same runner minute and, because "
                        "several of them commit, for the same branch tip."
                      if clashes else
                      "No two parsed schedules land on the same moment.")),
        "cites": [cite_file(WORKFLOW_DIR)],
    })

    # 8. The monthly beat has a published decision record. Read its live status
    #    line rather than restating it: an ADR that re-syncs with a different
    #    status changes this row without anyone editing the page.
    hop_a = next(h for h in meta["cross_repo"]["hops"] if h["id"] == "hop-a")
    adr = None
    if hop_a.get("cadence_source_file"):
        adr = REPO_ROOT / hop_a["cadence_source_file"]
    if adr:
        m = re.search(r"<strong>Status:</strong>\s*(.*?)\s*&middot;",
                      adr.read_text(encoding="utf-8"))
        if not m:
            raise SourceError(
                "could not read the Status line out of %s. The design-notes "
                "renderer changed shape; fix the pattern rather than dropping "
                "the check." % adr)
        status = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        settled = status.upper().startswith("ACCEPTED") and "owed" not in status
        checks.append({
            "name": "The monthly cycle's decision record is fully settled",
            "verdict": "yes" if settled else "not yet",
            "cls": "p-ok" if settled else "p-warn",
            "detail": ("ADR-0016 defines the monthly world-update cycle and is "
                       "published here unedited from pdoom1. Its own status "
                       "line reads: %s" % status),
            # The ADR states its status twice (header block and body list);
            # the header is the one the renderer builds, so take the first.
            "cites": [cite(adr, "<strong>Status:</strong>", occurrence="first")],
        })

    source_index = [
        (WORKFLOW_DIR, "%d workflow files: name, triggers, cron expressions, "
                       "park notices, whether they deploy or commit"
                       % len(workflows)),
        (CLOCKS_JSON, "declared internal cadences and their anchors"),
        (METABOLISM_JSON, "the cadences that cannot be derived here: pdoom1's "
                          "release nomenclature, the cross-repo cycle, and two "
                          "documented-not-measured facts"),
        (LEAGUE_CONFIG, "competition timezone, declared league reset day and time"),
        (LEAGUE_MANAGER, "the week arithmetic the rollover actually performs"),
        (SEED_LEDGER, "blessed epochs, seeds and ladder versions"),
        (REPO_ROOT / "CLAUDE.md", "two facts with no in-repo measurement, each "
                                  "cited to the line that states them"),
    ]
    if adr:
        source_index.append(
            (adr, "the monthly world-update cycle and its live status line, "
                  "published unedited from pdoom1's decision records"))
    source_index.sort(key=lambda pair: pair[0].as_posix())

    svg = render_svg(cycles, deploy_facts[0])

    return render_html({
        "workflows": workflows,
        "cycles": cycles,
        "meta": meta,
        "ledger": ledger,
        "next_epoch": next_epoch_label(ledger),
        "deploy_facts": deploy_facts,
        "checks": checks,
        "svg": svg,
        "source_index": source_index,
        "source_count": len(workflows) + len(source_index) - 1,
    })



def _diff_is_only_anchors(current, fresh):
    """True when the ONLY differences are file:line anchors in citation links.

    Citations render as ...blob/main/<path>#L<n>. When something is inserted above
    a cited line every anchor below it shifts, and the page is 'stale' without a
    single fact having changed. Normalising the anchors away tells the two
    incidents apart; it is deliberately conservative -- anything else differing
    means CONTENT, and the caller says so.
    """
    anchor = re.compile(r"#L\d+")
    return anchor.sub("#L0", current) == anchor.sub("#L0", fresh)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the committed page is stale; write nothing")
    args = ap.parse_args()

    try:
        page = build()
    except SourceError as exc:
        print("SOURCE ERROR: %s" % exc, file=sys.stderr)
        return 2

    if args.check:
        if not OUT.exists():
            print("STALE: %s does not exist. Run: python "
                  "scripts/generate-metabolism.py"
                  % OUT.relative_to(REPO_ROOT).as_posix())
            return 1
        current = OUT.read_text(encoding="utf-8")
        if current != page:
            # WHICH CLASS OF STALE? These are different incidents that printed the
            # same words, and twice in four days someone (me) spent twenty minutes
            # hunting a cadence change that had never happened. A citation is a
            # file:line ANCHOR, so it moves whenever anything above it moves --
            # the fact is identical and only its coordinates changed. Say so.
            only_anchors = _diff_is_only_anchors(current, page)
            if only_anchors:
                print("STALE (COORDINATES ONLY): %s cites its sources by file:line, "
                      "and a cited line has MOVED.\n"
                      "  NO cadence, cron or park notice changed -- something was "
                      "inserted above a citation.\n"
                      "  This is expected after editing any cited file. Regenerate:\n"
                      "    python scripts/generate-metabolism.py"
                      % OUT.relative_to(REPO_ROOT).as_posix())
            else:
                print("STALE (CONTENT): %s no longer matches what its sources "
                      "produce.\n"
                      "  A cadence, a cron or a park notice has genuinely CHANGED -- "
                      "read the diff before regenerating.\n"
                      "  Regenerate:\n    python scripts/generate-metabolism.py"
                      % OUT.relative_to(REPO_ROOT).as_posix())
            return 1
        print("OK: /metabolism/ is in step with its sources.")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8", newline="\n")
    print("Wrote %s (%d bytes)"
          % (OUT.relative_to(REPO_ROOT).as_posix(), len(page)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
