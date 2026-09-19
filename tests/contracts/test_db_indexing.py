"""PER-004: every foreign-key column must be covered by an index once the proposed indexes are applied.

Postgres does not index the referencing side of a foreign key, so an unindexed FK means a sequential scan on every
join and cascade. This reads the schema files and supabase_performance_indexes.sql and fails if a table gains an FK
column that neither an existing index, a UNIQUE/PRIMARY KEY, nor the proposal covers.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ["supabase_schema.sql", "supabase_response_validation_schema.sql", "supabase_pairwise_feedback_schema.sql"]
PROPOSAL = "supabase_performance_indexes.sql"


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def strip_comments(sql):
    return "\n".join(line.split("--", 1)[0] for line in sql.splitlines())


def foreign_keys():
    """(table, column) for every column declared `... REFERENCES ...` inside a CREATE TABLE."""
    found = []
    for name in SCHEMAS:
        sql = strip_comments(read(name))
        for m in re.finditer(r"CREATE TABLE (?:IF NOT EXISTS )?public\.(\w+)\s*\((.*?)\n\);", sql, re.S | re.I):
            table, body = m.group(1), m.group(2)
            for line in body.splitlines():
                col = re.match(r"\s*(\w+)\s+[\w\(\)\s,]*?\bREFERENCES\b", line, re.I)
                # A primary-key column is already indexed (users.id -> auth.users).
                if col and not re.search(r"PRIMARY KEY", line, re.I):
                    found.append((table, col.group(1)))
    return found


def indexed_columns(files):
    """(table, leading column) covered by CREATE INDEX or an inline/table-level UNIQUE."""
    covered = set()
    for name in files:
        sql = strip_comments(read(name))
        for m in re.finditer(r"CREATE (?:UNIQUE )?INDEX (?:IF NOT EXISTS )?\w+\s+ON\s+public\.(\w+)\s*\(\s*(\w+)", sql, re.I):
            covered.add((m.group(1), m.group(2)))
        for t in re.finditer(r"CREATE TABLE (?:IF NOT EXISTS )?public\.(\w+)\s*\((.*?)\n\);", sql, re.S | re.I):
            for u in re.finditer(r"UNIQUE\s*\(\s*(\w+)", t.group(2), re.I):
                covered.add((t.group(1), u.group(1)))
    return covered


def test_the_parser_finds_the_known_foreign_keys():
    fks = set(foreign_keys())
    assert ("resolutions", "ticket_id") in fks
    assert ("tickets", "user_id") in fks
    assert ("evaluation_score_overrides", "evaluation_id") in fks
    assert len(fks) >= 12


@pytest.mark.parametrize("table,column", foreign_keys())
def test_every_foreign_key_is_indexed_once_the_proposal_is_applied(table, column):
    covered = indexed_columns(SCHEMAS + [PROPOSAL])
    assert (table, column) in covered, f"{table}.{column} is a foreign key with no index"


def test_the_proposal_is_idempotent_and_non_destructive():
    sql = strip_comments(read(PROPOSAL))
    for stmt in re.findall(r"CREATE (?:UNIQUE )?INDEX [^\n;]*", sql, re.I):
        assert "IF NOT EXISTS" in stmt.upper(), stmt
    assert not re.search(r"\b(DROP TABLE|DROP COLUMN|TRUNCATE|DELETE FROM|ALTER TABLE)\b", sql, re.I)


def test_slow_query_view_is_not_readable_by_customers():
    sql = strip_comments(read(PROPOSAL))
    assert re.search(r"REVOKE ALL ON public\.slow_queries FROM[^;]*\bauthenticated\b", sql, re.I)
    assert not re.search(r"GRANT[^;]*slow_queries[^;]*\b(anon|authenticated|PUBLIC)\b", sql, re.I)
    assert "500" in sql  # the PER-004 threshold


def test_user_management_migration_is_covered_by_the_same_rules():
    """supabase_user_management.sql adds FK columns of its own: they must be indexed, and it must be idempotent."""
    sql = strip_comments(read("supabase_user_management.sql"))
    for column in ("target_user_id", "actor_id"):
        assert re.search(rf"CREATE INDEX IF NOT EXISTS \w+\s+ON public\.admin_audit_log \({column}", sql), column
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert not re.search(r"CREATE POLICY", sql)  # service role only - no customer-facing access
    assert "IF NOT EXISTS" in sql.split("ADD COLUMN", 1)[1].split("\n")[0].upper() or "ADD COLUMN IF NOT EXISTS" in sql.upper()
    assert not re.search(r"\b(DROP|TRUNCATE|DELETE FROM)\b", sql, re.I)
