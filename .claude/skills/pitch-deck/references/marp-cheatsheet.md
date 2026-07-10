# Marp cheatsheet

Everything needed to write and export a Marp deck. Load this before generating slides.

## Deck frontmatter (top of the file, once)

```markdown
---
marp: true
theme: project        # custom theme from assets/theme.css; use 'default'/'gaia'/'uncover' if not registered
paginate: true        # page numbers
header: ''            # repeated top text (leave empty to omit)
footer: 'Presenter · Project · 2026'
math: katex           # enable KaTeX math ($...$ and $$...$$)
---
```

## Slides and per-slide directives

- Slides are separated by a line containing only `---`.
- Underscore-prefixed directives apply to the **current slide only**:

```markdown
<!-- _class: lead -->        # centered title layout (from theme)
<!-- _paginate: false -->    # hide page number on this slide
<!-- _backgroundColor: #0b132b -->
<!-- _color: white -->
```

## Title / section slide

```markdown
<!-- _class: lead -->
# Big Title

Subtitle line

Presenter · Venue · Date
```

## Images and sizing

```markdown
![w:600](figure.png)          # width 600px
![h:300](figure.png)          # height 300px
![w:600 blur:4px](figure.png) # filters are supported
```

### Background images and split layouts (best for results slides)

```markdown
![bg](fullbleed.png)                 # full-slide background
![bg right](figure.png)              # image fills right half, text on left
![bg right:40%](figure.png)          # image fills right 40%, text gets 60%
![bg left:35% fit](diagram.png)      # 'fit' scales to fit the region
```

Multiple `![bg]` on one slide tile automatically (side by side).

## Two columns (for comparisons)

Marp has no native columns; use a div + inline CSS, or add the rule to the theme.

```markdown
<div class="columns">
<div>

**Before**
- point
- point

</div>
<div>

**After**
- point
- point

</div>
</div>
```

The theme in `assets/theme.css` already defines `.columns` as a 2-up CSS grid.

## Speaker notes

Any HTML comment on a slide becomes a speaker note (visible in presenter view and PPTX notes, hidden on the slide):

```markdown
## Slide title

- sparse bullet

<!-- This is the spoken narrative. Put the detail, the caveats, the "if asked" here. -->
```

## Math (KaTeX)

Requires `math: katex` in frontmatter.

```markdown
Inline: the estimator $\hat{\beta}$ minimizes the loss.

Display:
$$
\hat{\beta} = \arg\min_{\beta}\; \tfrac{1}{2}\lVert y - X\beta \rVert_2^2 + \lambda \sum_{g} \sqrt{p_g}\,\lVert \beta_g \rVert_2
$$
```

## Code blocks (for pipeline / usage slides)

Fenced blocks get syntax highlighting automatically:

````markdown
```groovy
process ANALYZE {
    input: path sample
    output: path "result.txt"
    script: "python analyze.py ${sample} > result.txt"
}
```
````

## Fitting content

If a slide overflows, prefer splitting it. If you must shrink, scope a font size to one slide:

```markdown
<!-- _class: lead -->
<style scoped>
section { font-size: 22px; }
</style>
```

## Exporting

Marp CLI needs Node.js. `npx` fetches it on demand (no install):

```bash
# Self-contained HTML (opens in any browser, good for sharing)
npx @marp-team/marp-cli@latest decks/NAME.md -o NAME.html

# PDF (needs a Chromium; marp-cli downloads one, or set CHROME_PATH)
npx @marp-team/marp-cli@latest decks/NAME.md --pdf

# Editable PowerPoint (for non-technical stakeholders)
npx @marp-team/marp-cli@latest decks/NAME.md --pptx

# Live preview while editing
npx @marp-team/marp-cli@latest -w -s decks/
```

To register the custom theme explicitly on the CLI:

```bash
npx @marp-team/marp-cli@latest decks/NAME.md --theme assets/theme.css --pdf
```

### CI note

To rebuild decks in GitHub Actions, run the same `npx` command in a `node`-based job on push when `decks/**.md` changes, and upload the rendered PDF/HTML as an artifact.
