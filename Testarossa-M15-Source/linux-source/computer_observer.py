import hashlib
import hmac
import json
import math
import re
import secrets
import time
import urllib.request
from pathlib import Path

ENDPOINT = "http://172.30.50.1:8766/v1/inspect"
KEY_PATH = Path("/etc/jarvis-baby/windows-observer.key")
ALLOWED_OPERATIONS = frozenset({
    "workstation", "blender_status",
    "blender_scene_snapshot", "blender_project_snapshot"
})
MAX_RESPONSE = 8192
MAX_SCENE_RESPONSE = 1024 * 1024
MAX_PROJECT_RESPONSE = 1200 * 1024


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _text(value, maximum=255, nullable=False):
    if nullable and value is None:
        return
    if type(value) is not str or len(value) > maximum:
        raise ValueError("Invalid snapshot text")


def _integer(value, minimum=0, maximum=100_000_000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid snapshot integer")


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Invalid snapshot number")


def _vector(value):
    if type(value) is not list or len(value) != 3:
        raise ValueError("Invalid snapshot vector")
    for component in value:
        _number(component)


def _string_list(value, cap=500, item_length=255):
    if type(value) is not list or len(value) > cap:
        raise ValueError("Invalid snapshot string list")
    for item in value:
        _text(item, item_length)


def _validate_animation(animation):
    if animation is None:
        return
    fields = {
        "action", "keyframes", "keyframes_available", "layers", "slots"
    }
    if type(animation) is not dict or set(animation) != fields:
        raise ValueError("Invalid animation metadata")
    _text(animation["action"], nullable=True)
    if type(animation["keyframes_available"]) is not bool:
        raise ValueError("Invalid keyframe availability")
    if animation["keyframes"] is not None:
        _integer(animation["keyframes"], 0, 10_000_000)
    if animation["keyframes_available"] != (animation["keyframes"] is not None):
        raise ValueError("Inconsistent keyframe metadata")
    _integer(animation["layers"], 0, 100_000)
    _integer(animation["slots"], 0, 100_000)


def _validate_object(obj, project_global=False):
    if type(obj) is not dict:
        raise ValueError("Invalid scene object")

    base = {
        "name", "type", "collections", "location", "rotation_euler",
        "scale", "dimensions", "parent", "parent_type",
        "hidden_viewport", "hidden_render", "modifiers", "materials",
        "constraints", "animation"
    }
    expected = set(base)
    kind = obj.get("type")
    if kind == "MESH":
        expected.add("geometry")
    if kind == "ARMATURE":
        expected.add("armature")
    if project_global:
        expected.add("scenes")
    if set(obj) != expected:
        raise ValueError("Invalid object fields")

    _text(obj["name"])
    if type(kind) is not str or not re.fullmatch(r"[A-Z_]{1,32}", kind):
        raise ValueError("Invalid object type")

    _string_list(obj["collections"], 100)
    if project_global:
        _string_list(obj["scenes"], 50)

    for key in ("location", "rotation_euler", "scale", "dimensions"):
        _vector(obj[key])

    _text(obj["parent"], nullable=True)
    _text(obj["parent_type"], 50)

    for key in ("hidden_viewport", "hidden_render"):
        if type(obj[key]) is not bool:
            raise ValueError("Invalid object visibility")

    modifiers = obj["modifiers"]
    if type(modifiers) is not list or len(modifiers) > 100:
        raise ValueError("Invalid modifiers")
    for modifier in modifiers:
        if type(modifier) is not dict or set(modifier) != {"name", "type"}:
            raise ValueError("Invalid modifier")
        _text(modifier["name"])
        _text(modifier["type"], 100)

    _string_list(obj["materials"], 100)

    constraints = obj["constraints"]
    if type(constraints) is not list or len(constraints) > 100:
        raise ValueError("Invalid constraints")
    for constraint in constraints:
        if type(constraint) is not dict or set(constraint) != {
            "name", "type", "target"
        }:
            raise ValueError("Invalid constraint")
        _text(constraint["name"])
        _text(constraint["type"], 100)
        _text(constraint["target"], nullable=True)

    _validate_animation(obj["animation"])

    if kind == "MESH":
        geometry = obj["geometry"]
        if type(geometry) is not dict or set(geometry) != {
            "vertices", "edges", "polygons"
        }:
            raise ValueError("Invalid mesh geometry")
        for key in ("vertices", "edges", "polygons"):
            _integer(geometry[key])

    if kind == "ARMATURE":
        armature = obj["armature"]
        if type(armature) is not dict or set(armature) != {
            "bone_count", "bones", "bones_truncated"
        }:
            raise ValueError("Invalid armature metadata")
        _integer(armature["bone_count"], 0, 1_000_000)
        _string_list(armature["bones"], 300)
        if type(armature["bones_truncated"]) is not bool:
            raise ValueError("Invalid bone truncation flag")


def _validate_scene(result):
    required = {
        "schema_version", "captured_at", "blender_version",
        "scene", "summary", "objects", "read_only"
    }
    if type(result) is not dict or set(result) != required:
        raise ValueError("Invalid scene snapshot fields")
    if type(result["schema_version"]) is not int or result["schema_version"] != 1:
        raise ValueError("Unsupported scene schema")
    _number(result["captured_at"])
    _text(result["blender_version"], 100)
    if result["read_only"] is not True:
        raise ValueError("Scene snapshot is not read-only")

    scene = result["scene"]
    fields = {
        "name", "frame_current", "frame_start", "frame_end",
        "render_engine", "resolution_x", "resolution_y",
        "resolution_percentage", "camera", "active_object"
    }
    if type(scene) is not dict or set(scene) != fields:
        raise ValueError("Invalid scene metadata")
    _text(scene["name"], 200)
    _text(scene["render_engine"], 100)
    _text(scene["camera"], nullable=True)
    _text(scene["active_object"], nullable=True)
    for key in ("frame_current", "frame_start", "frame_end"):
        _integer(scene[key], -1_000_000, 1_000_000)
    for key in ("resolution_x", "resolution_y"):
        _integer(scene[key], 1, 100_000)
    _integer(scene["resolution_percentage"], 1, 1000)

    summary = result["summary"]
    summary_fields = {
        "object_count", "object_type_counts", "objects_truncated",
        "mesh_count", "armature_count", "camera_count", "light_count"
    }
    if type(summary) is not dict or set(summary) != summary_fields:
        raise ValueError("Invalid scene summary")
    for key in (
        "object_count", "mesh_count", "armature_count",
        "camera_count", "light_count"
    ):
        _integer(summary[key], 0, 100_000)
    if type(summary["objects_truncated"]) is not bool:
        raise ValueError("Invalid scene truncation flag")

    counts = summary["object_type_counts"]
    if type(counts) is not dict or len(counts) > 32:
        raise ValueError("Invalid object type counts")
    for key, value in counts.items():
        if type(key) is not str or not re.fullmatch(r"[A-Z_]{1,32}", key):
            raise ValueError("Invalid object type count key")
        _integer(value, 0, 100_000)

    objects = result["objects"]
    if type(objects) is not list or len(objects) > 500:
        raise ValueError("Invalid scene objects")
    names = set()
    for obj in objects:
        _validate_object(obj)
        if obj["name"] in names:
            raise ValueError("Duplicate object name")
        names.add(obj["name"])
    if len(objects) > summary["object_count"]:
        raise ValueError("Object list exceeds reported count")
    return result


def _validate_project_scene(scene):
    fields = {
        "name", "frame_current", "frame_start", "frame_end",
        "render_engine", "resolution_x", "resolution_y",
        "resolution_percentage", "camera", "active_object",
        "object_count", "objects", "objects_truncated"
    }
    if type(scene) is not dict or set(scene) != fields:
        raise ValueError("Invalid project scene")
    _text(scene["name"], 200)
    _text(scene["render_engine"], 100)
    _text(scene["camera"], nullable=True)
    _text(scene["active_object"], nullable=True)
    for key in ("frame_current", "frame_start", "frame_end"):
        _integer(scene[key], -1_000_000, 1_000_000)
    for key in ("resolution_x", "resolution_y"):
        _integer(scene[key], 1, 100_000)
    _integer(scene["resolution_percentage"], 1, 1000)
    _integer(scene["object_count"], 0, 100_000)
    if type(scene["objects_truncated"]) is not bool:
        raise ValueError("Invalid scene truncation flag")
    objects = scene["objects"]
    if type(objects) is not list or len(objects) > 500:
        raise ValueError("Invalid project scene objects")
    names = set()
    for obj in objects:
        _validate_object(obj)
        if obj["name"] in names:
            raise ValueError("Duplicate project scene object")
        names.add(obj["name"])
    if len(objects) > scene["object_count"]:
        raise ValueError("Project scene object overflow")


def _validate_project(result):
    fields = {
        "schema_version", "captured_at", "blender_version", "project",
        "scenes", "scenes_truncated", "collections",
        "collections_truncated", "materials", "materials_truncated",
        "actions", "actions_truncated", "objects", "objects_truncated",
        "summary", "read_only"
    }
    if type(result) is not dict or set(result) != fields:
        raise ValueError("Invalid project snapshot fields")
    if type(result["schema_version"]) is not int or result["schema_version"] != 3:
        raise ValueError("Unsupported project schema")
    _number(result["captured_at"])
    _text(result["blender_version"], 100)
    if result["read_only"] is not True:
        raise ValueError("Project snapshot is not read-only")

    project = result["project"]
    project_fields = {
        "filepath", "filename", "is_saved", "is_dirty",
        "scene_count", "collection_count", "material_count",
        "action_count", "object_count"
    }
    if type(project) is not dict or set(project) != project_fields:
        raise ValueError("Invalid project metadata")
    _text(project["filepath"], 2048)
    _text(project["filename"], 255, nullable=True)
    if type(project["is_saved"]) is not bool or type(project["is_dirty"]) is not bool:
        raise ValueError("Invalid project flags")
    for key in (
        "scene_count", "collection_count", "material_count",
        "action_count", "object_count"
    ):
        _integer(project[key], 0, 100_000)

    caps = {
        "scenes": 50, "collections": 500, "materials": 500,
        "actions": 500, "objects": 500
    }
    for key, cap in caps.items():
        if type(result[key]) is not list or len(result[key]) > cap:
            raise ValueError("Invalid project " + key)
    for key in (
        "scenes_truncated", "collections_truncated", "materials_truncated",
        "actions_truncated", "objects_truncated"
    ):
        if type(result[key]) is not bool:
            raise ValueError("Invalid project truncation flag")

    for scene in result["scenes"]:
        _validate_project_scene(scene)

    collection_fields = {
        "name", "parent", "children", "objects", "objects_truncated"
    }
    for item in result["collections"]:
        if type(item) is not dict or set(item) != collection_fields:
            raise ValueError("Invalid project collection")
        _text(item["name"])
        _text(item["parent"], nullable=True)
        _string_list(item["children"], 100)
        _string_list(item["objects"], 500)
        if type(item["objects_truncated"]) is not bool:
            raise ValueError("Invalid collection truncation flag")

    for item in result["materials"]:
        if type(item) is not dict or set(item) != {
            "name", "users", "use_nodes"
        }:
            raise ValueError("Invalid project material")
        _text(item["name"])
        _integer(item["users"])
        if type(item["use_nodes"]) is not bool:
            raise ValueError("Invalid material node flag")

    for item in result["actions"]:
        if type(item) is not dict or set(item) != {
            "name", "users", "layers", "slots", "keyframes",
            "keyframes_available"
        }:
            raise ValueError("Invalid project action")
        _text(item["name"])
        for key in ("users", "layers", "slots"):
            _integer(item[key])
        if type(item["keyframes_available"]) is not bool:
            raise ValueError("Invalid action keyframe flag")
        if item["keyframes"] is not None:
            _integer(item["keyframes"], 0, 10_000_000)
        if item["keyframes_available"] != (item["keyframes"] is not None):
            raise ValueError("Inconsistent action keyframe metadata")

    global_names = set()
    for obj in result["objects"]:
        _validate_object(obj, project_global=True)
        if obj["name"] in global_names:
            raise ValueError("Duplicate project object name")
        global_names.add(obj["name"])

    summary_fields = {
        "scene_count", "collection_count", "material_count",
        "action_count", "object_count", "mesh_count", "armature_count",
        "camera_count", "light_count", "objects_truncated"
    }
    summary = result["summary"]
    if type(summary) is not dict or set(summary) != summary_fields:
        raise ValueError("Invalid project summary")
    for key in summary_fields - {"objects_truncated"}:
        _integer(summary[key])
    if type(summary["objects_truncated"]) is not bool:
        raise ValueError("Invalid project summary flag")

    for key, source in (
        ("scene_count", "scenes"),
        ("collection_count", "collections"),
        ("material_count", "materials"),
        ("action_count", "actions"),
        ("object_count", "objects"),
    ):
        if summary[key] != project[key]:
            raise ValueError("Inconsistent project summary")
        if len(result[source]) > project[key]:
            raise ValueError("Project inventory exceeds reported count")
    return result


def validate_result(operation, result):
    if operation not in ALLOWED_OPERATIONS or type(result) is not dict:
        raise ValueError("Invalid observer result")

    if operation == "blender_scene_snapshot":
        return _validate_scene(result)
    if operation == "blender_project_snapshot":
        return _validate_project(result)

    if operation == "workstation":
        required = {"hostname", "os", "architecture", "processor", "python"}
        if set(result) != required:
            raise ValueError("Invalid workstation fields")
        for value in result.values():
            if type(value) is not str or not value or len(value) > 300:
                raise ValueError("Invalid workstation value")
        return result

    required = {"installed", "executable", "version", "version_error", "running"}
    if set(result) != required:
        raise ValueError("Invalid Blender status fields")
    if type(result["installed"]) is not bool or type(result["running"]) is not bool:
        raise ValueError("Invalid Blender status flags")
    if type(result["executable"]) is not str or len(result["executable"]) > 300:
        raise ValueError("Invalid Blender executable")
    for key in ("version", "version_error"):
        value = result[key]
        if value is not None and (type(value) is not str or len(value) > 300):
            raise ValueError("Invalid Blender status text")
    return result


def inspect_computer(operation):
    if type(operation) is not str or operation not in ALLOWED_OPERATIONS:
        raise ValueError("Unsupported computer-awareness operation")

    key_hex = KEY_PATH.read_text(encoding="ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{64}", key_hex):
        raise RuntimeError("Observer authentication key is invalid")
    key = bytes.fromhex(key_hex)

    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(32)
    body = json.dumps({"operation": operation}, separators=(",", ":")).encode()
    signed = timestamp.encode() + b"\n" + nonce.encode() + b"\n" + body
    signature = hmac.new(key, signed, hashlib.sha256).hexdigest()

    request = urllib.request.Request(
        ENDPOINT, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Jarvis-Timestamp": timestamp,
            "X-Jarvis-Nonce": nonce,
            "X-Jarvis-Signature": signature,
        },
    )
    if operation == "blender_project_snapshot":
        limit = MAX_PROJECT_RESPONSE
    elif operation == "blender_scene_snapshot":
        limit = MAX_SCENE_RESPONSE
    else:
        limit = MAX_RESPONSE

    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(limit + 1)
    if not raw or len(raw) > limit:
        raise RuntimeError("Invalid observer response size")

    decoded = json.loads(
        raw.decode("utf-8"), object_pairs_hook=_unique_object,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Invalid JSON number"))
    )
    if type(decoded) is not dict or set(decoded) != {"ok", "operation", "result"}:
        raise RuntimeError("Invalid observer response")
    if decoded["ok"] is not True or decoded["operation"] != operation:
        raise RuntimeError("Observer rejected the request")
    return validate_result(operation, decoded["result"])
