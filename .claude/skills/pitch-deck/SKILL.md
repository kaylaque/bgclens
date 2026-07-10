---
name: pitch-deck
description: Generate a Marp (markdown) slide deck to present a project, research result, tool, or product idea. Use whenever the user wants to turn a project description, PRD, paper, or feature story into slides — including phrases like "make a deck", "pitch deck", "slides for", "present this", "to-deck", "turn this PRD into slides", "lab meeting slides", "conference talk", or when they paste a project/research summary and ask how to present it. Especially reach for this for bioinformatics or scientific talks (methods, results, figures, equations). Produces a Marp `.md` deck plus export commands; it does not design non-Marp slides or write the underlying research.
---

# Pitch Deck Generator

Turn a project story, PRD, or research summary into a **Marp** slide deck — markdown that lives in the repo, diffs cleanly in version control, and exports to HTML, PDF, or PPTX with one command.

## When to use

Use this skill when the user:

- wants slides for a project, tool, research result, or product idea
- asks to "make a deck", "pitch deck", "slides for X", or invokes `/to-deck`
- pastes a `tasks/prd-*.md`, a project README, a paper abstract, or a results summary and asks how to present it
- needs a lab-meeting, conference, thesis-committee, or funding presentation

**Important:** Do NOT invent results or write the underlying research. Present what the user gives you. If a claimed number or figure isn't provided, mark it as a placeholder (see Step 3) rather than fabricating it.

## The Job

1. Receive a project story, PRD, or research summary from the user
2. Ask 3-4 essential clarifying questions (with lettered options)
3. Pick the matching deck preset and generate a Marp deck
4. Save to `decks/[deck-name].md` (kebab-case)
5. Print the export commands so the user can render HTML / PDF / PPTX

## Step 1: Clarifying Questions

Ask only what you can't infer from the input. Focus on audience, purpose, length, and depth — these drive every downstream choice. Format with lettered options so the user can reply "1A, 2C, 3B".

```
1. Who is the audience?
   A. Technical peers (lab meeting / research group)
   B. Broad scientific / conference audience
   C. Funders / reviewers / non-specialists
   D. Internal stakeholders (product/eng)

2. What is the goal of the deck?
   A. Share research progress and results
   B. Pitch a tool/pipeline you built
   C. Propose new work / request funding or resources
   D. Teach a method or concept

3. How long should it be?
   A. Lightning (5-7 slides, ~5 min)
   B. Standard talk (10-15 slides, ~15 min)
   C. Full seminar (20-30 slides, ~40 min)

4. How much methods / math detail?
   A. Keep it high-level (intuition, minimal equations)
   B. Balanced (key equations + intuition)
   C. Deep (full derivations, code, parameters)
```

Remember to indent the options. If the user already answered any of these in their prompt (e.g. "a 10-min lab meeting talk"), skip that question.

## Step 2: Choose a preset

Map goal (Q2) to a slide arc. These are starting skeletons — adapt slide count to the length answer (Q3) by expanding or merging sections.

### Preset A — Research talk (goal = share results / propose work)
1. **Title** — project, presenter, affiliation, date
2. **Motivation** — why this matters (biological / real-world stakes)
3. **Background** — the minimum the audience needs (define key terms)
4. **The gap / question** — what's unknown, stated as a crisp question
5. **Data** — dataset, scale, provenance
6. **Approach / methods** — the method, with a key equation or diagram
7. **Results** — one claim per slide, each anchored to a figure
8. **Interpretation** — what the results mean, honestly (limits too)
9. **Next steps** — what's next
10. **Summary + acknowledgments** — 3 takeaways, then thanks/refs

### Preset B — Tool / pipeline pitch (goal = pitch what you built)
1. **Title**
2. **Problem** — the pain, concretely
3. **Solution** — what the tool does in one sentence
4. **How it works** — architecture / pipeline diagram
5. **Demo / usage** — commands or screenshots
6. **Results / validation** — evidence it works
7. **Roadmap** — what's next
8. **Ask** — call to action (try it, contribute, adopt)

### Preset C — Teaching a method (goal = teach)
1. **Title** → 2. **Why care** → 3. **Intuition first** → 4. **Formal statement** → 5. **Worked example** → 6. **When it breaks / assumptions** → 7. **Summary**

## Step 3: Generate the Marp deck

Read `references/marp-cheatsheet.md` before writing slides — it has the exact syntax for title slides, split image layouts, two columns, speaker notes, KaTeX math, and code blocks, plus the export commands. Load `assets/theme.css` as the deck theme so decks stay branded and consistent.

Every deck starts with this frontmatter (adjust title/footer):

```markdown
---
marp: true
theme: project
paginate: true
header: ''
footer: 'Presenter · Project · 2026'
math: katex
---
```

Then slides separated by `---` on its own line.

### Rules that keep decks good

- **One idea per slide.** If a slide has two claims, split it. Titles should assert the takeaway ("CAZyme count is predicted by 12 gene families"), not label the topic ("Results").
- **Figure-forward for results.** Each results slide is a figure + a one-line takeaway, not a paragraph. Use the `![bg right:40%](figure.png)` split layout so the image and its interpretation sit side by side. Reference figures by the path the user gives; if none is given, insert `![w:600](FIGURE_PLACEHOLDER_describe-what-goes-here.png)` and list it in Open Items.
- **Speaker notes carry the detail.** Slides stay sparse; put the spoken narrative in HTML-comment speaker notes (`<!-- ... -->`) so the user has a script without cluttering the slide.
- **Math belongs on the method slide.** Use KaTeX (`$...$` inline, `$$...$$` display) for equations rather than screenshots — they stay editable and crisp. E.g. a group-lasso penalty renders natively.
- **Placeholders, never fabrication.** Any number, quote, or figure the user didn't provide becomes an ALL-CAPS placeholder and gets listed under Open Items on the last slide. Do not invent p-values, sample sizes, or accuracy figures.
- **Define jargon on first use** for audiences B and C (Q1). A technical peer audience (A) needs less hand-holding.

## Output

- **Format:** Marp markdown (`.md`)
- **Location:** `decks/`
- **Filename:** `[deck-name].md` (kebab-case, e.g. `bvelezensis-pangenome-lab-meeting.md`)

After saving, print the export commands (from the cheatsheet) so the user can render the deck:

```bash
npx @marp-team/marp-cli@latest decks/[deck-name].md -o [deck-name].html   # self-contained HTML
npx @marp-team/marp-cli@latest decks/[deck-name].md --pdf                  # PDF
npx @marp-team/marp-cli@latest decks/[deck-name].md --pptx                 # editable PowerPoint
```

If a PRD under `tasks/prd-*.md` was the input, note that the deck and the PRD are two views of the same story — keep the deck's problem/solution framing consistent with the PRD's Introduction and Goals.

## Example (excerpt — Preset A, audience A, deep methods)

```markdown
---
marp: true
theme: project
paginate: true
footer: 'Z. Fathoni · B. velezensis pangenome · 2026'
math: katex
---

<!-- _class: lead -->
# Predicting CAZyme repertoires from the *B. velezensis* pangenome

Group-LASSO selection over 546 genomes

Zain Fathoni · Lab Meeting · 2026

---

## Why CAZymes, why *B. velezensis*

- CAZymes drive cell-wall degradation and biocontrol activity
- We want to know **which gene families predict CAZyme count** — a genome-mining goal
- 546 genomes give us the statistical power to ask this cleanly

<!-- Open with the biocontrol angle — that's what the room cares about. Land the genome-mining framing before any stats. -->

---

## The question

> Across the pangenome's presence/absence matrix, **which few gene families carry predictive signal** for CAZyme count and BGC presence?

Most columns are assumed to carry none — a sparsity assumption we'll lean on.

---

## Method: group LASSO

Blocks of correlated gene families are selected or zeroed together:

$$
\hat{\beta} = \arg\min_{\beta}\; \tfrac{1}{2}\lVert y - X\beta \rVert_2^2 \;+\; \lambda \sum_{g=1}^{G} \sqrt{p_g}\,\lVert \beta_g \rVert_2
$$

- The group norm zeros **entire families** below a threshold (block soft-thresholding)
- $\lambda$ tuned by cross-validation; selection stabilized by stability selection

<!-- Don't derive soft-thresholding live unless asked — point to the appendix slide. -->

---

## Result: a sparse, stable gene-family signature

![bg right:42%](FIGURE_PLACEHOLDER_selection-path-or-stability-plot.png)

- SELECTED_N families retained at the CV-optimal $\lambda$
- Signature is stable across STABILITY_SELECTION_FRACTION of subsamples

<!-- The takeaway is *sparse and stable*, not the exact count — but fill the real numbers before presenting. -->

---

<!-- _class: lead -->
## Takeaways

1. A handful of gene families predict CAZyme repertoire
2. Group LASSO + stability selection gives a reproducible signature
3. Next: validate the signature against held-out genomes

**Open items:** SELECTED_N, STABILITY_SELECTION_FRACTION, selection-path figure
```

## Checklist

Before saving the deck:

- [ ] Asked clarifying questions with lettered options (skipped any already answered)
- [ ] Chose the preset matching the stated goal, sized to the length answer
- [ ] One idea per slide; titles assert takeaways, not topics
- [ ] Results slides are figure-forward with a one-line takeaway
- [ ] Equations use KaTeX, not images
- [ ] Speaker notes carry the spoken detail
- [ ] Every un-provided number/figure is an ALL-CAPS placeholder listed in Open Items — nothing fabricated
- [ ] Saved to `decks/[deck-name].md` and printed the export commands
