"""Round-trip test for embed_attachment: a faithfully-copied MCAP keeps its messages and
gains the attachment. Skipped if the mcap library isn't installed."""
import pytest

mcap = pytest.importorskip("mcap")
from mcap.reader import make_reader  # noqa: E402
from mcap.writer import Writer  # noqa: E402

from robotbase.recording import embed_attachment  # noqa: E402


def _write_minimal_mcap(path):
    with open(path, "wb") as f:
        w = Writer(f)
        w.start()
        sid = w.register_schema("std_msgs/msg/String", "ros2msg", b"string data")
        cid = w.register_channel("/chatter", "cdr", sid)
        for i in range(3):
            w.add_message(cid, log_time=i, data=b"\x00\x01\x02", publish_time=i, sequence=i)
        w.finish()


def test_embed_attachment_preserves_messages_and_adds_attachment(tmp_path):
    path = str(tmp_path / "episode.mcap")
    _write_minimal_mcap(path)

    assert embed_attachment(path, "episode.json", b'{"scenario": "demo"}') is True

    with open(path, "rb") as f:
        reader = make_reader(f)
        # messages survive the copy
        topics = {ch.topic for _s, ch, _m in reader.iter_messages()}
        assert topics == {"/chatter"}
        # the attachment is present with our payload
        atts = {a.name: a.data for a in reader.iter_attachments()}
        assert atts["episode.json"] == b'{"scenario": "demo"}'


def test_embed_attachment_missing_file_returns_false(tmp_path):
    assert embed_attachment(str(tmp_path / "nope.mcap"), "x", b"y") is False
