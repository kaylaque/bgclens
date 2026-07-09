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
    intent: str = typer.Option(..., "--intent", "-i", help="Analysis intent: enrichment|diversity|ordination|clustering|comparison|network_structure"),
    topic: str = typer.Option("BGC analysis", "--topic", "-t", help="Research question (free text, used for literature ranking)."),
    no_literature: bool = typer.Option(False, "--no-literature", help="Skip literature ranking (faster)."),
) -> None:
    """Show method recommendations for the given intent and topic."""
    from bgclens.core.api import open_project, recommend
    from bgclens.core.intent import AnalysisRequest, Intent

    try:
        proj = open_project(project)
        request = AnalysisRequest(topic=topic, intent=Intent(intent))
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


@app.command("web")
def web_cmd(
    host: str = typer.Option("127.0.0.1", help="Host to bind."),
    port: int = typer.Option(8765, help="Port to bind."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Do not open browser automatically."),
) -> None:
    """Launch the BGCLens web UI and open a browser."""
    import webbrowser
    import uvicorn

    url = f"http://{host}:{port}"
    console.print(f"[bold green]Starting BGCLens web UI at {url}[/bold green]")
    if not no_browser:
        webbrowser.open(url)
    uvicorn.run("bgclens_web.api.main:app", host=host, port=port, reload=False, log_level="warning")


if __name__ == "__main__":
    app()
