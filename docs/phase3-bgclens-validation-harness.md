# Phase 3 — Validation Harness (BGCLens)

**Status:** Draft for review · **Consumes:** Phase 2 runnable candidates · **Feeds:** curation gate, Phase 4 confidence measure · **Next gate:** catalog-reviewer ownership, sandbox choice

---

## 1. Goal of Phase 3

Automate the step "build tests that confirm a replicated method aligns with the source paper's principles." Phase 3 turns a Phase 2 catalog candidate into an executable **test package**, runs it in a sandbox, and produces the evidence the human curation gate uses to promote (or reject) the method into the deterministic catalog.

---

## 2. Role in the system

Phase 3 sits on the **guidance side** but is the bridge to validity: it generates the evidence that lets a human safely move a method across the firewall. Its output is the input to the Phase 4 confidence measure ("how aligned is this implementation with the study's principles").

**Firewall rules (non-negotiable):**
- The LLM writes tests but **never grades itself** — a deterministic runner executes them.
- Every generated test carries the **paper passage it encodes** as provenance.
- Test *generation* is guidance; only **human-approved test results** become evidence.

---

## 3. Test taxonomy

| Test type | Encodes | Determinism |
|---|---|---|
| Principle tests | The paper's claimed behavior ("input X → output has property Y") | Property-based (invariants) |
| Contract tests | Compatibility with BGCFlow's real output schema | Fully deterministic IO checks |
| Divergence tests | Behavior when your DB/organism differs from the paper's — still valid, or flags the mismatch | Deterministic + guarded |
| Golden tests | Reproduction of a paper-supplied example (data + expected output) | Regression anchor |

For discovery-track (non-executable) methods, Phase 3 emits a **manual validation checklist** instead of runnable tests.

---

## 4. Generation-to-gate flow

```
Phase 2 runnable candidate (+ provenance)
        │
        ▼
[1] LLM test generator  → test specs + code, each tagged with paper passage
        │
        ▼
[2] Human review of generated tests (verify assertion matches the claim)
        │
        ▼
[3] Sandbox runner (deterministic)  → pass/fail per test
        │
        ▼
[4] Confidence measure (weighted pass rate)  → Phase 4
        │
        ▼
[5] Human curation gate  → promote / reject into catalog
```

Step [2] is what stops a hallucinated principle from silently becoming a gating test.

---

## 5. Architecture / development guidance

### 5.1 Component recommendations

- **Test runner** — pytest as the harness. Use Hypothesis for principle tests, since scientific invariants map naturally to property-based assertions.
- **Pipeline-contract tests** — BGCFlow is Snakemake-based, and Snakemake ships native unit-test scaffolding (`--generate-unit-tests`). Build contract/pipeline tests on that scaffolding rather than reinventing; reserve pytest+Hypothesis for method-level principle tests.
- **Sandbox** — run each method in an isolated, pinned environment (containerized or per-method conda env). No network by default; declared inputs mounted read-only. This keeps an untrusted third-party method from touching anything it shouldn't.
- **Provenance manifest** — a machine-readable map of `test → paper passage → SQ served`. This is the reviewer's checklist and the auditor's trail.
- **Confidence measure** — aggregate weighted pass/fail into a single banded score (not a raw percentage presented as truth) and hand it to Phase 4. Divergence-test failures should be surfaced explicitly, not averaged away.
- **LLM role — bounded** — generates test specs/code and narrates results in plain language. It never executes, grades, or promotes.

### 5.2 Build order (MVP-first)

- **Phase 3.0 (MVP):** contract + principle tests for a **single hand-picked method**, end to end through the sandbox and gate — prove the generate → review → run → gate loop works before scaling.
- **Phase 3.1:** add divergence + golden tests; wire the confidence measure into Phase 4.
- **Phase 3.2:** widen to the Phase 2 candidate stream; add the manual-checklist path for discovery-track methods.

---

## 6. Honest risks

- **Hallucinated principles.** An LLM can encode a confident but wrong assertion as a test. Mitigation: mandatory provenance + human review before any test can gate a method.
- **Over-trusting the confidence number.** It's a banded prior on alignment, not proof of correctness — present it as such, and never let it silently overwrite a validity field.
- **Sandbox escape / dependency rot.** Pin environments, isolate the network, mount inputs read-only.

---

## 7. Open items / next gate

- [ ] Resolve **catalog-reviewer ownership** — the human at steps [2] and [5] (shared with Phase 2)
- [ ] Choose the sandbox mechanism (container vs per-method conda env)
- [ ] Define the confidence-measure weighting (esp. how hard divergence failures count)
- [ ] Confirm the provenance-manifest format shared with Phase 2
