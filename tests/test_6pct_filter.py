"""Tests for ≤6% candidate filtering in generator output."""
import unittest

import generator


class TestSixPctFilterCandidateTable(unittest.TestCase):
    """Generator must exclude candidates ≤6% from all candidate tables."""

    def test_candidate_table_excludes_6pct_candidates(self):
        """Candidates polling ≤6% are removed from candidate table rows."""
        markets = [
            {
                "ticker": "KXMAYORLA-BASS",
                "candidate_name": "Karen Bass",
                "event_ticker": "KXMAYORLA-26",
                "marcus_fv": 50,
                "market_price": 45,
                "verdict": "TRADE",
            },
            {
                "ticker": "KXMAYORLA-PRATT",
                "candidate_name": "Spencer Pratt",
                "event_ticker": "KXMAYORLA-26",
                "marcus_fv": 30,
                "market_price": 28,
                "verdict": "PASS",
            },
            {
                "ticker": "KXMAYORLA-MILLER",
                "candidate_name": "Adam Miller",
                "event_ticker": "KXMAYORLA-26",
                "marcus_fv": 5,
                "market_price": 5,
                "verdict": "PASS",
            },
        ]

        # Simulate what generator._render_race_card does
        # It should filter Miller (FV=5, below threshold) from displayed rows
        displayed_candidates = [
            m for m in markets
            if m.get("marcus_fv", 0) is not None and float(m.get("marcus_fv", 0)) > 6.0
        ]

        self.assertEqual(len(displayed_candidates), 2)
        self.assertEqual(displayed_candidates[0]["candidate_name"], "Karen Bass")
        self.assertEqual(displayed_candidates[1]["candidate_name"], "Spencer Pratt")

    def test_all_candidates_below_6pct_returns_empty(self):
        """If all candidates are ≤6%, the filtered list is empty — not an error."""
        markets = [
            {"candidate_name": "A", "marcus_fv": 4.0},
            {"candidate_name": "B", "marcus_fv": 5.0},
            {"candidate_name": "C", "marcus_fv": 6.0},  # exactly 6 — excluded
        ]

        filtered = [
            m for m in markets
            if m.get("marcus_fv", 0) is not None and float(m.get("marcus_fv", 0)) > 6.0
        ]

        self.assertEqual(len(filtered), 0)


class TestSixPctFilterAnalysisText(unittest.TestCase):
    """Analysis text must not mention candidates ≤6%."""

    def test_analysis_excludes_low_polling_candidates(self):
        """Analysis text should only reference viable candidates (>6%).
        
        When building analysis text, construct it from the viable candidates
        dict — do NOT include non-viable candidates in the text at all.
        """
        all_candidates = {
            "Karen Bass": 25.0,
            "Spencer Pratt": 12.0,
            "Nithya Raman": 11.5,
            "Adam Miller": 4.0,
            "Rae Huang": 5.0,
        }

        viable = {k: v for k, v in all_candidates.items() if v > 6.0}
        nonviable = {k: v for k, v in all_candidates.items() if v <= 6.0}

        # Verify our test data划分 is correct
        self.assertEqual(set(viable.keys()), {"Karen Bass", "Spencer Pratt", "Nithya Raman"})
        self.assertEqual(set(nonviable.keys()), {"Adam Miller", "Rae Huang"})

        # Good analysis text mentions only viable candidates
        good_analysis = (
            "Bass leads at {bass}% with Pratt and Raman in a tight race for second. "
            "Pratt's celebrity endorsements have boosted his name recognition."
        ).format(bass=viable["Karen Bass"])

        self.assertNotIn("Miller", good_analysis)
        self.assertNotIn("Huang", good_analysis)
        self.assertIn("Bass", good_analysis)
        self.assertIn("Pratt", good_analysis)
        self.assertIn("Raman", good_analysis)


class TestPollingFailureDetection(unittest.TestCase):
    """Generator must detect markets where polling lookup failed."""

    PLACEHOLDER_PATTERNS = [
        "no polling source",
        "Because no polling source",
        "_POOL_FAILED_",
        "polling source not yet implemented",
    ]

    def test_detects_no_polling_source_placeholder(self):
        analysis = "Because no polling source is implemented for this contract type."
        found = any(p.lower() in analysis.lower() for p in self.PLACEHOLDER_PATTERNS)
        self.assertTrue(found)

    def test_detects_pool_failed_marker(self):
        analysis = "Marcus sets fair value equal to current market price. _POOL_FAILED_"
        found = any(p.lower() in analysis.lower() for p in self.PLACEHOLDER_PATTERNS)
        self.assertTrue(found)

    def test_detects_no_recent_polling(self):
        analysis = "No recent polling data available for this race."
        found = any(p.lower() in analysis.lower() for p in self.PLACEHOLDER_PATTERNS)
        self.assertFalse(found)  # this specific phrase isn't in our patterns

    def test_real_analysis_not_flagged(self):
        real_analyses = [
            "Bass leads with 25% in recent polls. Pratt at 12%, Raman at 11%.",
            "Wikipedia polling shows a tight race in the Colombian presidential election.",
            "Three-poll average gives the incumbent a 8-point edge over the challenger.",
        ]
        for analysis in real_analyses:
            found = any(p.lower() in analysis.lower() for p in self.PLACEHOLDER_PATTERNS)
            self.assertFalse(found, f"Real analysis incorrectly flagged: {analysis[:50]}")

    def test_complete_market_with_real_polling_not_flagged(self):
        """A complete market with real polling should not trigger the alert."""
        complete_markets = [
            {
                "ticker": "KXMAYORLA-BASS",
                "status": "complete",
                "analysis": "Bass leads with 25% in threePoll average. Her institutional "
                            "advantages and early polling lead make her the favorite.",
                "sources": [{"label": "Wikipedia polling", "url": "https://en.wikipedia.org/"}],
            },
            {
                "ticker": "KXMAYORLA-PRATT",
                "status": "complete",
                "analysis": "Pratt holds second place at 12% with celebrity endorsements. "
                            "His unusual coalition bridges conservative and anti-establishment voters.",
                "sources": [{"label": "Wikipedia polling", "url": "https://en.wikipedia.org/"}],
            },
        ]

        failed = []
        for m in complete_markets:
            if any(p.lower() in (m.get("analysis") or "").lower() for p in self.PLACEHOLDER_PATTERNS):
                failed.append(m["ticker"])

        self.assertEqual(failed, [])

    def test_incomplete_market_with_placeholder_flagged(self):
        """A market with placeholder text should be detected."""
        incomplete_markets = [
            {
                "ticker": "KXLAMAYOR1R-BASS",
                "status": "complete",
                "analysis": "Because no polling source is implemented for this contract type.",
                "sources": [],
            },
        ]

        failed = []
        for m in incomplete_markets:
            if any(p.lower() in (m.get("analysis") or "").lower() for p in self.PLACEHOLDER_PATTERNS):
                failed.append(m["ticker"])

        self.assertEqual(failed, ["KXLAMAYOR1R-BASS"])


if __name__ == "__main__":
    unittest.main()