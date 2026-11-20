"""Read-only Blender scene and character-development intelligence."""

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    summary: str
    evidence: tuple[str, ...]
    recommendation: str


@dataclass(frozen=True)
class PipelineAssessment:
    stage: str
    status: str
    reason: str


class BlenderSceneAnalyzer:
    """Analyze validated Blender observer snapshots without modifying Blender."""

    BODY_HINTS = (
        "body", "torso", "pelvis", "chest", "spine",
        "head", "neck", "character", "testarossa"
    )
    FACE_HINTS = (
        "face", "eye", "eyebrow", "eyelash", "mouth",
        "lip", "nose", "jaw", "teeth"
    )
    HAND_HINTS = ("hand", "finger", "thumb", "palm")
    HAIR_HINTS = ("hair", "bang", "ponytail", "braid")
    CLOTHING_HINTS = (
        "cloth", "clothing", "outfit", "dress", "shirt",
        "skirt", "shoe", "boot", "glove"
    )

    def analyze_scene(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        self._require_snapshot(snapshot, 1)

        objects = snapshot["objects"]
        meshes = [o for o in objects if o["type"] == "MESH"]
        armatures = [o for o in objects if o["type"] == "ARMATURE"]
        cameras = [o for o in objects if o["type"] == "CAMERA"]
        lights = [o for o in objects if o["type"] == "LIGHT"]

        names = [o["name"].lower() for o in objects]
        mesh_names = [o["name"].lower() for o in meshes]

        findings: list[Finding] = []

        if not meshes:
            findings.append(Finding(
                "NO_CHARACTER_MESH", "blocker",
                "No mesh objects were found in the inspected scene.",
                ("mesh_count=0",),
                "Create or import a character mesh before topology and rigging work."
            ))
        else:
            findings.append(Finding(
                "MESHES_PRESENT", "info",
                f"Found {len(meshes)} mesh object(s).",
                tuple(o["name"] for o in meshes[:20]),
                "Inspect mesh topology, anatomy, and object organization."
            ))

        if not armatures:
            findings.append(Finding(
                "NO_ARMATURE", "warning",
                "No armature object was found.",
                ("armature_count=0",),
                "Create a suitable skeletal rig after confirming the character mesh."
            ))
        else:
            bone_counts = [
                o.get("armature", {}).get("bone_count", 0)
                for o in armatures
            ]
            findings.append(Finding(
                "ARMATURE_PRESENT", "info",
                f"Found {len(armatures)} armature object(s).",
                tuple(
                    f"{o['name']}: {o.get('armature', {}).get('bone_count', 0)} bones"
                    for o in armatures
                ),
                "Inspect bone hierarchy, deformation coverage, and controls."
            ))
            if not any(count > 0 for count in bone_counts):
                findings.append(Finding(
                    "EMPTY_ARMATURE", "warning",
                    "Armature objects exist, but no bones were reported.",
                    tuple(f"bone_count={n}" for n in bone_counts),
                    "Inspect and populate the armature before attempting deformation."
                ))

        if meshes and not armatures:
            findings.append(Finding(
                "RIGGING_NOT_STARTED", "warning",
                "Meshes exist without a reported armature.",
                ("mesh_count>0", "armature_count=0"),
                "Review mesh organization and anatomy before creating the rig."
            ))

        if meshes and armatures:
            attached = [
                o["name"] for o in meshes
                if any(
                    m["type"] == "ARMATURE"
                    for m in o.get("modifiers", [])
                )
            ]
            if not attached:
                findings.append(Finding(
                    "NO_ARMATURE_MODIFIER", "warning",
                    "No mesh reports an armature modifier.",
                    ("armature objects exist", "no mesh armature modifier found"),
                    "Check whether meshes are bound to the intended armature."
                ))

        def matching(hints: tuple[str, ...]) -> list[str]:
            return [
                name for name in mesh_names
                if any(hint in name for hint in hints)
            ]

        anatomy = {
            "body_candidates": matching(self.BODY_HINTS),
            "face_candidates": matching(self.FACE_HINTS),
            "hand_candidates": matching(self.HAND_HINTS),
            "hair_candidates": matching(self.HAIR_HINTS),
            "clothing_candidates": matching(self.CLOTHING_HINTS),
        }

        for key, label in (
            ("body_candidates", "body"),
            ("face_candidates", "facial"),
            ("hand_candidates", "hand/finger"),
            ("hair_candidates", "hair"),
            ("clothing_candidates", "clothing"),
        ):
            if not anatomy[key]:
                findings.append(Finding(
                    f"{key.upper()}_NOT_IDENTIFIED", "info",
                    f"No clearly named {label} mesh candidate was identified.",
                    ("name-based inspection only",),
                    f"Inspect the scene manually or improve object naming; "
                    f"this does not prove the {label} geometry is absent."
                ))

        total_vertices = sum(
            o["geometry"]["vertices"] for o in meshes
        )
        total_edges = sum(
            o["geometry"]["edges"] for o in meshes
        )
        total_polygons = sum(
            o["geometry"]["polygons"] for o in meshes
        )

        if meshes and total_vertices == 0:
            findings.append(Finding(
                "EMPTY_MESH_GEOMETRY", "warning",
                "Mesh objects report zero total vertices.",
                ("total_vertices=0",),
                "Inspect mesh data before proceeding."
            ))

        animated = [
            o["name"] for o in objects
            if o.get("animation")
            and o["animation"].get("action") is not None
        ]

        if not animated:
            findings.append(Finding(
                "NO_OBJECT_ANIMATION", "info",
                "No object-level active animation action was reported.",
                ("active object actions not found",),
                "Animation may be developed after rigging and deformation checks."
            ))

        material_count = sum(len(o.get("materials", [])) for o in meshes)

        if not material_count and meshes:
            findings.append(Finding(
                "NO_MESH_MATERIALS", "info",
                "No mesh material assignments were reported.",
                ("material assignments=0",),
                "Plan skin, eye, hair, and clothing material systems."
            ))

        summary = snapshot["summary"]
        if summary["objects_truncated"]:
            findings.append(Finding(
                "SCENE_OBJECTS_TRUNCATED", "warning",
                "The observer returned only part of the scene inventory.",
                (f"reported_objects={summary['object_count']}",
                 f"returned_objects={len(objects)}"),
                "Obtain a complete inventory before making global completeness claims."
            ))

        stages = self._pipeline(meshes, armatures, anatomy, animated)

        return {
            "analyzer_version": "0.1.0",
            "source": "read_only_blender_scene_snapshot",
            "blender_version": snapshot["blender_version"],
            "scene_name": snapshot["scene"]["name"],
            "read_only": True,
            "inventory": {
                "objects_returned": len(objects),
                "objects_reported": summary["object_count"],
                "meshes": len(meshes),
                "armatures": len(armatures),
                "cameras": len(cameras),
                "lights": len(lights),
                "vertices": total_vertices,
                "edges": total_edges,
                "polygons": total_polygons,
                "mesh_material_assignments": material_count,
                "animated_objects": animated,
            },
            "anatomy_candidates": anatomy,
            "pipeline": [asdict(stage) for stage in stages],
            "findings": [asdict(finding) for finding in findings],
            "limitations": [
                "Object names are clues, not proof of anatomical completeness.",
                "Vertex and polygon counts do not establish topology quality.",
                "This snapshot cannot establish mesh connectivity or skin-weight quality.",
                "A reported armature does not prove correct skeletal anatomy.",
                "No screenshot, image recognition, or geometry mutation is performed.",
            ],
        }

    def analyze_project(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        self._require_snapshot(snapshot, 3)

        scene_reports = []
        for scene in snapshot["scenes"]:
            scene_reports.append({
                "scene": scene["name"],
                "objects": scene["object_count"],
                "meshes": sum(o["type"] == "MESH" for o in scene["objects"]),
                "armatures": sum(o["type"] == "ARMATURE" for o in scene["objects"]),
                "truncated": scene["objects_truncated"],
            })

        return {
            "analyzer_version": "0.1.0",
            "source": "read_only_blender_project_snapshot",
            "read_only": True,
            "project": dict(snapshot["project"]),
            "inventory": {
                "scenes": len(snapshot["scenes"]),
                "collections": len(snapshot["collections"]),
                "materials": len(snapshot["materials"]),
                "actions": len(snapshot["actions"]),
                "objects": len(snapshot["objects"]),
                "meshes": sum(o["type"] == "MESH" for o in snapshot["objects"]),
                "armatures": sum(o["type"] == "ARMATURE" for o in snapshot["objects"]),
            },
            "scenes": scene_reports,
            "materials": [dict(m) for m in snapshot["materials"]],
            "actions": [dict(a) for a in snapshot["actions"]],
            "truncation": {
                key: snapshot[key]
                for key in (
                    "scenes_truncated", "collections_truncated",
                    "materials_truncated", "actions_truncated",
                    "objects_truncated"
                )
            },
            "limitations": [
                "Project inventory is limited to the observer's returned snapshot.",
                "Truncated inventories cannot support complete project conclusions.",
            ],
        }

    @staticmethod
    def _require_snapshot(snapshot: dict[str, Any], version: int) -> None:
        """Validate the observer snapshot structure before analysis."""
        if type(snapshot) is not dict:
            raise ValueError("snapshot_must_be_dictionary")
        if type(snapshot.get("schema_version")) is not int:
            raise ValueError("invalid_snapshot_schema_version")
        if snapshot["schema_version"] != version:
            raise ValueError("unsupported_blender_snapshot_schema")
        if snapshot.get("read_only") is not True:
            raise ValueError("snapshot_must_be_read_only")

        common = ("captured_at", "blender_version", "read_only")
        if any(key not in snapshot for key in common):
            raise ValueError("snapshot_missing_common_field")
        if type(snapshot["captured_at"]) not in (int, float):
            raise ValueError("invalid_snapshot_timestamp")
        if type(snapshot["blender_version"]) is not str:
            raise ValueError("invalid_blender_version")

        if version == 1:
            if not all(key in snapshot for key in (
                "scene", "summary", "objects"
            )):
                raise ValueError("scene_snapshot_missing_field")
            scene = snapshot["scene"]
            summary = snapshot["summary"]
            objects = snapshot["objects"]

            if type(scene) is not dict or type(scene.get("name")) is not str:
                raise ValueError("invalid_scene_metadata")
            if type(summary) is not dict:
                raise ValueError("invalid_scene_summary")
            if type(objects) is not list:
                raise ValueError("invalid_scene_objects")

            for key in (
                "object_count", "object_type_counts", "objects_truncated",
                "mesh_count", "armature_count", "camera_count", "light_count"
            ):
                if key not in summary:
                    raise ValueError("scene_summary_missing_field")
            for key in (
                "object_count", "mesh_count", "armature_count",
                "camera_count", "light_count"
            ):
                if type(summary[key]) is not int or summary[key] < 0:
                    raise ValueError("invalid_scene_summary_count")
            if type(summary["objects_truncated"]) is not bool:
                raise ValueError("invalid_scene_truncation_flag")
            if type(summary["object_type_counts"]) is not dict:
                raise ValueError("invalid_object_type_counts")

            for obj in objects:
                if type(obj) is not dict:
                    raise ValueError("invalid_scene_object")
                if type(obj.get("name")) is not str or type(obj.get("type")) is not str:
                    raise ValueError("invalid_scene_object_identity")
                if obj["type"] == "MESH":
                    geometry = obj.get("geometry")
                    if type(geometry) is not dict:
                        raise ValueError("mesh_geometry_missing")
                    for key in ("vertices", "edges", "polygons"):
                        value = geometry.get(key)
                        if type(value) is not int or value < 0:
                            raise ValueError("invalid_mesh_geometry_count")
                animation = obj.get("animation")
                if type(animation) is not dict:
                    raise ValueError("object_animation_metadata_missing")
                if "action" not in animation:
                    raise ValueError("object_animation_action_missing")
                modifiers = obj.get("modifiers")
                materials = obj.get("materials")
                if type(modifiers) is not list or type(materials) is not list:
                    raise ValueError("invalid_object_component_lists")

        elif version == 3:
            required = (
                "project", "scenes", "scenes_truncated",
                "collections", "collections_truncated",
                "materials", "materials_truncated",
                "actions", "actions_truncated",
                "objects", "objects_truncated", "summary"
            )
            if any(key not in snapshot for key in required):
                raise ValueError("project_snapshot_missing_field")
            if type(snapshot["project"]) is not dict:
                raise ValueError("invalid_project_metadata")
            if type(snapshot["summary"]) is not dict:
                raise ValueError("invalid_project_summary")

            for key in (
                "scenes", "collections", "materials", "actions", "objects"
            ):
                if type(snapshot[key]) is not list:
                    raise ValueError("invalid_project_inventory")
            for key in (
                "scenes_truncated", "collections_truncated",
                "materials_truncated", "actions_truncated", "objects_truncated"
            ):
                if type(snapshot[key]) is not bool:
                    raise ValueError("invalid_project_truncation_flag")

            for scene in snapshot["scenes"]:
                if (
                    type(scene) is not dict
                    or type(scene.get("name")) is not str
                    or type(scene.get("object_count")) is not int
                    or type(scene.get("objects")) is not list
                    or type(scene.get("objects_truncated")) is not bool
                ):
                    raise ValueError("invalid_project_scene_entry")
                for obj in scene["objects"]:
                    if (
                        type(obj) is not dict
                        or type(obj.get("name")) is not str
                        or type(obj.get("type")) is not str
                    ):
                        raise ValueError("invalid_project_scene_object")

            for obj in snapshot["objects"]:
                if (
                    type(obj) is not dict
                    or type(obj.get("name")) is not str
                    or type(obj.get("type")) is not str
                ):
                    raise ValueError("invalid_project_object")

            for item_key in ("collections", "materials", "actions"):
                for item in snapshot[item_key]:
                    if type(item) is not dict:
                        raise ValueError("invalid_project_inventory_entry")

    @staticmethod
    def _pipeline(meshes, armatures, anatomy, animated):
        return [
            PipelineAssessment(
                "scene_inspection", "complete",
                "A validated scene snapshot was supplied."
            ),
            PipelineAssessment(
                "anatomical_foundation",
                "candidate_found" if anatomy["body_candidates"] else "unverified",
                "A body-named mesh exists." if anatomy["body_candidates"]
                else "No body-named mesh was identified."
            ),
            PipelineAssessment(
                "production_topology",
                "requires_inspection" if meshes else "blocked",
                "Mesh counts are available, but topology quality is not measurable "
                "from this snapshot."
            ),
            PipelineAssessment(
                "facial_system",
                "candidate_found" if anatomy["face_candidates"] else "unverified",
                "Face-named mesh candidates exist." if anatomy["face_candidates"]
                else "Facial geometry has not been identified by name."
            ),
            PipelineAssessment(
                "rigging_and_deformation",
                "candidate_found" if meshes and armatures else "blocked",
                "Meshes and armatures exist; binding and deformation still need validation."
                if meshes and armatures else
                "Both mesh and armature evidence are required."
            ),
            PipelineAssessment(
                "animation_system",
                "candidate_found" if animated else "not_detected",
                "Active object animation actions were reported." if animated
                else "No active object animation action was reported."
            ),
        ]
