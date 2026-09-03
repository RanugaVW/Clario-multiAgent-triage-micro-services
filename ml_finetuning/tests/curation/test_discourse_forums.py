from src.curation.sources import discourse_forums


def _topic():
    return {"id": 555, "slug": "account-suspended"}


def _thread_with_staff_reply():
    return {
        "post_stream": {
            "posts": [
                {"post_number": 1, "cooked": "<p>My account was suspended, why?</p>", "staff": False},
                {
                    "post_number": 2,
                    "cooked": "<p>Your account was suspended for a policy violation. Please contact support to appeal.</p>",
                    "staff": True,
                },
            ]
        },
        "slug": "account-suspended",
    }


def test_fetch_returns_example_from_staff_post(monkeypatch):
    monkeypatch.setattr(discourse_forums, "_HOSTS", ("community.udemy.com",))
    monkeypatch.setattr(discourse_forums, "_search_topics", lambda host, keyword: [_topic()])
    monkeypatch.setattr(discourse_forums, "_fetch_thread", lambda host, topic_id: _thread_with_staff_reply())

    results = discourse_forums.fetch("Account Suspension", ["suspended"], limit=5)

    assert len(results) == 1
    assert results[0].issue_text == "My account was suspended, why?"
    assert results[0].resolution_text == "Your account was suspended for a policy violation. Please contact support to appeal."
    assert results[0].responder_role == "staff"
    assert results[0].source_url == "https://community.udemy.com/t/account-suspended/555"


def test_fetch_skips_thread_with_no_staff_reply(monkeypatch):
    thread = _thread_with_staff_reply()
    thread["post_stream"]["posts"][1]["staff"] = False

    monkeypatch.setattr(discourse_forums, "_HOSTS", ("community.udemy.com",))
    monkeypatch.setattr(discourse_forums, "_search_topics", lambda host, keyword: [_topic()])
    monkeypatch.setattr(discourse_forums, "_fetch_thread", lambda host, topic_id: thread)

    assert discourse_forums.fetch("Account Suspension", ["suspended"], limit=5) == []


def test_fetch_stops_once_limit_reached(monkeypatch):
    monkeypatch.setattr(discourse_forums, "_HOSTS", ("community.udemy.com", "discuss.openedx.org"))
    monkeypatch.setattr(discourse_forums, "_search_topics", lambda host, keyword: [_topic()])
    monkeypatch.setattr(discourse_forums, "_fetch_thread", lambda host, topic_id: _thread_with_staff_reply())

    results = discourse_forums.fetch("Account Suspension", ["suspended", "banned"], limit=1)

    assert len(results) == 1


def test_fetch_returns_empty_list_for_empty_keywords():
    assert discourse_forums.fetch("Account Suspension", [], limit=5) == []


def test_fetch_continues_past_search_error(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise discourse_forums.httpx.HTTPError("boom")

    monkeypatch.setattr(discourse_forums, "_HOSTS", ("community.udemy.com",))
    monkeypatch.setattr(discourse_forums, "_search_topics", _raise)

    assert discourse_forums.fetch("Account Suspension", ["suspended"], limit=5) == []
