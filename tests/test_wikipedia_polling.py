"""Tests for Wikipedia polling lookup."""
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import engine
from engine import (
    WikipediaPoller,
    _wikipedia_url,
    _normalize_candidate_name,
    _filter_6pct,
    _parse_wiki_poll_table_row,
    _scrape_wiki_polls,
    SIX_PCT_THRESHOLD,
)


class TestWikipediaUrl(unittest.TestCase):
    def test_los_angeles_mayoral(self):
        url = _wikipedia_url("Los Angeles Mayoral Primary", "2026-06-02")
        self.assertEqual(url, "https://en.wikipedia.org/wiki/2026_Los_Angeles_mayoral_election")

    def test_los_angeles_mayoral_case_insensitive(self):
        url = _wikipedia_url("LA MAYOR FIRST ROUND", "2026-06-02")
        self.assertEqual(url, "https://en.wikipedia.org/wiki/2026_Los_Angeles_mayoral_election")

    def test_armenia_parliamentary(self):
        url = _wikipedia_url("2026 Armenian Parliamentary Election", "2026-06-07")
        self.assertEqual(url, "https://en.wikipedia.org/wiki/2026_Armenian_parliamentary_election")

    def test_colombia_presidential(self):
        url = _wikipedia_url("Colombian Presidential", "2026-05-31")
        self.assertEqual(url, "https://en.wikipedia.org/wiki/2026_Colombian_presidential_election")

    def test_no_event_date_returns_none(self):
        self.assertIsNone(_wikipedia_url("Los Angeles Mayoral", None))

    def test_unknown_race_returns_none(self):
        self.assertIsNone(_wikipedia_url("Australian Senate", "2026-07-04"))


class TestNormalizeCandidateName(unittest.TestCase):
    def test_full_names(self):
        self.assertEqual(_normalize_candidate_name("Karen Bass"), "Karen Bass")
        self.assertEqual(_normalize_candidate_name("Spencer Pratt"), "Spencer Pratt")
        self.assertEqual(_normalize_candidate_name("Nithya Raman"), "Nithya Raman")

    def test_aliases(self):
        self.assertEqual(_normalize_candidate_name("bass"), "Karen Bass")
        self.assertEqual(_normalize_candidate_name("pratt"), "Spencer Pratt")
        self.assertEqual(_normalize_candidate_name("raman"), "Nithya Raman")

    def test_unknown_returns_stripped(self):
        self.assertEqual(_normalize_candidate_name("  Some Unknown Candidate  "), "Some Unknown Candidate")

    def test_empty_returns_empty(self):
        self.assertEqual(_normalize_candidate_name(""), "")


class TestFilter6Pct(unittest.TestCase):
    def test_excludes_6_percent_exactly(self):
        # Exactly 6.0 should be excluded (> not >=)
        polls = {"Candidate": 6.0}
        result = _filter_6pct(polls)
        self.assertEqual(result, {})

    def test_excludes_below_6_percent(self):
        polls = {"Miller": 4.0, "Huang": 5.0, "Bass": 25.0}
        result = _filter_6pct(polls)
        self.assertEqual(result, {"Bass": 25.0})

    def test_keeps_above_6_percent(self):
        polls = {"Bass": 25.0, "Pratt": 6.1, "Raman": 11.5}
        result = _filter_6pct(polls)
        self.assertEqual(result, {"Bass": 25.0, "Pratt": 6.1, "Raman": 11.5})

    def test_empty_input_returns_empty(self):
        self.assertEqual(_filter_6pct({}), {})

    def test_all_below_6_returns_empty(self):
        polls = {"A": 3.0, "B": 4.0, "C": 5.9}
        result = _filter_6pct(polls)
        self.assertEqual(result, {})


class TestParseWikiPollTableRow(unittest.TestCase):
    def test_bold_candidate_with_pct(self):
        # Simulate a Wikipedia table row with bold candidate name and % value
        row = "'''Karen Bass'''   25%   26%   24%"
        name, pct = _parse_wiki_poll_table_row(row)
        self.assertEqual(name, "Karen Bass")
        self.assertEqual(pct, 24.0)  # last value = most recent

    def test_no_bold_name_returns_none(self):
        row = "Some header row without bold"
        name, pct = _parse_wiki_poll_table_row(row)
        self.assertIsNone(name)

    def test_bold_name_no_pct_returns_none(self):
        """Bold name present but no percentage in row → both are None."""
        row = "'''Karen Bass'''"
        name, pct = _parse_wiki_poll_table_row(row)
        # No percentage data in this row → neither name nor pct is returned
        self.assertIsNone(name)
        self.assertIsNone(pct)


class TestWikipediaPollerCache(unittest.TestCase):
    """WikipediaPoller caches results within a run."""

    def test_cache_returns_same_result(self):
        poller = WikipediaPoller()

        # Manually inject a result for testing
        cache_key = ("Los Angeles Mayoral Primary", ("Karen Bass",))
        poller._cache[cache_key] = {"Karen Bass": 25.0}

        result = poller.poll("Los Angeles Mayoral Primary", "2026-06-02", ["Karen Bass"])
        self.assertEqual(result, {"Karen Bass": 25.0})


if __name__ == "__main__":
    unittest.main()