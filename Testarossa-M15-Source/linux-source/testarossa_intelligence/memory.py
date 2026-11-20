"""Bounded JSON skill and experience memory; never stores executable code."""
import json
import os
import re
import tempfile
import time
import uuid

_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
_MAX_FILE = 2 * 1024 * 1024
_MAX_SKILLS = 500
_MAX_EXPERIENCES = 2000


class JsonStore:
    def __init__(self, directory):
        self.directory = os.path.abspath(directory)
        os.makedirs(self.directory, mode=0o700, exist_ok=True)
        if os.path.islink(self.directory):
            raise ValueError("memory_directory_symlink")

    def _path(self, name):
        if type(name) is not str or not _NAME.fullmatch(name):
            raise ValueError("invalid_memory_name")
        return os.path.join(self.directory, name + ".json")

    def load(self, name, default):
        path = self._path(name)
        try:
            if os.path.islink(path):
                raise ValueError("memory_file_symlink")
            if os.path.getsize(path) > _MAX_FILE:
                raise ValueError("memory_file_too_large")
            with open(path, "r", encoding="utf-8") as stream:
                value = json.load(stream)
            if type(value) is not dict:
                raise ValueError("invalid_memory_document")
            return value
        except FileNotFoundError:
            return default

    def save(self, name, value):
        path = self._path(name)
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
        if len(raw) > _MAX_FILE:
            raise ValueError("memory_file_too_large")
        fd, temp_path = tempfile.mkstemp(prefix=".memory-", dir=self.directory)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class SkillLibrary:
    def __init__(self, directory):
        self.store = JsonStore(directory)

    def add(self, name, title, purpose, prerequisites, steps, verification, tags=()):
        if type(name) is not str or not _NAME.fullmatch(name):
            raise ValueError("invalid_skill_name")
        if type(title) is not str or not 1 <= len(title) <= 120:
            raise ValueError("invalid_skill_title")
        if type(purpose) is not str or not 1 <= len(purpose) <= 500:
            raise ValueError("invalid_skill_purpose")
        for seq, limit in ((prerequisites, 20), (steps, 40),
                           (verification, 20), (tags, 20)):
            if type(seq) not in (list, tuple) or len(seq) > limit:
                raise ValueError("invalid_skill_sequence")
            if any(type(x) is not str or not x.strip() or len(x) > 500 for x in seq):
                raise ValueError("invalid_skill_entry")
        data = self.store.load("skills", {"items": []})
        items = data.get("items")
        if type(items) is not list:
            raise ValueError("invalid_skill_store")
        existing = next((x for x in items if x.get("name") == name), None)
        skill = {
            "name": name, "title": title, "purpose": purpose,
            "prerequisites": list(prerequisites), "steps": list(steps),
            "verification": list(verification), "tags": list(tags),
            "updated_at": int(time.time()),
            "uses": existing.get("uses", 0) if existing else 0,
        }
        if existing:
            items[items.index(existing)] = skill
        else:
            if len(items) >= _MAX_SKILLS:
                raise ValueError("skill_limit")
            items.append(skill)
        self.store.save("skills", {"items": items})
        return skill

    def search(self, query, limit=10):
        if type(query) is not str or not query.strip():
            raise ValueError("invalid_search")
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("invalid_limit")
        terms = set(query.lower().split())
        items = self.store.load("skills", {"items": []}).get("items", [])
        ranked = []
        for skill in items:
            haystack = " ".join([
                skill.get("title", ""), skill.get("purpose", ""),
                " ".join(skill.get("tags", []))
            ]).lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                ranked.append((score, skill))
        ranked.sort(key=lambda pair: (-pair[0], pair[1]["name"]))
        return [skill for _, skill in ranked[:limit]]


class ExperienceLog:
    def __init__(self, directory):
        self.store = JsonStore(directory)

    def record(self, goal, stage, outcome, summary, error_code=None):
        if outcome not in {"success", "failure", "blocked", "cancelled"}:
            raise ValueError("invalid_outcome")
        for key, value, limit in (
            ("goal", goal, 500), ("stage", stage, 80), ("summary", summary, 1000)
        ):
            if type(value) is not str or not value.strip() or len(value) > limit:
                raise ValueError("invalid_" + key)
        if error_code is not None and (
            type(error_code) is not str or len(error_code) > 80
        ):
            raise ValueError("invalid_error_code")
        data = self.store.load("experiences", {"items": []})
        items = data.get("items")
        if type(items) is not list:
            raise ValueError("invalid_experience_store")
        entry = {
            "id": str(uuid.uuid4()), "timestamp": int(time.time()),
            "goal": goal, "stage": stage, "outcome": outcome,
            "summary": summary, "error_code": error_code,
        }
        items.append(entry)
        self.store.save("experiences", {"items": items[-_MAX_EXPERIENCES:]})
        return entry

    def recent(self, limit=20):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("invalid_limit")
        items = self.store.load("experiences", {"items": []}).get("items", [])
        return list(reversed(items[-limit:]))
