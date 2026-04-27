"""CLI commands for cross-framework comparison and analysis.

Provides commands to compare frameworks, analyze all pairs, and generate
equivalence mappings. All output is formatted using Rich tables and panels.
"""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.cross_framework_analyzer import CrossFrameworkAnalyzer
from src.core.framework_registry import SUPPORTED_FRAMEWORKS, FrameworkRegistry
from src.core.framework_loader import FrameworkLoader
from src.data.database import get_session
from src.data.repositories.framework_repository import FrameworkRepository
from src.ml.control_matcher import ControlMatcher
from src.ml.embeddings import EmbeddingConfig, EmbeddingGenerator
from src.ml.similarity import SimilarityCalculator
from src.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()

# Framework whitelist as a list for Click choices
FRAMEWORK_CHOICES = sorted(SUPPORTED_FRAMEWORKS)


@click.group(name="compare")
def compare() -> None:
    """Compare and analyze controls across different frameworks."""


@compare.command(name="frameworks")
@click.option(
    "--source",
    required=True,
    type=click.Choice(FRAMEWORK_CHOICES, case_sensitive=False),
    help="Source framework identifier",
)
@click.option(
    "--target",
    required=True,
    type=click.Choice(FRAMEWORK_CHOICES, case_sensitive=False),
    help="Target framework identifier",
)
@click.option(
    "--output-format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format (table or json)",
)
def frameworks_command(source: str, target: str, output_format: str) -> None:
    """Compare controls between two frameworks.
    
    Performs ML-based semantic matching between source and target frameworks,
    showing mapping coverage, confidence levels, and control relationships.
    """
    try:
        # Initialize dependencies
        logger.info("Initializing cross-framework comparison")
        
        # Set up data directory and registry
        data_dir = Path("data")
        registry = FrameworkRegistry(data_dir)
        
        # Set up ML components with explicit embedding configuration.
        embedding_gen = EmbeddingGenerator(config=EmbeddingConfig())
        similarity_calc = SimilarityCalculator()
        
        # Get database session and repositories
        with get_session() as session:
            framework_repo = FrameworkRepository(session)
            
            # Initialize control matcher
            matcher = ControlMatcher(
                embedding_generator=embedding_gen,
                similarity_calculator=similarity_calc,
                control_repository=None,  # Will be injected at runtime
                framework_repository=framework_repo,
            )
            
            # Initialize analyzer
            analyzer = CrossFrameworkAnalyzer(matcher, registry)
            
            # Run the analysis
            console.print(f"\n[cyan]Analyzing {source} → {target}...[/cyan]\n")
            result = analyzer.analyze(source, target)
            
            # Display results based on format
            if output_format == "json":
                # Output as JSON
                output = {
                    "source_framework": result.source_framework,
                    "target_framework": result.target_framework,
                    "total_source_controls": result.total_source_controls,
                    "mapped_controls": result.mapped_controls,
                    "unmapped_controls": result.unmapped_controls,
                    "mapping_percentage": result.mapping_percentage,
                    "analyzed_at": result.analyzed_at.isoformat(),
                    "matches": [
                        {
                            "source_control_id": m.source_control_id,
                            "matched_control_id": m.matched_control_id,
                            "similarity_score": m.similarity_score,
                            "confidence": m.confidence,
                        }
                        for m in result.matches
                    ],
                }
                console.print_json(json.dumps(output, indent=2))
            else:
                # Display as rich table
                _display_framework_comparison_table(result)
        
        logger.info("Comparison complete")
        
    except Exception as exc:
        # Display error in rich panel
        error_panel = Panel(
            f"[red]{str(exc)}[/red]",
            title="❌ Comparison Failed",
            border_style="red",
        )
        console.print(error_panel)
        logger.error(f"Comparison failed: {exc}")
        raise click.Abort()


@compare.command(name="all-pairs")
@click.option(
    "--output-format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format (table or json)",
)
def all_pairs_command(output_format: str) -> None:
    """Analyze all possible framework pairs.
    
    Runs cross-framework analysis for all 6 unique pairs of frameworks
    and displays a summary of mapping coverage for each.
    """
    try:
        # Initialize dependencies
        logger.info("Starting all-pairs analysis")
        
        # Set up data directory and registry
        data_dir = Path("data")
        registry = FrameworkRegistry(data_dir)
        
        # Set up ML components with explicit embedding configuration.
        embedding_gen = EmbeddingGenerator(config=EmbeddingConfig())
        similarity_calc = SimilarityCalculator()
        
        # Get database session and repositories
        with get_session() as session:
            framework_repo = FrameworkRepository(session)
            
            # Initialize control matcher
            matcher = ControlMatcher(
                embedding_generator=embedding_gen,
                similarity_calculator=similarity_calc,
                control_repository=None,
                framework_repository=framework_repo,
            )
            
            # Initialize analyzer
            analyzer = CrossFrameworkAnalyzer(matcher, registry)
            
            # Run analysis for all pairs
            console.print("\n[cyan]Analyzing all framework pairs...[/cyan]\n")
            results = analyzer.analyze_all_pairs()
            
            # Display results based on format
            if output_format == "json":
                # Output as JSON
                output = [
                    {
                        "source_framework": r.source_framework,
                        "target_framework": r.target_framework,
                        "total_source_controls": r.total_source_controls,
                        "mapped_controls": r.mapped_controls,
                        "unmapped_controls": r.unmapped_controls,
                        "mapping_percentage": r.mapping_percentage,
                    }
                    for r in results
                ]
                console.print_json(json.dumps(output, indent=2))
            else:
                # Display as rich table
                _display_all_pairs_summary_table(results)
        
        logger.info("All-pairs analysis complete")
        
    except Exception as exc:
        # Display error in rich panel
        error_panel = Panel(
            f"[red]{str(exc)}[/red]",
            title="❌ Analysis Failed",
            border_style="red",
        )
        console.print(error_panel)
        logger.error(f"All-pairs analysis failed: {exc}")
        raise click.Abort()


@compare.command(name="equivalence")
@click.option(
    "--source",
    required=True,
    type=click.Choice(FRAMEWORK_CHOICES, case_sensitive=False),
    help="Source framework identifier",
)
@click.option(
    "--target",
    required=True,
    type=click.Choice(FRAMEWORK_CHOICES, case_sensitive=False),
    help="Target framework identifier",
)
def equivalence_command(source: str, target: str) -> None:
    """Display flat equivalence map between two frameworks.
    
    Shows a simple mapping of source control IDs to their matched target
    control IDs. Only includes HIGH and MEDIUM confidence matches.
    """
    try:
        # Initialize dependencies
        logger.info("Building equivalence map")
        
        # Set up data directory and registry
        data_dir = Path("data")
        registry = FrameworkRegistry(data_dir)
        
        # Set up ML components with explicit embedding configuration.
        embedding_gen = EmbeddingGenerator(config=EmbeddingConfig())
        similarity_calc = SimilarityCalculator()
        
        # Get database session and repositories
        with get_session() as session:
            framework_repo = FrameworkRepository(session)
            
            # Initialize control matcher
            matcher = ControlMatcher(
                embedding_generator=embedding_gen,
                similarity_calculator=similarity_calc,
                control_repository=None,
                framework_repository=framework_repo,
            )
            
            # Initialize analyzer
            analyzer = CrossFrameworkAnalyzer(matcher, registry)
            
            # Get equivalence map
            console.print(f"\n[cyan]Building equivalence map for {source} → {target}...[/cyan]\n")
            equivalence_map = analyzer.get_equivalence_map(source, target)
            
            # Display as rich table
            _display_equivalence_table(source, target, equivalence_map)
        
        logger.info("Equivalence map created")
        
    except Exception as exc:
        # Display error in rich panel
        error_panel = Panel(
            f"[red]{str(exc)}[/red]",
            title="❌ Equivalence Map Failed",
            border_style="red",
        )
        console.print(error_panel)
        logger.error(f"Equivalence map failed: {exc}")
        raise click.Abort()


def _display_framework_comparison_table(result) -> None:
    """Display detailed comparison results in a rich table.
    
    Shows mapping statistics and sample matches with confidence levels.
    """
    # Create summary table
    summary_table = Table(title=f"{result.source_framework} → {result.target_framework}", show_header=False)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green")
    
    summary_table.add_row("Total Source Controls", str(result.total_source_controls))
    summary_table.add_row("Mapped Controls", str(result.mapped_controls))
    summary_table.add_row("Unmapped Controls", str(result.unmapped_controls))
    summary_table.add_row("Mapping Coverage", f"{result.mapping_percentage}%")
    
    console.print(summary_table)
    console.print()
    
    # Create matches table (show first 20 matches)
    if result.matches:
        matches_table = Table(title="Sample Control Matches", show_lines=True)
        matches_table.add_column("Source Control", style="cyan")
        matches_table.add_column("Target Control", style="yellow")
        matches_table.add_column("Similarity", justify="right", style="magenta")
        matches_table.add_column("Confidence", style="green")
        
        # Add up to 20 matches
        for match in result.matches[:20]:
            matches_table.add_row(
                match.source_control_id,
                match.matched_control_id,
                f"{match.similarity_score:.3f}",
                match.confidence,
            )
        
        console.print(matches_table)
    else:
        console.print("[yellow]No matches found[/yellow]")


def _display_all_pairs_summary_table(results) -> None:
    """Display summary table for all framework pairs.
    
    Shows mapping coverage percentages for each framework pair analyzed.
    """
    # Create summary table
    table = Table(title="Cross-Framework Mapping Summary", show_lines=True)
    table.add_column("Source", style="cyan")
    table.add_column("Target", style="yellow")
    table.add_column("Total Controls", justify="right", style="white")
    table.add_column("Mapped", justify="right", style="green")
    table.add_column("Coverage %", justify="right", style="magenta")
    
    # Add each result as a row
    for result in results:
        table.add_row(
            result.source_framework,
            result.target_framework,
            str(result.total_source_controls),
            str(result.mapped_controls),
            f"{result.mapping_percentage:.1f}%",
        )
    
    console.print(table)


def _display_equivalence_table(source: str, target: str, equivalence_map: dict[str, list[str]]) -> None:
    """Display equivalence mapping as a rich table.
    
    Shows flat mapping of source controls to matched target controls.
    """
    # Create equivalence table
    table = Table(title=f"Equivalence Map: {source} → {target}", show_lines=True)
    table.add_column("Source Control", style="cyan")
    table.add_column("Matched Target Controls", style="yellow")
    table.add_column("Count", justify="right", style="green")
    
    # Add each mapping as a row
    for source_id, target_ids in sorted(equivalence_map.items()):
        target_list = ", ".join(target_ids)
        table.add_row(source_id, target_list, str(len(target_ids)))
    
    console.print(table)
    console.print(f"\n[green]Total mapped controls: {len(equivalence_map)}[/green]")
