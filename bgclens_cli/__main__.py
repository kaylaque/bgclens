"""BGCLens CLI — thin Typer wrapper over the engine."""
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich import box

app = typer.Typer(name="bgclens", help="Post-processing & interpretation layer for BGCFlow.", add_completion=False)
console = Console()


@app.command("open")
def open_cmd(
    project: Path = typer.Argument(..., help="Path to a finished BGCFlow processed project directory."),
) -> None:
    """Ingest a BGCFlow project and show its capabilities manifest."""
    from bgclens.core.api import open_project
    try:
        proj = open_project(project)
    except ValueError as e:
        console.print(f"[red]✖ {e}[/red]")
        raise typer.Exit(1)

    m = proj.manifest
    console.print(f"\n[bold green]✔ Project loaded:[/] {m.project_name}")
    console.print(f"[bold]Pipelines:[/] {', '.join(sorted(m.available_pipelines)) or 'none'}")
    if m.duckdb_path:
        console.print(f"[bold]DuckDB:[/] {m.duckdb_path}")
    if proj.gcf_presence_absence:
        pa = proj.gcf_presence_absence
        console.print(f"[bold]GCF matrix:[/] {len(pa.rows)} GCFs × {len(pa.cols)} genomes")
    if proj.bgc_counts:
        console.print(f"[bold]BGC counts:[/] {len(proj.bgc_counts.genome_ids)} genomes × {len(proj.bgc_counts.features)} BGC classes")
    if proj.taxonomy:
        console.print(f"[bold]Taxonomy:[/] {len(proj.taxonomy.genome_ids)} genomes")


@app.command("recommend")
def recommend_cmd(
    project: Path = typer.Argument(..., help="BGCFlow project directory."),
    intent: str = typer.Option(..., "--intent", "-i", help="Analysis intent: enrichment|diversity|ordination|clustering|comparison|network_structure|sq1_inventory|sq2_novelty|sq3_prioritization|sq4_distribution|sq5_diversity|sq6_genomic_context|sq7_association"),
    topic: str = typer.Option("BGC analysis", "--topic", "-t", help="Research question (free text, used for literature ranking)."),
    objective: Optional[str] = typer.Option(None, "--objective", help='Ranking objective, e.g. "manufacturability" to rank by ease of heterologous production.'),
    no_literature: bool = typer.Option(False, "--no-literature", help="Skip literature ranking (faster)."),
) -> None:
    """Show method recommendations for the given intent and topic."""
    from bgclens.core.api import open_project, recommend
    from bgclens.core.intent import AnalysisRequest, Intent

    try:
        proj = open_project(project)
        request = AnalysisRequest(topic=topic, intent=Intent(intent), objective=objective)
        validation, recs = recommend(proj, request, use_literature=not no_literature)
    except (ValueError, KeyError) as e:
        console.print(f"[red]✖ {e}[/red]")
        raise typer.Exit(1)

    if not validation.valid:
        console.print(f"[yellow]⚠ Intent '{intent}' is not compatible with this project:[/]")
        console.print(f"  {validation.suggestion}")
        raise typer.Exit(1)

    table = Table(box=box.ROUNDED, title=f"Method recommendations for intent: {intent}")
    table.add_column("Method", style="bold")
    table.add_column("Cost")
    table.add_column("Literature")
    table.add_column("Recommended")
    table.add_column("Warnings")

    for r in recs:
        cost_style = {"Safe": "green", "Heavy": "yellow", "Likely-to-fail": "red"}.get(r.cost_class, "white")
        lit_style = {"strong": "blue", "moderate": "magenta"}.get(r.literature_support, "white")
        table.add_row(
            r.method_name,
            f"[{cost_style}]{r.cost_class}[/]",
            f"[{lit_style}]{r.literature_support}[/]",
            "✓" if r.is_recommended else "",
            str(len(r.assumption_warnings)) + " warning(s)" if r.assumption_warnings else "",
        )

    console.print(table)

    if objective and recs and recs[0].alternatives:
        manu = next((a for a in recs[0].alternatives if a.get("objective") == "manufacturability"), None)
        if manu is not None:
            from rich.panel import Panel

            blockers = manu.get("blockers") or manu.get("notes") or []
            lines = [
                f"[bold]Tractability:[/] {manu.get('tractability_score', 0):.3f}",
                f"[bold]Top class:[/] {manu.get('top_class') or '—'}",
                f"[bold]Chassis hint:[/] {manu.get('chassis_hint') or '—'}",
            ]
            if blockers:
                lines.append("[bold]Blockers:[/] " + "; ".join(str(b) for b in blockers))
            else:
                lines.append("[bold]Blockers:[/] none")
            console.print(Panel("\n".join(lines), title="Manufacturability ranking", border_style="cyan", box=box.ROUNDED))


@app.command("run")
def run_cmd(
    project: Path = typer.Argument(..., help="BGCFlow project directory."),
    method: str = typer.Option(..., "--method", "-m", help="Method ID to run (e.g. pcoa, fisher_enrichment)."),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Directory to write results (figures, provenance YAML)."),
    no_llm: bool = typer.Option(False, "--no-llm", help="Disable LLM interpretation phrasing."),
    params_json: Optional[str] = typer.Option(None, "--params", help="Method params as JSON string."),
) -> None:
    """Run a method and write figure + interpretation to output directory."""
    from bgclens.core.api import open_project, run
    from bgclens.viz import render
    from bgclens.interpret import interpret
    from bgclens.core.provenance import RunRecord, hash_project

    try:
        proj = open_project(project)
    except ValueError as e:
        console.print(f"[red]✖ {e}[/red]")
        raise typer.Exit(1)

    params = {}
    if params_json:
        try:
            params = json.loads(params_json)
        except json.JSONDecodeError as e:
            console.print(f"[red]✖ Invalid --params JSON: {e}[/red]")
            raise typer.Exit(1)

    console.print(f"[bold]Running:[/] {method} on {proj.manifest.project_name}…")
    try:
        result = run(proj, method, params)
    except Exception as e:
        console.print(f"[red]✖ Method failed: {e}[/red]")
        raise typer.Exit(1)

    warnings = result.get("_assumption_warnings", [])
    for w in warnings:
        console.print(f"[yellow]⚠ {w}[/yellow]")

    # Interpretation
    interp_output = interpret(result, assumption_warnings=warnings, use_llm=not no_llm)
    console.print("\n" + "─" * 60)
    console.print(Markdown(interp_output["final_text"]))
    if interp_output["llm_used"]:
        console.print("[dim]✨ Interpretation enhanced by LLM[/dim]")

    # Write outputs
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

        # Figures
        try:
            svg_bytes, png_bytes = render(result, proj.metadata)
            (output_dir / f"{method}_figure.svg").write_bytes(svg_bytes)
            (output_dir / f"{method}_figure.png").write_bytes(png_bytes)
            console.print(f"\n[green]✔ Figure saved:[/] {output_dir}/{method}_figure.svg")
        except Exception as e:
            console.print(f"[yellow]⚠ Figure rendering failed: {e}[/yellow]")

        # Interpretation
        (output_dir / f"{method}_interpretation.md").write_text(interp_output["final_text"])

        # Provenance
        record = RunRecord(
            project_path=str(project),
            inputs_hash=hash_project(project),
            run_spec={"method_id": method, "params": params},
            llm={"enabled": not no_llm, "used": interp_output["llm_used"]},
            result_summary={k: v for k, v in result.items()
                           if not k.startswith("_") and not isinstance(v, (list, dict))},
        )
        prov_path = record.save(output_dir)
        console.print(f"[green]✔ Provenance saved:[/] {prov_path}")
    else:
        console.print("\n[dim]Tip: use --output ./results/ to save figure + provenance.[/dim]")


@app.command("report")
def report_cmd(
    run_id: str = typer.Argument(..., help="Run ID from a prior 'bgclens run' invocation (run record file stem, e.g. bgclens_run_abcd1234)."),
    out_dir: Path = typer.Option(Path("."), "--out", "-o", help="Output directory for the .qmd (and HTML if quarto installed)."),
    record_file: Optional[Path] = typer.Option(None, "--file", "-f", help="Explicit path to a run record YAML (overrides run_id lookup)."),
) -> None:
    """Generate a Quarto .qmd report from a prior run record."""
    from bgclens.core.provenance import RunRecord
    from bgclens.report import render

    # Resolve the record path
    if record_file:
        record_path = record_file
    else:
        # Support bare run_id (stem) or full filename with .yaml
        stem = run_id if not run_id.endswith(".yaml") else run_id[:-5]
        record_path = Path(".bgclens_runs") / f"{stem}.yaml"
        if not record_path.exists():
            # Also check current dir
            record_path = Path(f"{stem}.yaml")

    if not record_path.exists():
        console.print(f"[red]✖ Run record not found: {record_path}[/]")
        console.print("[dim]Tip: use --file to specify the exact YAML path, or run 'bgclens run ... --output ./results/' first.[/dim]")
        raise typer.Exit(1)

    try:
        record = RunRecord.from_yaml(record_path.read_text())
    except Exception as e:
        console.print(f"[red]✖ Failed to load run record: {e}[/]")
        raise typer.Exit(1)

    report = render(record, out_dir)
    console.print(f"[green]✔ Report written:[/] {report.qmd_path}")
    if report.html_path:
        console.print(f"[green]✔ HTML rendered:[/] {report.html_path}")
    elif report.note:
        console.print(f"[yellow]ℹ {report.note}[/]")


@app.command("clusters")
def clusters_cmd(
    project: Path = typer.Argument(..., help="BGCFlow project directory."),
) -> None:
    """List cluster profiles with banded confidence indicators."""
    from bgclens.core.api import open_project
    from bgclens.core.clusters import list_clusters

    try:
        proj = open_project(project)
        clusters = list_clusters(proj)
    except ValueError as e:
        console.print(f"[red]✖ {e}[/red]")
        raise typer.Exit(1)

    if not clusters:
        console.print("[yellow]No clusters found in this project.[/yellow]")
        raise typer.Exit(0)

    band_style = {
        "high": "cyan",
        "medium": "yellow",
        "low": "white",
        "novel-candidate": "magenta bold",
    }

    table = Table(box=box.ROUNDED, title=f"Cluster profiles — {proj.manifest.project_name} ({len(clusters)} GCFs)")
    table.add_column("Cluster ID", style="bold")
    table.add_column("Type")
    table.add_column("Novelty band")
    table.add_column("Organism")

    for c in clusters:
        style = band_style.get(c.novelty_band, "white")
        table.add_row(
            c.cluster_id,
            c.cluster_type or "—",
            f"[{style}]{c.novelty_band}[/{style}]",
            c.organism or "—",
        )

    console.print(table)
    console.print("[dim]Novelty bands are banded priors, not predictions of correctness.[/dim]")


@app.command("run-batch")
def run_batch_cmd(
    project: Path = typer.Argument(..., help="BGCFlow project directory."),
    methods: str = typer.Option("alpha_diversity,fisher_exact", "--methods", "-m",
                                help="Comma-separated method IDs to run."),
    clusters: Optional[str] = typer.Option(None, "--clusters", "-c",
                                           help="Comma-separated cluster IDs, or 'auto' for smoke round (default 3)."),
    use_llm: bool = typer.Option(True, "--use-llm/--no-llm", help="Enable LLM interpretation."),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Directory for run records."),
) -> None:
    """Run multiple analyses across clusters in parallel (smoke round = 3 by default)."""
    import asyncio
    from bgclens.core.api import open_project, run_batch
    from bgclens.core.provenance import RunRecord, hash_project

    try:
        proj = open_project(project)
    except ValueError as e:
        console.print(f"[red]✖ {e}[/red]")
        raise typer.Exit(1)

    method_ids = [m.strip() for m in methods.split(",") if m.strip()]
    cluster_ids: Optional[list[str]] = None
    if clusters and clusters.lower() != "auto":
        cluster_ids = [c.strip() for c in clusters.split(",") if c.strip()]

    console.print(f"[bold]Running batch:[/] {', '.join(method_ids)} on {proj.manifest.project_name}")
    if cluster_ids:
        console.print(f"[bold]Clusters:[/] {', '.join(cluster_ids)}")
    else:
        console.print("[bold]Clusters:[/] smoke round (auto, up to 3)")

    try:
        results = asyncio.run(run_batch(
            proj,
            method_ids=method_ids,
            cluster_ids=cluster_ids,
            use_llm=use_llm,
        ))
    except Exception as e:
        console.print(f"[red]✖ Batch run failed: {e}[/red]")
        raise typer.Exit(1)

    run_ids: list[str] = []
    out = output_dir or Path(".bgclens_runs")
    out.mkdir(parents=True, exist_ok=True)

    for res in results:
        cluster_id = res.get("_cluster_id", "")
        method_id = res.get("method", res.get("_method_id", "unknown"))
        error = res.get("_error")

        if error:
            console.print(f"[red]✗[/red] {method_id}@{cluster_id}: {error}")
        else:
            console.print(f"[green]✔[/green] {method_id}@{cluster_id}")
            # Save run record
            try:
                record = RunRecord(
                    project_path=str(project),
                    inputs_hash=hash_project(project),
                    run_spec={"method_id": method_id, "cluster_id": cluster_id, "params": {}},
                    llm={"enabled": use_llm},
                    result_summary={k: v for k, v in res.items()
                                   if not k.startswith("_") and not isinstance(v, (list, dict))},
                )
                saved = record.save(out)
                run_ids.append(saved.stem)
            except Exception as save_err:
                console.print(f"[yellow]⚠ Could not save run record: {save_err}[/yellow]")

    console.print(f"\n[bold]Run IDs:[/] {' '.join(run_ids)}")
    console.print(f"[dim]Use 'bgclens lock {' '.join(run_ids[:2])}...' to lock the report.[/dim]")


@app.command("lock")
def lock_cmd(
    run_ids: list[str] = typer.Argument(..., help="Run IDs from 'bgclens run-batch'."),
    rocrate: bool = typer.Option(False, "--rocrate/--no-rocrate", help="Wrap in RO-Crate archive."),
    out_dir: Path = typer.Option(Path(".bgclens_runs/reports"), "--out", "-o", help="Output directory."),
) -> None:
    """Render a batch report, lock it (immutable), and optionally wrap in RO-Crate."""
    from bgclens.core.provenance import RunRecord
    from bgclens.model import BatchReport
    from bgclens.interpret.reduce import reduce_summary
    from bgclens.report.quarto import render_batch

    records: list[RunRecord] = []
    for run_id in run_ids:
        stem = run_id if not run_id.endswith(".yaml") else run_id[:-5]
        for search_dir in [Path(".bgclens_runs"), Path(".")]:
            candidate = search_dir / f"{stem}.yaml"
            if candidate.exists():
                try:
                    records.append(RunRecord.from_yaml(candidate.read_text()))
                except Exception as e:
                    console.print(f"[yellow]⚠ Could not load {candidate}: {e}[/yellow]")
                break

    if not records:
        console.print("[red]✖ No valid run records found.[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Rendering batch report for {len(records)} run(s)…[/bold]")

    # Build comparison dict
    comparison = {}
    for rec in records:
        rs = rec.result_summary or {}
        cid = (rec.run_spec or {}).get("cluster_id", "unknown")
        mid = (rec.run_spec or {}).get("method_id", "unknown")
        comparison[f"{mid}@{cid}"] = rs.get("interpretation", f"{mid} completed")

    proj_name = Path(records[0].project_path).name
    summary_text = reduce_summary([r.result_summary or {} for r in records])

    batch = BatchReport(
        project_name=proj_name,
        records=records,
        summary=summary_text,
        cluster_comparison=comparison,
    )

    report = render_batch(batch, out_dir)
    console.print(f"[green]✔ Report written:[/] {report.qmd_path}")

    # Lock
    if report.qmd_path and report.qmd_path.exists():
        locked_path = records[0].lock(report.qmd_path)
        console.print(f"[green]✔ Locked:[/] {locked_path} (immutable)")
    else:
        console.print("[yellow]⚠ Could not lock: report file not found.[/yellow]")
        raise typer.Exit(1)

    # RO-Crate
    if rocrate:
        try:
            from bgclens.report.rocrate import wrap
            crate = wrap(records[0], extra_files=[])
            if crate:
                console.print(f"[green]✔ RO-Crate:[/] {crate}")
            else:
                console.print("[yellow]⚠ RO-Crate wrap failed (non-fatal).[/yellow]")
        except Exception as e:
            console.print(f"[yellow]⚠ RO-Crate wrap error: {e}[/yellow]")

    if report.html_path:
        console.print(f"[green]✔ HTML:[/] {report.html_path}")


@app.command("chat")
def chat_cmd(
    project: Path = typer.Argument(..., help="BGCFlow project directory."),
    message: str = typer.Option(..., "--message", "-q", help="Question to ask."),
    mention: Optional[str] = typer.Option(None, "--mention", help="@mention target (e.g. @gcf_001)."),
    run_id: Optional[str] = typer.Option(None, "--run", help="Run record ID to include as context."),
) -> None:
    """Ask a question about the project (grounded in analysis results, no fabrication)."""
    from bgclens.core.api import open_project
    from bgclens.interpret.chat import chat
    from bgclens.interpret.mentions import parse
    from bgclens.model import Turn
    from bgclens.core.provenance import RunRecord

    try:
        proj = open_project(project)
    except ValueError as e:
        console.print(f"[red]✖ {e}[/red]")
        raise typer.Exit(1)

    records: list[RunRecord] = []
    if run_id:
        stem = run_id if not run_id.endswith(".yaml") else run_id[:-5]
        for search_dir in [Path(".bgclens_runs"), Path(".")]:
            candidate = search_dir / f"{stem}.yaml"
            if candidate.exists():
                try:
                    records.append(RunRecord.from_yaml(candidate.read_text()))
                except Exception:
                    pass
                break

    full_message = message
    if mention:
        full_message = f"{mention} {message}" if not message.startswith("@") else message

    mentions = parse(full_message)
    turn = chat(proj, records, [], full_message, mentions)

    console.print(f"\n[bold blue]BGCLens:[/bold blue] {turn.content}")
    if turn.mentions:
        console.print(f"[dim]Context scoped to: {', '.join(turn.mentions)}[/dim]")
    console.print("[dim]Answers grounded in retrieved data only. No fabrication.[/dim]")


@app.command("web")
def web_cmd(
    host: str = typer.Option("127.0.0.1", help="Host to bind."),
    port: int = typer.Option(8766, help="Port to bind."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Do not open browser automatically."),
) -> None:
    """Launch the BGCLens web UI and open a browser."""
    import webbrowser
    import uvicorn

    url = f"http://{host}:{port}"
    console.print(f"[bold green]Starting BGCLens web UI at {url}[/bold green]")
    if not no_browser:
        webbrowser.open(url)
    uvicorn.run("bgclens_web.api.main:app", host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    app()
