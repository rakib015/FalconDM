import re
from typing import List

class BatchManager:
    """Expands URL patterns (e.g., [01-20], [a-z], [A-Z]) and parses multi-line URL lists."""

    @staticmethod
    def expand_pattern(pattern_url: str) -> List[str]:
        """
        Expands numerical and alphabetical range patterns like:
        - Numerical: https://example.com/file[01-15].zip -> 01 through 15 with zero padding
        - Alphabetical: https://example.com/chapter_[a-d].pdf -> chapter_a through chapter_d
        Recursively expands multi-dimensional patterns (e.g., /part[1-2]_[a-b].zip).
        """
        # 1. Numerical pattern: e.g. [01-15] or [1-100]
        num_match = re.search(r'\[(\d+)-(\d+)\]', pattern_url)
        if num_match:
            start_str, end_str = num_match.groups()
            start, end = int(start_str), int(end_str)
            width = len(start_str) if start_str.startswith('0') else 0

            prefix = pattern_url[:num_match.start()]
            suffix = pattern_url[num_match.end():]

            urls = []
            step = 1 if start <= end else -1
            for num in range(start, end + step, step):
                formatted_num = f"{num:0{width}d}" if width > 0 else str(num)
                sub_url = f"{prefix}{formatted_num}{suffix}"
                urls.extend(BatchManager.expand_pattern(sub_url))
            return urls

        # 2. Alphabetical pattern: e.g. [a-z] or [A-Z]
        alpha_match = re.search(r'\[([a-zA-Z])-([a-zA-Z])\]', pattern_url)
        if alpha_match:
            c1, c2 = alpha_match.groups()
            prefix = pattern_url[:alpha_match.start()]
            suffix = pattern_url[alpha_match.end():]

            urls = []
            step = 1 if ord(c1) <= ord(c2) else -1
            for code in range(ord(c1), ord(c2) + step, step):
                sub_url = f"{prefix}{chr(code)}{suffix}"
                urls.extend(BatchManager.expand_pattern(sub_url))
            return urls

        return [pattern_url]

    @staticmethod
    def parse_multiline(text: str) -> List[str]:
        """Parses a multi-line string containing multiple URLs."""
        urls = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("http://") or line.startswith("https://"):
                urls.append(line)
        return urls
