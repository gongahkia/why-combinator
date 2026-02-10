"""Tests for EventBus: subscribe/publish, subscribe_all, handler exceptions."""
from why_combinator.events import EventBus


def test_subscribe_and_publish():
    bus = EventBus()
    received = []
    bus.subscribe("test_event", lambda e: received.append(e))
    bus.publish("test_event", {"data": 42}, timestamp=1.0)
    assert len(received) == 1
    assert received[0].payload["data"] == 42


def test_subscribe_all():
    bus = EventBus()
    received = []
    bus.subscribe_all(lambda e: received.append(e))
    bus.publish("event_a", {"x": 1}, timestamp=1.0)
    bus.publish("event_b", {"y": 2}, timestamp=2.0)
    assert len(received) == 2
    assert received[0].type == "event_a"
    assert received[1].type == "event_b"


def test_handler_exception_does_not_crash():
    bus = EventBus()
    received = []

    def bad_handler(e):
        raise RuntimeError("oops")

    def good_handler(e):
        received.append(e)

    bus.subscribe("test", bad_handler)
    bus.subscribe("test", good_handler)
    bus.publish("test", {"ok": True}, timestamp=1.0)
    # Good handler should still fire even if bad one raises
    assert len(received) == 1


def test_no_subscribers():
    bus = EventBus()
    # Should not raise
    bus.publish("nobody_listening", {"data": 1}, timestamp=1.0)
