"""Rendering backends over the semantic IR (P4).

Each backend turns a ``RobotModel`` (and its ``RigidBody``/``Joint``/``Sensor`` parts) into a
concrete robot-description format — ``urdf`` today, ``mjcf`` as the proof that a second target is an
additive file, not a rewrite. The semantic types in ``robotbase.robotspec.semantic`` are the single
source of truth; nothing here holds robotics semantics, only formatting.
"""
