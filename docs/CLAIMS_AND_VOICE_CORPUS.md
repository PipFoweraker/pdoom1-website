# Claims & voice corpus

Pip's own words about p(Doom)1, captured verbatim from each surface as it is
published, so that:

1. the **claims** we make can be checked against each other for consistency and
   truth (this repo's first rule is never lying to a visitor), and
2. the **taglines** have a real corpus behind them rather than being reinvented
   per page — Pip wants to A/B test these, which needs candidates that were
   actually written rather than generated.

**Rule for this file: quote, never paraphrase.** A paraphrase in a corpus is a
mutation that later gets treated as source. Where something is summarised, mark
it. Record the date and URL of every capture.

---

## Capture: Manifund funding ask — 2026-07-29

**Source:** <https://manifund.org/projects/fund-development-of-pdoom1>
**Posted:** ~2026-07-29 10:46 Hobart (00:46 UTC). **Closes:** 2026-09-09.

### The ask
| | |
|---|---|
| Minimum | **USD 14,500** |
| Target | **USD 48,000** |
| Raised at capture | **USD 1,000** (first offer, Austin Chen, within ~5 min) |
| Itemised budget | **none published** |

USD 500 of the minimum is deliberately earmarked by Pip to celebrate and buy
Kambu a treat if the round funds. Reserve it in any spend plan; it is not slack.

### Verbatim — the strongest lines

> "p(Doom)1 is a nightmarishly hard, weird side project where players attempt to
> battle an inexorable rise in, you guessed it, p(Doom)."

> "I took the advice 'write what you know' literally. The game is about the
> challenge facing real AI safety researchers, grantmakers and philanthropists,
> wrapped up in a way that hopefully communicates the challenge while mitigating
> the actual despair."

> **"You can't win; you can only buy time. There's no victory condition. Your
> score is how long you hold P(Doom) back before a run ends."**

The bolded line is the strongest candidate in the corpus: it states a *mechanic*
and a *thesis* in the same breath, and it is falsifiable — anyone can check it by
playing. Compare the homepage, which currently reads "Practice saving the world
from deadly AI through bureaucracy". See the tension logged below.

### Stated influences (Manifund)
> "Magic: the Gathering, PoE, Tarkov, Civ, X:COM, sim games"

Note these are Pip's **personal gaming lineage**, and are a different set from the
**genre ancestors** identified for `/press/` by research on 2026-07-29 —
Bureaucracy (Infocom/Adams, 1987), Papers Please (Pope, 2013), Plague Inc.
(Ndemic, 2012), Democracy (Positech, 2005–), Universal Paperclips (Lantz, 2017).
Both sets are true; they answer different questions ("what shaped me" vs "what
shelf is this on"). Do not merge them into one list.

**Corroboration worth noting:** Tarkov appearing here retro-justifies the
"cozy-Tarkov" reading Pip used to describe the hero art on 2026-07-28. The art
vocabulary and the design lineage are drawing on the same source.

### Factual claims made, and their status
| claim | status |
|---|---|
| "early friends-and-family alpha is out at pdoom1.com" | **True.** v0.13.1 live, downloads resolve on all three platforms. |
| "patched daily currently" | **True as at capture** — pdoom1 confirmed a daily-patch week through Wed 2026-07-30. Time-limited; will stop being true. |
| "open historical AI-safety dataset" | **True** — the pdoom-data repo is public. |
| "None" raised in last 12 months externally | Not independently checked. |

---

## Open tension — flagged, not resolved

**Manifund says there is no victory condition. The homepage says "Practice
saving the world from deadly AI through bureaucracy".**

Neither is false — "practice" is doing careful work in that sentence, and a game
with no win state can still be practice. But they pull in opposite directions for
a first-time reader, and a funder who reads both may notice. Worth a deliberate
decision rather than leaving two surfaces to drift:

- keep both, on the grounds that they address different audiences; or
- bring the homepage closer to the no-win framing, which is more distinctive and
  more honest about the experience; or
- add the no-win line to the homepage *alongside* the existing tagline, so the
  promise is set and then immediately complicated — which is arguably the game's
  actual tone.

**Pip's call.** Logged here so it is not lost.

---

## Tagline candidates (for the A/B set)

Drawn only from things Pip has actually written. Not invented here.

1. "You can't win; you can only buy time."
2. "Your score is how long you hold p(Doom) back."
3. "A nightmarishly hard, weird side project."
4. "Write what you know — taken literally."
5. "Practice saving the world from deadly AI through bureaucracy." *(current homepage)*
6. "A bureaucracy simulator about AI safety, where you run the lab rather than serve it." *(from the /press/ genre research; the "run it rather than serve it" distinction is the one thing that genuinely separates this from Papers Please and its descendants)*

**Measurement note:** `attributionProps()` in `public/index.html` reads **only**
`utm_source` — it sets `source: 'utm:<value>'`, falling back to the referrer
hostname, then `unknown`. Any A/B test must therefore vary something the site
actually records, or carry its own instrumentation. Do not assume `utm_content`
or `utm_campaign` reach the Download event.
