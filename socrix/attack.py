"""Offline MITRE ATT&CK v19.2 reference (distilled from MITRE's STIX 2.1 bundle).

Built by scripts/build_attack_ref.py from mitre-attack/attack-stix-data enterprise-attack-19.2.json.
Uses the v18+ data model: technique <- detects - Detection Strategy -> Analytics -> Data Components.
"""
from __future__ import annotations
import json
from functools import lru_cache
from . import config as C


@lru_cache(maxsize=1)
def ref() -> dict:
    with open(C.ATTACK_REF) as f:
        return json.load(f)


@lru_cache(maxsize=1)
def technique_index() -> dict[str, dict]:
    return {t["id"]: t for t in ref()["techniques"]}


@lru_cache(maxsize=1)
def tactic_names() -> dict[str, str]:
    return {t["id"]: t["name"] for t in ref()["tactics"]}


def tactics_for(technique_id: str | None) -> list[str]:
    if not technique_id:
        return []
    base = technique_id.split(".")[0]
    t = technique_index().get(technique_id) or technique_index().get(base)
    return t["tactics"] if t else []


def version() -> str:
    return ref()["attack_version"]
