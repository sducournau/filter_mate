# -*- coding: utf-8 -*-
"""
Benchmark Report Generator for FilterMate.

v4.1.1 - January 2026 - EPIC-3 Sprint 1

PURPOSE:
Generates formatted reports from benchmark results:
1. JSON export for CI/automation
2. HTML reports with charts
3. Markdown reports for documentation
4. Console summary output
5. Comparison reports between runs

USAGE:
    from infrastructure.benchmark import ReportGenerator, BenchmarkResult
    
    generator = ReportGenerator(results)
    generator.to_json("benchmark_results.json")
    generator.to_html("benchmark_report.html")
    generator.to_markdown("BENCHMARKS.md")
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

from .framework import BenchmarkResult

logger = logging.getLogger('FilterMate.Benchmark.Report')


@dataclass
class ReportMetadata:
    """Metadata for benchmark report."""
    title: str = "FilterMate Benchmark Report"
    description: str = ""
    version: str = "4.1.1"
    timestamp: datetime = None
    environment: Dict[str, str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.environment is None:
            self.environment = {}


class ReportGenerator:
    """
    Generates benchmark reports in various formats.
    
    Supports JSON, HTML, Markdown, and console output.
    
    Example:
        results = runner.run_all()
        
        generator = ReportGenerator(results)
        generator.to_json("results.json")
        generator.to_html("report.html")
        
        # Or print summary
        print(generator.summary())
    """
    
    def __init__(
        self,
        results: List[BenchmarkResult],
        metadata: ReportMetadata = None,
    ):
        """
        Initialize report generator.
        
        Args:
            results: List of benchmark results
            metadata: Optional report metadata
        """
        self.results = results
        self.metadata = metadata or ReportMetadata()
    
    def summary(self) -> str:
        """
        Generate console summary.
        
        Returns:
            Formatted summary string
        """
        lines = [
            "=" * 60,
            f"  {self.metadata.title}",
            f"  Generated: {self.metadata.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
            "",
        ]
        
        for result in self.results:
            lines.append(result.summary())
        
        lines.extend([
            "",
            "-" * 60,
            f"Total benchmarks: {len(self.results)}",
            "=" * 60,
        ])
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert results to dictionary.
        
        Returns:
            Dictionary representation of results
        """
        return {
            'metadata': {
                'title': self.metadata.title,
                'description': self.metadata.description,
                'version': self.metadata.version,
                'timestamp': self.metadata.timestamp.isoformat(),
                'environment': self.metadata.environment,
            },
            'results': [r.to_dict() for r in self.results],
            'summary': {
                'total_benchmarks': len(self.results),
                'fastest': min((r.mean_ms for r in self.results), default=0),
                'slowest': max((r.mean_ms for r in self.results), default=0),
            }
        }
    
    def to_json(self, path: str, indent: int = 2) -> None:
        """
        Export results to JSON file.
        
        Args:
            path: Output file path
            indent: JSON indentation level
        """
        data = self.to_dict()
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        
        logger.info(f"📄 Saved JSON report to {path}")
    
    def to_markdown(self, path: str = None) -> str:
        """
        Generate Markdown report.
        
        Args:
            path: Optional output file path
            
        Returns:
            Markdown content string
        """
        lines = [
            f"# {self.metadata.title}",
            "",
            f"**Generated:** {self.metadata.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Version:** {self.metadata.version}",
            "",
        ]
        
        if self.metadata.description:
            lines.extend([self.metadata.description, ""])
        
        # Summary table
        lines.extend([
            "## Summary",
            "",
            "| Benchmark | Mean (ms) | Median (ms) | Std Dev | P95 (ms) | Ops/sec |",
            "|-----------|-----------|-------------|---------|----------|---------|",
        ])
        
        for r in self.results:
            lines.append(
                f"| {r.name} | {r.mean_ms:.2f} | {r.median_ms:.2f} | "
                f"{r.std_dev_ms:.2f} | {r.p95_ms:.2f} | {r.ops_per_second:.1f} |"
            )
        
        # Detailed results
        lines.extend([
            "",
            "## Detailed Results",
            "",
        ])
        
        for r in self.results:
            lines.extend([
                f"### {r.name}",
                "",
                f"**Description:** {r.description or 'N/A'}",
                "",
                f"- **Mean:** {r.mean_ms:.2f} ms",
                f"- **Median:** {r.median_ms:.2f} ms",
                f"- **Std Dev:** {r.std_dev_ms:.2f} ms",
                f"- **Min:** {r.min_ms:.2f} ms",
                f"- **Max:** {r.max_ms:.2f} ms",
                f"- **P95:** {r.p95_ms:.2f} ms",
                f"- **P99:** {r.p99_ms:.2f} ms",
                f"- **Iterations:** {r.iterations}",
                f"- **Warmup:** {r.warmup_iterations}",
                "",
            ])
            
            if r.metadata:
                lines.extend([
                    "**Metadata:**",
                    "```json",
                    json.dumps(r.metadata, indent=2),
                    "```",
                    "",
                ])
        
        content = "\n".join(lines)
        
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"📄 Saved Markdown report to {path}")
        
        return content
    
    def to_html(self, path: str = None) -> str:
        """
        Generate HTML report with styling.
        
        Args:
            path: Optional output file path
            
        Returns:
            HTML content string
        """
        # Build HTML
        html_parts = [
            "<!DOCTYPE html>",
            "<html lang='en'>",
            "<head>",
            "  <meta charset='UTF-8'>",
            "  <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
            f"  <title>{self.metadata.title}</title>",
            "  <style>",
            self._get_css_styles(),
            "  </style>",
            "</head>",
            "<body>",
            "  <div class='container'>",
            f"    <h1>{self.metadata.title}</h1>",
            f"    <p class='meta'>Generated: {self.metadata.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>",
            f"    <p class='meta'>Version: {self.metadata.version}</p>",
        ]
        
        # Summary section
        html_parts.extend([
            "    <h2>Summary</h2>",
            "    <table class='summary-table'>",
            "      <thead>",
            "        <tr>",
            "          <th>Benchmark</th>",
            "          <th>Mean (ms)</th>",
            "          <th>Median (ms)</th>",
            "          <th>Std Dev</th>",
            "          <th>P95 (ms)</th>",
            "          <th>Ops/sec</th>",
            "        </tr>",
            "      </thead>",
            "      <tbody>",
        ])
        
        for r in self.results:
            html_parts.append(
                f"        <tr>"
                f"<td>{r.name}</td>"
                f"<td>{r.mean_ms:.2f}</td>"
                f"<td>{r.median_ms:.2f}</td>"
                f"<td>{r.std_dev_ms:.2f}</td>"
                f"<td>{r.p95_ms:.2f}</td>"
                f"<td>{r.ops_per_second:.1f}</td>"
                f"</tr>"
            )
        
        html_parts.extend([
            "      </tbody>",
            "    </table>",
        ])
        
        # Chart placeholder
        html_parts.extend([
            "    <h2>Performance Chart</h2>",
            "    <div class='chart-container'>",
            self._generate_bar_chart_svg(),
            "    </div>",
        ])
        
        # Detailed results
        html_parts.extend([
            "    <h2>Detailed Results</h2>",
        ])
        
        for r in self.results:
            html_parts.extend([
                f"    <div class='result-card'>",
                f"      <h3>{r.name}</h3>",
                f"      <p class='description'>{r.description or 'No description'}</p>",
                f"      <div class='stats'>",
                f"        <div class='stat'><span class='label'>Mean</span><span class='value'>{r.mean_ms:.2f} ms</span></div>",
                f"        <div class='stat'><span class='label'>Median</span><span class='value'>{r.median_ms:.2f} ms</span></div>",
                f"        <div class='stat'><span class='label'>Min</span><span class='value'>{r.min_ms:.2f} ms</span></div>",
                f"        <div class='stat'><span class='label'>Max</span><span class='value'>{r.max_ms:.2f} ms</span></div>",
                f"        <div class='stat'><span class='label'>P95</span><span class='value'>{r.p95_ms:.2f} ms</span></div>",
                f"        <div class='stat'><span class='label'>Iterations</span><span class='value'>{r.iterations}</span></div>",
                f"      </div>",
                f"    </div>",
            ])
        
        html_parts.extend([
            "  </div>",
            "</body>",
            "</html>",
        ])
        
        content = "\n".join(html_parts)
        
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"📄 Saved HTML report to {path}")
        
        return content
    
    def _get_css_styles(self) -> str:
        """Get CSS styles for HTML report."""
        return """
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        h1 { color: #2c3e50; margin-bottom: 10px; }
        h2 { color: #34495e; margin: 30px 0 15px; border-bottom: 2px solid #3498db; padding-bottom: 5px; }
        h3 { color: #2980b9; margin-bottom: 10px; }
        .meta { color: #7f8c8d; font-size: 0.9em; margin-bottom: 5px; }
        .summary-table { 
            width: 100%; 
            border-collapse: collapse; 
            background: white;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            margin: 15px 0;
        }
        .summary-table th, .summary-table td { 
            padding: 12px 15px; 
            text-align: left; 
            border-bottom: 1px solid #ddd;
        }
        .summary-table th { 
            background: #3498db; 
            color: white; 
            font-weight: 600;
        }
        .summary-table tr:hover { background: #f8f9fa; }
        .chart-container { 
            background: white; 
            padding: 20px; 
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            margin: 15px 0;
        }
        .result-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            margin: 15px 0;
        }
        .description { color: #7f8c8d; margin-bottom: 15px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 15px; }
        .stat { text-align: center; }
        .stat .label { display: block; font-size: 0.8em; color: #7f8c8d; text-transform: uppercase; }
        .stat .value { display: block; font-size: 1.4em; font-weight: 600; color: #2c3e50; }
        """
    
    def _generate_bar_chart_svg(self) -> str:
        """Generate simple SVG bar chart."""
        if not self.results:
            return "<p>No data available</p>"
        
        max_mean = max(r.mean_ms for r in self.results)
        if max_mean == 0:
            max_mean = 1
        
        bar_height = 30
        chart_width = 600
        chart_height = len(self.results) * (bar_height + 10) + 40
        
        svg_parts = [
            f'<svg width="{chart_width}" height="{chart_height}" xmlns="http://www.w3.org/2000/svg">',
            '<style>',
            '  .bar { fill: #3498db; }',
            '  .bar:hover { fill: #2980b9; }',
            '  .label { font-size: 12px; fill: #333; }',
            '  .value { font-size: 11px; fill: #666; }',
            '</style>',
        ]
        
        for i, r in enumerate(self.results):
            y = i * (bar_height + 10) + 20
            bar_width = (r.mean_ms / max_mean) * (chart_width - 200)
            
            # Truncate name if too long
            name = r.name[:25] + "..." if len(r.name) > 25 else r.name
            
            svg_parts.extend([
                f'<text x="5" y="{y + 20}" class="label">{name}</text>',
                f'<rect x="180" y="{y}" width="{bar_width}" height="{bar_height}" class="bar" rx="3"/>',
                f'<text x="{185 + bar_width}" y="{y + 20}" class="value">{r.mean_ms:.2f} ms</text>',
            ])
        
        svg_parts.append('</svg>')
        return "\n".join(svg_parts)
    
    def compare_with(
        self,
        previous_results: List[BenchmarkResult],
        threshold_percent: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Compare current results with previous run.
        
        Args:
            previous_results: Results from previous benchmark run
            threshold_percent: Threshold for flagging regressions
            
        Returns:
            Comparison report dictionary
        """
        previous_by_name = {r.name: r for r in previous_results}
        
        comparisons = []
        regressions = []
        improvements = []
        
        for current in self.results:
            previous = previous_by_name.get(current.name)
            if not previous:
                continue
            
            diff_ms = current.mean_ms - previous.mean_ms
            diff_pct = (diff_ms / previous.mean_ms * 100) if previous.mean_ms > 0 else 0
            
            comparison = {
                'name': current.name,
                'current_mean_ms': current.mean_ms,
                'previous_mean_ms': previous.mean_ms,
                'diff_ms': diff_ms,
                'diff_percent': diff_pct,
            }
            comparisons.append(comparison)
            
            if diff_pct > threshold_percent:
                regressions.append(comparison)
            elif diff_pct < -threshold_percent:
                improvements.append(comparison)
        
        return {
            'comparisons': comparisons,
            'regressions': regressions,
            'improvements': improvements,
            'threshold_percent': threshold_percent,
            'has_regressions': len(regressions) > 0,
        }


def generate_report(
    results: List[BenchmarkResult],
    output_dir: str = ".",
    formats: List[str] = None,
) -> Dict[str, str]:
    """
    Convenience function to generate reports in multiple formats.
    
    Args:
        results: Benchmark results
        output_dir: Output directory
        formats: List of formats ('json', 'html', 'md')
        
    Returns:
        Dict mapping format to output path
    """
    formats = formats or ['json', 'html', 'md']
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generator = ReportGenerator(results)
    outputs = {}
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if 'json' in formats:
        path = output_dir / f"benchmark_{timestamp}.json"
        generator.to_json(str(path))
        outputs['json'] = str(path)
    
    if 'html' in formats:
        path = output_dir / f"benchmark_{timestamp}.html"
        generator.to_html(str(path))
        outputs['html'] = str(path)
    
    if 'md' in formats:
        path = output_dir / f"benchmark_{timestamp}.md"
        generator.to_markdown(str(path))
        outputs['md'] = str(path)
    
    return outputs
