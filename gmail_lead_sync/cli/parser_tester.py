"""
Parser tester CLI utility for Gmail Lead Sync Engine.

This module provides a command-line tool for testing regex patterns against
sample email content. It helps agents verify parsing rules before deploying
them to production.

Features:
- Test name and phone regex patterns against email files
- Display all matches with line numbers
- Highlight matches in context
- Validate regex syntax and display error messages
"""

import re
import sys
import argparse
from typing import List, Tuple, Optional
from pathlib import Path


class ParserTester:
    """
    Utility for testing regex patterns against email content.
    
    This class provides methods to test regex patterns, highlight matches,
    and validate regex syntax. It's designed to help users verify their
    parsing rules before adding them to Lead_Source configurations.
    """
    
    def validate_regex(self, pattern: str) -> Tuple[bool, Optional[str]]:
        """
        Validate regex pattern syntax.
        
        Checks if the regex pattern is syntactically correct and can be
        compiled by Python's re module.
        
        Args:
            pattern: Regex pattern string to validate
            
        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is None.
        """
        try:
            re.compile(pattern)
            return True, None
        except re.error as e:
            return False, f"Invalid regex syntax: {e}"
    
    def test_pattern(
        self,
        email_body: str,
        pattern: str,
        pattern_type: str
    ) -> List[Tuple[str, int]]:
        """
        Test regex pattern and find all matches in email body.
        
        Applies the regex pattern to the email body and returns all matches
        with their line numbers. Uses the first capture group if present,
        otherwise returns the full match.
        
        Args:
            email_body: Full text content of the email
            pattern: Regex pattern to test
            pattern_type: Type of pattern ('name' or 'phone') for display
            
        Returns:
            List of tuples (match_text, line_number) for all matches found
        """
        matches = []
        lines = email_body.split('\n')
        
        for line_num, line in enumerate(lines, start=1):
            for match in re.finditer(pattern, line):
                # Use first capture group if present, otherwise full match
                if match.groups():
                    match_text = match.group(1)
                else:
                    match_text = match.group(0)
                
                matches.append((match_text, line_num))
        
        return matches
    
    def highlight_matches(
        self,
        email_body: str,
        matches: List[Tuple[str, int]]
    ) -> str:
        """
        Show matches in context with highlighting.
        
        Returns the email body with matches highlighted using ANSI color codes
        for terminal display. Shows line numbers for matched lines.
        
        Args:
            email_body: Full text content of the email
            matches: List of tuples (match_text, line_number) from test_pattern
            
        Returns:
            Formatted string with highlighted matches
        """
        if not matches:
            return email_body
        
        # ANSI color codes for highlighting
        HIGHLIGHT = '\033[93m'  # Yellow
        BOLD = '\033[1m'
        RESET = '\033[0m'
        
        lines = email_body.split('\n')
        result_lines = []
        
        # Get set of line numbers with matches
        matched_line_nums = {line_num for _, line_num in matches}
        
        for line_num, line in enumerate(lines, start=1):
            if line_num in matched_line_nums:
                # Highlight all matches in this line
                highlighted_line = line
                # Get all matches for this line
                line_matches = [match_text for match_text, ln in matches if ln == line_num]
                
                # Sort by length (longest first) to avoid partial replacements
                line_matches.sort(key=len, reverse=True)
                
                for match_text in line_matches:
                    # Escape special regex characters in match_text for replacement
                    escaped_match = re.escape(match_text)
                    highlighted_line = re.sub(
                        f'({escaped_match})',
                        f'{HIGHLIGHT}{BOLD}\\1{RESET}',
                        highlighted_line,
                        count=1
                    )
                
                result_lines.append(f"Line {line_num}: {highlighted_line}")
            else:
                result_lines.append(f"Line {line_num}: {line}")
        
        return '\n'.join(result_lines)


def main() -> None:
    """
    Main entry point for the parser tester CLI.
    
    Parses command-line arguments and runs the pattern testing workflow.
    """
    parser = argparse.ArgumentParser(
        description='Test regex patterns against email content',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test name extraction
  python -m gmail_lead_sync.cli.parser_tester --email-file sample.txt --name-regex "Name:\\s*(.+)"
  
  # Test phone extraction
  python -m gmail_lead_sync.cli.parser_tester --email-file sample.txt --phone-regex "Phone:\\s*([\\d\\-]+)"
  
  # Test both patterns
  python -m gmail_lead_sync.cli.parser_tester --email-file sample.txt \\
      --name-regex "Name:\\s*(.+)" \\
      --phone-regex "Phone:\\s*([\\d\\-]+)"
        """
    )
    
    parser.add_argument(
        '--email-file',
        required=True,
        type=str,
        help='Path to file containing email body text'
    )
    
    parser.add_argument(
        '--name-regex',
        type=str,
        help='Regex pattern for extracting lead name'
    )
    
    parser.add_argument(
        '--phone-regex',
        type=str,
        help='Regex pattern for extracting phone number'
    )
    
    args = parser.parse_args()
    
    # Validate that at least one pattern is provided
    if not args.name_regex and not args.phone_regex:
        parser.error('At least one of --name-regex or --phone-regex must be provided')
    
    # Read email file
    email_file = Path(args.email_file)
    if not email_file.exists():
        print(f"Error: Email file not found: {args.email_file}", file=sys.stderr)
        sys.exit(1)
    
    try:
        email_body = email_file.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading email file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Initialize tester
    tester = ParserTester()
    
    # Test name pattern if provided
    if args.name_regex:
        print("=" * 80)
        print("TESTING NAME PATTERN")
        print("=" * 80)
        print(f"Pattern: {args.name_regex}\n")
        
        # Validate syntax
        is_valid, error_msg = tester.validate_regex(args.name_regex)
        if not is_valid:
            print(f"❌ {error_msg}\n", file=sys.stderr)
        else:
            print("✓ Pattern syntax is valid\n")
            
            # Find matches
            matches = tester.test_pattern(email_body, args.name_regex, 'name')
            
            if matches:
                print(f"Found {len(matches)} match(es):\n")
                for i, (match_text, line_num) in enumerate(matches, start=1):
                    print(f"  {i}. Line {line_num}: '{match_text}'")
                print()
                
                # Show highlighted context
                print("Email body with matches highlighted:")
                print("-" * 80)
                print(tester.highlight_matches(email_body, matches))
                print("-" * 80)
            else:
                print("⚠ No matches found\n")
        
        print()
    
    # Test phone pattern if provided
    if args.phone_regex:
        print("=" * 80)
        print("TESTING PHONE PATTERN")
        print("=" * 80)
        print(f"Pattern: {args.phone_regex}\n")
        
        # Validate syntax
        is_valid, error_msg = tester.validate_regex(args.phone_regex)
        if not is_valid:
            print(f"❌ {error_msg}\n", file=sys.stderr)
        else:
            print("✓ Pattern syntax is valid\n")
            
            # Find matches
            matches = tester.test_pattern(email_body, args.phone_regex, 'phone')
            
            if matches:
                print(f"Found {len(matches)} match(es):\n")
                for i, (match_text, line_num) in enumerate(matches, start=1):
                    print(f"  {i}. Line {line_num}: '{match_text}'")
                print()
                
                # Show highlighted context
                print("Email body with matches highlighted:")
                print("-" * 80)
                print(tester.highlight_matches(email_body, matches))
                print("-" * 80)
            else:
                print("⚠ No matches found\n")
        
        print()
    
    print("=" * 80)
    print("TESTING COMPLETE")
    print("=" * 80)


if __name__ == '__main__':
    main()
