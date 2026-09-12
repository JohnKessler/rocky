"""Rocky's memory."""

from __future__ import annotations

import pytest
from rocky.brain.memory import Memory


@pytest.fixture
def memory(tmp_path):
    m = Memory(str(tmp_path / "m.db"), max_facts=6)
    yield m
    m.close()


class TestFacts:
    def test_remember_and_recall(self, memory: Memory):
        memory.remember("John takes his tea strong", "preference")
        assert [f.text for f in memory.recall("tea")] == ["John takes his tea strong"]

    def test_duplicates_are_not_stored_twice(self, memory: Memory):
        a = memory.remember("The workshop is in the garage")
        b = memory.remember("the workshop IS in the GARAGE")
        assert a.id == b.id
        assert len(memory.all_facts()) == 1

    def test_empty_text_is_ignored(self, memory: Memory):
        assert memory.remember("   ") is None

    def test_recall_survives_punctuation(self, memory: Memory):
        """Search text comes from speech, so it arrives full of apostrophes
        and question marks that FTS5 would otherwise treat as operators."""
        memory.remember("John's daughter is called Mira")
        assert memory.recall("what's john's daughter called?")

    def test_recall_with_no_query_returns_the_most_used(self, memory: Memory):
        memory.remember("one")
        memory.remember("two")
        for _ in range(3):
            memory.recall("two")
        assert memory.recall("")[0].text == "two"

    def test_forget(self, memory: Memory):
        fact = memory.remember("temporary")
        assert memory.forget(fact.id) is True
        assert memory.forget(fact.id) is False
        assert memory.all_facts() == []

    def test_pruning_keeps_the_useful_ones(self, memory: Memory):
        keeper = memory.remember("this one matters")
        for _ in range(5):
            memory.recall("matters")
        for i in range(10):
            memory.remember(f"filler {i}")
        assert memory.stats()["facts"] == 6
        assert any(f.id == keeper.id for f in memory.all_facts())

    def test_long_text_is_truncated_not_rejected(self, memory: Memory):
        fact = memory.remember("x" * 900)
        assert 0 < len(fact.text) <= 400


class TestTranscript:
    def test_turns_come_back_in_order(self, memory: Memory):
        memory.log_turn("user", "hello")
        memory.log_turn("rocky", "Good, good, good.")
        turns = memory.recent_turns()
        assert [t["role"] for t in turns] == ["user", "rocky"]

    def test_limit_returns_the_most_recent(self, memory: Memory):
        for i in range(10):
            memory.log_turn("user", f"line {i}")
        turns = memory.recent_turns(limit=3)
        assert [t["text"] for t in turns] == ["line 7", "line 8", "line 9"]


def test_memory_survives_a_reopen(tmp_path):
    path = str(tmp_path / "m.db")
    first = Memory(path)
    first.remember("Rocky lives on the desk by the window")
    first.close()

    second = Memory(path)
    assert second.recall("window")
    second.close()
