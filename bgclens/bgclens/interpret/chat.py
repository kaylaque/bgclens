"""Multi-turn retrieval-augmented chat for BGCLens.

LLM role: answer biology + methodology questions grounded in the loaded project
data.  Fabrication of specific accessions / statistics is still prohibited, but
the assistant is now free to draw on general BGC biology knowledge.
"""
from __future__ import annotations
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bgclens.model import Mention, Turn
    from bgclens.core.provenance import RunRecord
    from bgclens.model import Project

logger = logging.getLogger(__name__)

_MAX_HISTORY  = 8     # turns kept in context window
_MAX_CTX_CHARS = 6000 # cap on assembled retrieval context

# ── Method knowledge base ────────────────────────────────────────────────────
_METHOD_KB: dict[str, str] = {
    "alpha_diversity": (
        "Alpha diversity measures within-sample species richness and evenness. "
        "In BGC analysis, it quantifies how many distinct BGC families are present "
        "per genome, using Shannon entropy and Simpson's index. High alpha diversity "
        "indicates a genome encodes a wide variety of secondary metabolite pathways."
    ),
    "fisher_enrichment": (
        "Fisher's exact test (BGC class enrichment) tests whether a specific BGC "
        "class (e.g. NRPS, PKS-I, terpene) is statistically overrepresented in one "
        "group of genomes vs another. Returns odds ratio and p-value per BGC class. "
        "Useful for identifying which metabolite families distinguish two ecological niches."
    ),
    "hierarchical_clustering": (
        "Hierarchical clustering groups genomes by BGC profile similarity using "
        "Ward or complete linkage. The dendrogram reveals chemotype groups — sets "
        "of genomes with similar secondary metabolite repertoires. Often used to "
        "identify which strains are closest relatives for combinatorial BGC mining."
    ),
    "pcoa": (
        "PCoA (Principal Coordinates Analysis) projects pairwise Bray-Curtis or "
        "Jaccard distances into 2D/3D space, visualising how similar genomes are "
        "in their overall BGC composition. Distinct clouds of points = distinct "
        "chemotypes. Complements hierarchical clustering."
    ),
    "pca": (
        "PCA (Principal Component Analysis) projects high-dimensional BGC presence/"
        "absence or count vectors into low-dimensional space based on variance. "
        "Useful for identifying which BGC families drive the most variation across "
        "the genome set."
    ),
    "permanova": (
        "PERMANOVA (Permutational MANOVA) statistically tests whether predefined "
        "groups of genomes differ in BGC composition. A significant result (p < 0.05) "
        "means the groups have genuinely different secondary metabolite profiles, "
        "not just random variation. R² indicates how much of the total variation "
        "is explained by the grouping."
    ),
    "louvain_community": (
        "Louvain community detection runs on the GCF similarity network, partitioning "
        "BGC families into modules that share structural similarity. Each community "
        "often corresponds to a biosynthetic enzyme superfamily. High modularity "
        "indicates well-separated BGC family clusters."
    ),
    "manufacturability": (
        "Manufacturability analysis scores BGC candidates on feasibility of "
        "heterologous expression in a chassis organism (E. coli, Streptomyces, "
        "yeast). Scores cluster size, known toxic intermediates, codon adaptation "
        "index, and presence of self-resistance genes. Returns a tractability score "
        "and chassis hint."
    ),
}

_SYSTEM_PROMPT = """\
You are BGCLens Assistant — a scientific expert embedded in a bioinformatics tool \
that analyses biosynthetic gene clusters (BGCs) from BGCFlow projects.

You help bench biologists and computational researchers with:
• Interpretation of BGC analysis results (diversity, enrichment, clustering, PCoA, PERMANOVA, community detection, manufacturability)
• BGC biology: polyketides (PKS), non-ribosomal peptides (NRPS), terpenes, siderophores, RiPPs, hybrid clusters
• BGCFlow pipeline methodology and outputs (antiSMASH, BiG-SCAPE, GCF networks)
• Bioinformatics methods and their biological meaning
• Wet-lab next steps: validation strategies, heterologous expression, bioassays

RULES:
1. When PROJECT CONTEXT below contains relevant data, cite it explicitly.
2. For biology / methodology questions not in the context, answer from scientific knowledge — \
   you are a domain expert, not a pure retrieval system.
3. NEVER fabricate specific numbers, statistics, UniProt IDs, PMIDs, accession numbers, \
   or sequences that are not in the provided context.
4. Answers should be focused (3-7 sentences). Methodological questions can be slightly longer.
5. When a @mention scopes to a cluster or analysis section, prioritise that context first.
6. You may suggest biological interpretations and experimental next steps.
7. Do NOT write validity scores or confidence bands — those come from the deterministic engine.
8. Answer ANY question that could relate to: biology, chemistry, genomics, bioinformatics, ecology, \
   experimental design, scientific writing, data analysis — even if not explicitly stated. \
   The user is a bench scientist; be helpful rather than gatekeeping relevance.
"""


def _assemble_context(
    project: "Project",
    records: list,
    mentions: list["Mention"],
) -> tuple[str, dict]:
    """Build retrieval context string.  Returns (context_text, key_numbers_for_guard)."""
    parts: list[str] = []
    key_numbers: dict[str, float] = {}

    # ── Project manifest ─────────────────────────────────────────────────────
    m = project.manifest
    parts.append(f"=== PROJECT: {m.project_name} ===")
    parts.append(f"Pipelines run: {', '.join(sorted(m.available_pipelines)) or 'none'}")
    if project.gcf_presence_absence:
        pa = project.gcf_presence_absence
        gcf_n = len(pa.rows)
        genome_n = len(pa.cols)
        parts.append(f"GCF matrix: {gcf_n} GCFs × {genome_n} genomes")
        key_numbers["gcf_count"] = float(gcf_n)
        key_numbers["genome_count"] = float(genome_n)

    if project.bgc_counts:
        bc = project.bgc_counts
        parts.append(
            f"BGC counts: {len(bc.genome_ids)} genomes × {len(bc.features)} BGC classes"
        )

    if project.taxonomy:
        tx = project.taxonomy
        parts.append(f"Taxonomy: {len(tx.genome_ids)} annotated genomes")

    # ── Mention-scoped context ────────────────────────────────────────────────
    for mention in mentions:
        oid  = mention.object_id
        otype = mention.object_type

        if otype == "cluster":
            parts.append(f"\n=== @{oid} (CLUSTER) ===")
            if project.gcf_presence_absence:
                pa = project.gcf_presence_absence
                if oid in pa.rows:
                    idx = pa.rows.index(oid)
                    row_vals = pa.values[idx]
                    n_present = sum(1 for v in row_vals if v > 0)
                    parts.append(f"Present in {n_present}/{len(pa.cols)} genomes")
                    key_numbers[f"{oid}_n_present"] = float(n_present)

            # Taxonomy for genomes carrying this cluster
            if project.taxonomy and project.gcf_presence_absence:
                pa = project.gcf_presence_absence
                if oid in pa.rows:
                    idx = pa.rows.index(oid)
                    carrying = [
                        pa.cols[j] for j, v in enumerate(pa.values[idx]) if v > 0
                    ][:5]
                    organisms = []
                    for gid in carrying:
                        org = getattr(project.taxonomy, "get_organism", None)
                        if callable(org):
                            organisms.append(org(gid) or gid)
                        else:
                            organisms.append(gid)
                    if organisms:
                        parts.append(f"Carrying genomes (up to 5): {', '.join(organisms)}")

            # Most recent run result for this cluster
            for rec in reversed(records):
                rs = getattr(rec, "result_summary", rec if isinstance(rec, dict) else {})
                run_spec = getattr(rec, "run_spec", {}) or {}
                if isinstance(run_spec, dict) and run_spec.get("cluster_id") == oid:
                    interp = rs.get("interpretation", "")
                    cb = rs.get("confidence_band", rs.get("_confidence_band", ""))
                    if interp:
                        parts.append(f"Latest result: {interp[:400]}")
                    if cb:
                        parts.append(f"Confidence band: {cb}")
                    break

        elif otype == "method":
            kb_desc = _METHOD_KB.get(oid, "")
            parts.append(f"\n=== @{oid} (METHOD) ===")
            if kb_desc:
                parts.append(kb_desc)
            # Surface the most recent run result for this method
            for rec in reversed(records):
                rs = getattr(rec, "result_summary", rec if isinstance(rec, dict) else {})
                run_spec = getattr(rec, "run_spec", {}) or {}
                method = run_spec.get("method_id") if isinstance(run_spec, dict) else None
                if method == oid:
                    interp = rs.get("interpretation", "")
                    if interp:
                        parts.append(f"Latest result: {interp[:500]}")
                    # Include key scalar metrics
                    scalars = {
                        k: v for k, v in rs.items()
                        if not k.startswith("_")
                        and k not in ("svg", "interpretation", "method")
                        and isinstance(v, (int, float, str))
                        and not isinstance(v, bool)
                        and len(str(v)) <= 30
                    }
                    if scalars:
                        parts.append("Metrics: " + ", ".join(
                            f"{k}={v}" for k, v in list(scalars.items())[:8]
                        ))
                        for k, v in scalars.items():
                            try:
                                key_numbers[f"{oid}_{k}"] = float(v)
                            except (ValueError, TypeError):
                                pass
                    break

        elif otype == "report_section":
            # run_id embedded in id: "section_<8chars>"
            run_id_prefix = oid.replace("section_", "")
            for rec in reversed(records):
                run_spec = getattr(rec, "run_spec", {}) or {}
                rs = getattr(rec, "result_summary", {}) or {}
                mid = run_spec.get("method_id", "")
                if mid:
                    parts.append(f"\n=== Report section: {mid} ===")
                    interp = rs.get("interpretation", "")
                    if interp:
                        parts.append(interp[:600])
                    break

    # ── Recent run records (last 4, not already mentioned) ───────────────────
    mentioned_ids = {m.object_id for m in mentions}
    parts.append("\n=== RECENT ANALYSES ===")
    seen = 0
    for rec in reversed(records):
        if seen >= 4:
            break
        rs = getattr(rec, "result_summary", {}) or {}
        run_spec = getattr(rec, "run_spec", {}) or {}
        mid = run_spec.get("method_id", "")
        cid = run_spec.get("cluster_id", "")
        if mid in mentioned_ids:
            continue
        interp = rs.get("interpretation", "")
        cb = rs.get("confidence_band", "")
        line = f"• {mid}"
        if cid:
            line += f" @ {cid}"
        if cb:
            line += f" [{cb}]"
        if interp:
            line += f": {interp[:200]}"
        parts.append(line)
        seen += 1

    context = "\n".join(parts)
    if len(context) > _MAX_CTX_CHARS:
        context = context[:_MAX_CTX_CHARS] + "\n[context truncated]"
    return context, key_numbers


def chat(
    project: "Project",
    records: list,
    history: list["Turn"],
    message: str,
    mentions: list["Mention"] | None = None,
) -> "Turn":
    """Single chat turn.  Always returns a Turn, never raises."""
    from bgclens.model import Turn

    mentions = mentions or []
    fallback = (
        "I couldn't retrieve a response right now. "
        "Try asking about a specific cluster (@cluster_id), method, or analysis result."
    )

    try:
        context_text, key_numbers = _assemble_context(project, records, mentions)

        try:
            from bgclens.core.config import get_settings
            settings = get_settings()
            llm_cfg = settings.llm

            if not llm_cfg.enabled or not llm_cfg.api_key:
                return Turn(
                    role="assistant",
                    content=f"[LLM not configured]\n\nContext:\n{context_text[:600]}",
                    mentions=[m.object_id for m in mentions],
                )

            from openai import OpenAI
            client = OpenAI(base_url=llm_cfg.base_url, api_key=llm_cfg.api_key)

            messages = [
                {"role": "system",
                 "content": _SYSTEM_PROMPT + f"\n\nPROJECT CONTEXT:\n{context_text}"},
            ]
            for turn in history[-_MAX_HISTORY:]:
                messages.append({"role": turn.role, "content": turn.content})
            messages.append({"role": "user", "content": message})

            response = client.chat.completions.create(
                model=llm_cfg.model,
                messages=messages,
                temperature=0.4,
                max_tokens=1200,
            )
            msg = response.choices[0].message
            content = (msg.content or "").strip()
            # Reasoning models (DeepSeek R-series) put final answer in content,
            # but if max_tokens ran out during chain-of-thought content is empty.
            # Fall back to reasoning_content which has the full thought + answer.
            if not content:
                content = (getattr(msg, "reasoning_content", None) or "").strip()
                # Extract the final paragraph/answer after "**Answer:**" or last block
                if content:
                    for marker in ("**Answer:**", "**Final Answer:**", "In summary,", "Therefore,"):
                        idx = content.rfind(marker)
                        if idx != -1:
                            content = content[idx:].strip()
                            break
                    else:
                        # Take the last 800 chars of reasoning as the answer
                        content = content[-800:].strip()
            reply = content or fallback

        except Exception as exc:
            logger.debug("chat LLM call failed: %s", exc)
            reply = fallback

        return Turn(
            role="assistant",
            content=reply,
            mentions=[m.object_id for m in mentions],
        )

    except Exception as exc:
        logger.warning("chat() outer error: %s", exc)
        return Turn(role="assistant", content=fallback)
