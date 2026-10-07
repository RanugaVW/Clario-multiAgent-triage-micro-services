"""Fake supabase client for job tests: any query-builder chain returns the rows."""


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self.calls = []

    def __getattr__(self, name):
        def chain(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self
        return chain

    def execute(self):
        return FakeResult(self._rows)


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.queries = {}

    def table(self, name):
        query = FakeQuery(self.tables.get(name, []))
        self.queries[name] = query
        return query
