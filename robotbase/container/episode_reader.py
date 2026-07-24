#!/usr/bin/env python3
"""Container-side MCAP episode reader for `robotbase episode ...` (Phase 2).

Runs *inside* the ROS container, where `rosbag2_py` and the message types are available
(the host venv has neither). It reads a run's `episode.mcap` and emits **bounded, structured
JSON** to stdout — a summary, a derived event timeline, or a downsampled slice of one topic
around a time of interest — never a raw frame dump. `robotbase.runtime` materializes this
file into the mounted `.robotbase/` and invokes it; it is not meant to be run by hand.

ROS imports are function-local on purpose: the module stays importable on a plain host (no
ROS) so the pure helpers below can be unit-tested.
"""
from __future__ import annotations

import argparse
import json
import sys

COLLISION_RANGE_M = 0.12
MAX_SAMPLES = 40


# ---- pure helpers (host-importable; unit-tested) ----------------------------

def downsample(items: list, max_samples: int) -> list:
    """Evenly stride *items* down to at most *max_samples*, preserving ends."""
    if max_samples <= 0 or len(items) <= max_samples:
        return items
    stride = len(items) / max_samples
    return [items[int(i * stride)] for i in range(max_samples)]


def compact(type_name: str, msg) -> dict:
    """Reduce a deserialized message to a small, bounded dict.

    Per-type formatters for the topics we ship; a truncated generic fallback otherwise.
    Crucially, images never return pixel data — only dimensions/encoding.
    """
    if type_name.endswith("LaserScan"):
        valid = [r for r in msg.ranges if msg.range_min <= r <= msg.range_max]
        return {
            "min_range": round(min(valid), 3) if valid else None,
            "num_valid": len(valid),
            "num_total": len(msg.ranges),
        }
    if type_name.endswith("Odometry"):
        p = msg.pose.pose.position
        tw = msg.twist.twist
        return {"x": round(p.x, 3), "y": round(p.y, 3),
                "vx": round(tw.linear.x, 3), "wz": round(tw.angular.z, 3)}
    if type_name.endswith("Twist"):
        return {"vx": round(msg.linear.x, 3), "wz": round(msg.angular.z, 3)}
    if type_name.endswith("Image"):
        return {"width": msg.width, "height": msg.height, "encoding": msg.encoding}
    # Generic fallback: a truncated dict so an unknown type is still legible but bounded.
    from rosidl_runtime_py import message_to_ordereddict

    return {"summary": json.dumps(message_to_ordereddict(msg), default=str)[:400]}


# ---- MCAP access (container-only) -------------------------------------------

def _open(path: str):
    import rosbag2_py

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=path, storage_id="mcap"),
        rosbag2_py.ConverterOptions("", ""),
    )
    return reader


def _topic_types(reader) -> dict:
    return {t.name: t.type for t in reader.get_all_topics_and_types()}


def summary(path: str) -> dict:
    reader = _open(path)
    types = _topic_types(reader)
    counts: dict[str, int] = {}
    t0 = t1 = None
    while reader.has_next():
        topic, _data, t = reader.read_next()
        counts[topic] = counts.get(topic, 0) + 1
        t0 = t if t0 is None else t0
        t1 = t
    duration = (t1 - t0) / 1e9 if t0 is not None else 0.0
    return {
        "duration_seconds": round(duration, 3),
        "message_count": sum(counts.values()),
        "topics": [
            {"name": n, "type": types.get(n, ""), "count": counts[n]} for n in sorted(counts)
        ],
    }


def events(path: str) -> dict:
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    reader = _open(path)
    types = _topic_types(reader)
    scan_cls = get_message(types["/scan"]) if "/scan" in types else None
    t0 = None
    found: list[dict] = []
    collided = False
    while reader.has_next():
        topic, data, t = reader.read_next()
        t0 = t if t0 is None else t0
        if topic == "/scan" and scan_cls and not collided:
            msg = deserialize_message(data, scan_cls)
            valid = [r for r in msg.ranges if msg.range_min <= r <= msg.range_max]
            if valid and min(valid) < COLLISION_RANGE_M:
                found.append({
                    "type": "collision",
                    "timestamp": round((t - t0) / 1e9, 3),
                    "detail": f"minimum LiDAR range dropped below {COLLISION_RANGE_M} m",
                })
                collided = True
    return {"events": found}


def query(path, topic, around, window, max_samples) -> dict:
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    reader = _open(path)
    types = _topic_types(reader)
    if topic not in types:
        return {"error": f"topic {topic!r} not in episode", "topics": sorted(types)}
    cls = get_message(types[topic])
    lo = around - window if around is not None else None
    hi = around + window if around is not None else None
    t0 = None
    collected: list[tuple[float, object]] = []
    while reader.has_next():
        name, data, t = reader.read_next()
        t0 = t if t0 is None else t0
        if name != topic:
            continue
        rel = (t - t0) / 1e9
        if lo is not None and (rel < lo or rel > hi):
            continue
        collected.append((rel, deserialize_message(data, cls)))
    collected = downsample(collected, max_samples)
    return {
        "topic": topic,
        "type": types[topic],
        "window": None if around is None else [round(lo, 3), round(hi, 3)],
        "count": len(collected),
        "samples": [{"t": round(rel, 3), **compact(types[topic], m)} for rel, m in collected],
    }


def main() -> None:
    ap = argparse.ArgumentParser(prog="episode_reader")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("summary", "events"):
        p = sub.add_parser(name)
        p.add_argument("mcap")
    q = sub.add_parser("query")
    q.add_argument("mcap")
    q.add_argument("--topic", required=True)
    q.add_argument("--around", type=float, default=None)
    q.add_argument("--window", type=float, default=2.0)
    q.add_argument("--max", type=int, default=MAX_SAMPLES, dest="max_samples")
    args = ap.parse_args()

    if args.cmd == "summary":
        out = summary(args.mcap)
    elif args.cmd == "events":
        out = events(args.mcap)
    else:
        out = query(args.mcap, args.topic, args.around, args.window, args.max_samples)
    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
