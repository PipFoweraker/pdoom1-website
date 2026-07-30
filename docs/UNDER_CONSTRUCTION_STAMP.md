# The under-construction stamp

A diagonal rubber-stamp impression — the thing a clerk slams on a form.
Mid-2000s office paperwork, not a Web 1.0 "under construction" GIF.

Source: `public/css/stamp.css`. First adopter: `public/frontier-labs/index.html`.

## What it is for

Marking a block of the site whose data is **not yet what it will be**, without
either (a) hiding the block or (b) letting a reader mistake a placeholder for a
measurement. It is the visual half of the same discipline `/state-of-doom/`
applies in text: render *"awaiting &lt;source&gt;"*, never a guessed value.

It is a **label, not a censor bar**. If a stamp is covering something the reader
needs, the stamp is wrong.

## Adopting it on another page

Two lines. One `<link>`, one block of markup.

```html
<!-- in <head>, AFTER the page's own inline <style> is not required —
     every class is namespaced .stamp*, so order does not matter -->
<link rel="stylesheet" href="/css/stamp.css">
```

```html
<div class="stamp-block" role="note">
  <p><span class="stamp stamp--awaiting"><span class="stamp-sr">Status stamp: </span><span class="stamp-text">Awaiting data</span></span></p>
  <div class="stamp-body">
    <p>What this block will show, what it is waiting on, and who is doing it.</p>
  </div>
  <p class="stamp-docket">
    Form PD-1/FL &middot; Ref <a href="https://github.com/PipFoweraker/pdoom-data/issues/37">pdoom-data#37</a> &middot; Clerk: unassigned
  </p>
</div>
```

That is the whole component. No JS, no images, no external fonts, no network
requests — the site's CSP posture stays intact.

### Required bits, and why each one

| Bit | Why it is not optional |
| --- | --- |
| `role="note"` on the block | tells assistive tech the panel is an aside about the content, not the content |
| `<span class="stamp-sr">Status stamp: </span>` | a sighted reader knows it is a stamp from the border and the angle. Nobody else does. |
| Sentence case in the HTML (`Awaiting data`) | CSS does the shouting via `text-transform`. Several screen readers spell ALL-CAPS source text out letter by letter. |
| `<span class="stamp-text">` wrapper | lifts the letters above the ink-void overlay (`z-index`) |
| A real reference in `.stamp-docket` | a made-up docket number is exactly the authoritative-sounding lie the stamp exists to prevent |

## Choosing the words

**Pick what is true of that specific block.** A stamp saying something false is
worse than no stamp — it launders a guess into an official-looking record.

| Class | Words that fit | True when |
| --- | --- | --- |
| `.stamp--awaiting` | Awaiting data · Awaiting source | the data does not exist yet anywhere |
| `.stamp--provisional` | Provisional · Subject to revision | data exists but is hand-entered / interim |
| `.stamp--review` | Under review · Definition under review | the *boundary* is being argued, not the values |
| `.stamp--incomplete` | File incomplete · Known incomplete | the set is real but knowingly missing members |
| `.stamp--restricted` | Not a measurement · Illustrative only | the block is a model artefact, not an observation |

Variants differ only in `--stamp-ink` and slam angle, so adding one is a
two-property rule.

## Sizes and placement

- `.stamp--sm` / `.stamp--lg` — scale.
- Default placement is **in normal flow**. Use this.
- `.stamp--overlay` — corner impression, `pointer-events:none`. Only for panels
  whose content is *itself* pending. The panel must be `position:relative` and
  must reserve `padding-top` for it. On ≤480px it drops back into flow
  automatically, because a rotated absolute box on a narrow screen will overlap
  something.

## How the effect is built

Four cheap layers, no images:

1. `transform: rotate(-7deg)` — the slam angle. Small enough to read as
   deliberate, large enough not to look like a CSS bug. Variants vary it so two
   stamps on one page are not obviously the same object.
2. `::before` — a duplicate border box offset ~1–3px at `opacity:.28`. This is
   the misregistered second impression of a tired stamp, and it is what stops
   the element reading as a plain badge.
3. `text-shadow: .5px .5px 0 currentColor` — the same trick on the letterforms.
4. `::after` — an angled `repeating-linear-gradient` in the **page background
   colour** at `opacity:.18`, with uneven stop widths (1/6/7/19/21/34px). Reads
   as streaky voids where the ink did not take.

Plus condensed all-caps letterspacing (`font-weight:800`, `letter-spacing:.18em`,
`font-stretch:condensed` as a no-op-if-unavailable enhancement) and a double
rule (`border` + `inset box-shadow`).

### Why layer 4 is an overlay and not a mask

A CSS `mask-image` would give more convincing ink weathering. It is rejected
deliberately: if masking fails or composites unexpectedly, the stamp renders
**invisible**. That is the one failure mode a trust label cannot have — the
reader would then see pending data with nothing marking it as pending. An
overlay's worst case is that it renders as nothing, and you are left with a
clean stamp. Degrade toward *more* honest, not less.

## Degradation checklist

- **No CSS at all** → `Status stamp: Awaiting data` as plain text ahead of the
  explanation. Meaning survives intact.
- **No JS** → irrelevant; the component uses none.
- **`prefers-reduced-motion`** → nothing here moves in the first place. The
  media block only neutralises transitions a host page might inherit onto it.
- **`forced-colors: active`** → border and text switch to `CanvasText`, ink-void
  overlay is dropped (it would otherwise punch holes in a system-colour fill).
- **≤480px** → `white-space` unlocks so long wording wraps instead of
  overflowing; overlay placement falls back to flow.

## Rules

1. **Never in `public/css/site.css`.** That file loads nearly everywhere and has
   whited out the site once already (CLAUDE.md, "Cascade gotcha"). `stamp.css`
   is opt-in per page.
2. **No emoji.** The stamp is typography. A pictograph would turn a
   bureaucratic instrument into a sticker.
3. **Remove the stamp when the data lands.** A stamp that outlives its condition
   trains readers to ignore all of them — the same reasoning as the ADR
   scrubber's deliberately narrow match in `sync-design-notes.py`.
