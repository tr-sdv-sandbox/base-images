"""
Test result reporting in various formats.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from .models import TestReport, TestResult, TestStatus, StepResult


logger = logging.getLogger(__name__)


class TestReporter:
    """Generate test reports in various formats"""
    
    @staticmethod
    def generate_report(report: TestReport, 
                       format: str = "console",
                       output: Optional[Union[str, Path]] = None) -> str:
        """
        Generate test report in specified format.
        
        Args:
            report: Test execution report
            format: Output format (console, json, markdown, junit)
            output: Optional output file path
            
        Returns:
            Generated report as string
        """
        if format == "console":
            content = TestReporter._generate_console_report(report)
        elif format == "json":
            content = TestReporter._generate_json_report(report)
        elif format == "markdown":
            content = TestReporter._generate_markdown_report(report)
        elif format == "junit":
            content = TestReporter._generate_junit_report(report)
        else:
            raise ValueError(f"Unknown report format: {format}")
            
        # Write to file if specified
        if output:
            output = Path(output)
            output.parent.mkdir(parents=True, exist_ok=True)
            with open(output, 'w') as f:
                f.write(content)
            logger.info(f"Report written to {output}")
            
        return content
    
    @staticmethod
    def _generate_console_report(report: TestReport) -> str:
        """Generate human-readable console report"""
        lines = []
        
        # Header
        lines.append("=" * 80)
        lines.append(f"Test Report: {report.suite.name}")
        lines.append("=" * 80)
        lines.append(f"Started: {report.start_time.isoformat()}")
        lines.append(f"Duration: {report.total_duration_ms:.1f}ms")
        lines.append("")
        
        # Summary
        summary = report.get_summary()
        lines.append("Summary:")
        lines.append(f"  Total:   {summary['total']}")
        lines.append(f"  Passed:  {summary['passed']} "
                    f"({summary['passed']/summary['total']*100:.1f}%)")
        lines.append(f"  Failed:  {summary['failed']}")
        lines.append(f"  Skipped: {summary['skipped']}")
        lines.append(f"  Errors:  {summary['error']}")
        lines.append("")
        
        # Test case details
        lines.append("Test Cases:")
        lines.append("-" * 40)
        
        for result in report.results:
            status_icon = {
                TestStatus.PASSED: "✓",
                TestStatus.FAILED: "✗",
                TestStatus.SKIPPED: "○",
                TestStatus.ERROR: "!"
            }.get(result.status, "?")
            
            lines.append(f"{status_icon} {result.test_case.name}")
            lines.append(f"  Status: {result.status.value}")
            lines.append(f"  Duration: {result.duration_ms:.1f}ms")
            
            # Show requirements
            if result.test_case.requirements:
                lines.append(f"  Requirements: {', '.join(result.test_case.requirements)}")
                
            # Show failed steps
            failed_steps = [sr for sr in result.step_results if sr.status != TestStatus.PASSED]
            if failed_steps:
                lines.append("  Failed Steps:")
                for sr in failed_steps:
                    lines.append(f"    - {sr.step.type.value}: {sr.message}")
                    
            lines.append("")
            
        # Requirements coverage
        if report.spec and report.spec.requirements:
            lines.append("Requirements Coverage:")
            lines.append("-" * 40)
            
            coverage = report.get_requirements_coverage()
            for req_id in sorted(report.spec.requirements.keys()):
                req = report.spec.requirements[req_id]
                tests = coverage.get(req_id, [])
                
                if tests:
                    lines.append(f"✓ {req_id}: {len(tests)} test(s)")
                else:
                    lines.append(f"✗ {req_id}: NOT TESTED")
                    
            lines.append("")
            
        return "\n".join(lines)
    
    @staticmethod
    def _generate_json_report(report: TestReport) -> str:
        """Generate JSON report"""
        data = {
            "suite": report.suite.name,
            "start_time": report.start_time.isoformat(),
            "end_time": report.end_time.isoformat() if report.end_time else None,
            "duration_ms": report.total_duration_ms,
            "summary": report.get_summary(),
            "results": []
        }
        
        # Add test results
        for result in report.results:
            test_data = {
                "name": result.test_case.name,
                "status": result.status.value,
                "duration_ms": result.duration_ms,
                "requirements": result.test_case.requirements,
                "steps": []
            }
            
            # Add step results
            for step_result in result.step_results:
                step_data = {
                    "type": step_result.step.type.value,
                    "status": step_result.status.value,
                    "message": step_result.message,
                    "duration_ms": step_result.duration_ms
                }
                
                if step_result.actual_value is not None:
                    step_data["actual"] = step_result.actual_value
                if step_result.expected_value is not None:
                    step_data["expected"] = step_result.expected_value
                    
                test_data["steps"].append(step_data)
                
            data["results"].append(test_data)
            
        # Add requirements coverage
        if report.spec:
            data["requirements_coverage"] = report.get_requirements_coverage()
            
        return json.dumps(data, indent=2, default=str)
    
    @staticmethod
    def _generate_markdown_report(report: TestReport) -> str:
        """Generate Markdown report"""
        lines = []
        
        # Header
        lines.append(f"# Test Report: {report.suite.name}")
        lines.append("")
        lines.append(f"**Started:** {report.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Duration:** {report.total_duration_ms:.1f}ms")
        lines.append("")
        
        # Summary table
        summary = report.get_summary()
        lines.append("## Summary")
        lines.append("")
        lines.append("| Status | Count | Percentage |")
        lines.append("|--------|-------|------------|")
        lines.append(f"| Total | {summary['total']} | 100% |")
        lines.append(f"| ✓ Passed | {summary['passed']} | "
                    f"{summary['passed']/summary['total']*100:.1f}% |")
        lines.append(f"| ✗ Failed | {summary['failed']} | "
                    f"{summary['failed']/summary['total']*100:.1f}% |")
        lines.append(f"| ○ Skipped | {summary['skipped']} | "
                    f"{summary['skipped']/summary['total']*100:.1f}% |")
        lines.append(f"| ! Error | {summary['error']} | "
                    f"{summary['error']/summary['total']*100:.1f}% |")
        lines.append("")
        
        # Test case details
        lines.append("## Test Cases")
        lines.append("")
        
        for result in report.results:
            status_icon = {
                TestStatus.PASSED: "✓",
                TestStatus.FAILED: "✗", 
                TestStatus.SKIPPED: "○",
                TestStatus.ERROR: "!"
            }.get(result.status, "?")
            
            lines.append(f"### {status_icon} {result.test_case.name}")
            lines.append("")
            lines.append(f"- **Status:** {result.status.value}")
            lines.append(f"- **Duration:** {result.duration_ms:.1f}ms")
            
            if result.test_case.requirements:
                lines.append(f"- **Requirements:** {', '.join(result.test_case.requirements)}")
                
            if result.test_case.description:
                lines.append(f"- **Description:** {result.test_case.description}")
                
            # Show step details for failed tests
            if result.status != TestStatus.PASSED:
                lines.append("")
                lines.append("#### Steps")
                lines.append("")
                
                for i, sr in enumerate(result.step_results):
                    status = "✓" if sr.status == TestStatus.PASSED else "✗"
                    lines.append(f"{i+1}. {status} **{sr.step.type.value}** - {sr.message}")
                    
            lines.append("")
            
        # Requirements coverage
        if report.spec and report.spec.requirements:
            lines.append("## Requirements Coverage")
            lines.append("")
            
            coverage = report.get_requirements_coverage()
            covered = len([r for r, t in coverage.items() if t])
            total = len(report.spec.requirements)
            
            lines.append(f"**Coverage:** {covered}/{total} ({covered/total*100:.1f}%)")
            lines.append("")
            
            lines.append("| Requirement | Status | Tests |")
            lines.append("|-------------|--------|-------|")
            
            for req_id in sorted(report.spec.requirements.keys()):
                req = report.spec.requirements[req_id]
                tests = coverage.get(req_id, [])
                
                if tests:
                    status = "✓ Covered"
                    test_list = ", ".join(tests)
                else:
                    status = "✗ Not Covered"
                    test_list = "-"
                    
                lines.append(f"| {req_id} | {status} | {test_list} |")
                
        return "\n".join(lines)
    
    @staticmethod
    def _generate_junit_report(report: TestReport) -> str:
        """Generate JUnit XML report"""
        # Simple JUnit format implementation
        lines = []
        
        lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        
        summary = report.get_summary()
        lines.append(f'<testsuites tests="{summary["total"]}" '
                    f'failures="{summary["failed"]}" '
                    f'errors="{summary["error"]}" '
                    f'time="{report.total_duration_ms/1000:.3f}">')
        
        lines.append(f'  <testsuite name="{report.suite.name}" '
                    f'tests="{summary["total"]}" '
                    f'failures="{summary["failed"]}" '
                    f'errors="{summary["error"]}" '
                    f'time="{report.total_duration_ms/1000:.3f}">')
        
        for result in report.results:
            lines.append(f'    <testcase name="{result.test_case.name}" '
                        f'time="{result.duration_ms/1000:.3f}">')
            
            if result.status == TestStatus.FAILED:
                failed_step = next((sr for sr in result.step_results 
                                  if sr.status == TestStatus.FAILED), None)
                if failed_step:
                    lines.append(f'      <failure message="{failed_step.message}"/>')
                    
            elif result.status == TestStatus.ERROR:
                lines.append(f'      <error message="{result.error_message or "Unknown error"}"/>')
                
            elif result.status == TestStatus.SKIPPED:
                lines.append('      <skipped/>')
                
            lines.append('    </testcase>')
            
        lines.append('  </testsuite>')
        lines.append('</testsuites>')
        
        return "\n".join(lines)