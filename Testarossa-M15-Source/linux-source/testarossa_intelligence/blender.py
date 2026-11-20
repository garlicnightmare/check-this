"""Character-generation knowledge and staged Blender production plans."""
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class ProductionStage:
    id: str
    title: str
    objective: str
    acceptance: tuple[str, ...]
    approval_required: bool


CHARACTER_PIPELINE = (
    ProductionStage("reference", "Design specification",
        "Establish proportions, silhouette, visual identity and reference measurements.",
        ("Full-body proportion sheet defined", "Identity choices separated from provisional defaults"), False),
    ProductionStage("anatomy", "Anatomical foundation",
        "Construct a coherent human anatomy with continuous forms and correct landmarks.",
        ("Head, torso, pelvis and limbs proportionally connected",
         "Hands and feet anatomically complete", "No disconnected primitive mannequin parts"), False),
    ProductionStage("topology", "Production topology",
        "Create deformation-aware topology with clean edge flow and controlled density.",
        ("Deformation loops around shoulders, elbows, hips and knees",
         "Facial loops support expression", "No non-manifold defects"), False),
    ProductionStage("face", "Facial system",
        "Build facial forms and controls for expression and speech.",
        ("Eyes, eyelids, nose and lips defined",
         "Facial expressions independently testable"), False),
    ProductionStage("surface", "Surface and materials",
        "Create skin, eyes, hair and material response with a coherent art direction.",
        ("Materials use named parameters", "No missing material references"), False),
    ProductionStage("hair_clothing", "Hair and modular wardrobe",
        "Create groomed hair and separately addressable clothing components.",
        ("Hair is separate and editable", "Wardrobe parts can be changed independently"), False),
    ProductionStage("rig", "Rigging and deformation",
        "Create a full-body rig with IK/FK controls, facial controls and tested skin weights.",
        ("All major joints deform correctly", "Hands and fingers are controllable",
         "No severe mesh collapse in test poses"), False),
    ProductionStage("motion", "Animation system",
        "Create grounded locomotion, idle, gestures and expressive reactions.",
        ("Idle breathing and blinking", "Walk and turn cycle", "Emotion transitions tested"), False),
    ProductionStage("qa", "Visual and technical validation",
        "Inspect silhouette, topology, materials, rigging and animation under test poses.",
        ("Automated checks pass", "Visual review recorded", "Failures have repair tasks"), False),
    ProductionStage("delivery", "Save and package",
        "Prepare a versioned, recoverable Blender project and its reports.",
        ("Project opens successfully", "Assets are inventoried", "Backup and report exist"), True),
)


def character_plan():
    """Return a declarative plan; this does not execute Blender."""
    return {
        "character": "Testarossa",
        "pipeline_version": 1,
        "design_constraints": {
            "anatomy": "realistic_human",
            "style": "realistic_body_mechanics_expressive_anime_game_personality",
            "quality": "high_detail",
            "forbidden_shortcuts": [
                "low_poly_mannequin", "disconnected_primitive_body_parts",
                "toy_like_proportions", "unrigged_final_mesh"
            ],
            "identity_choices": {
                "nose": "C", "lips": "C",
                "eyebrows": "B", "eyelashes": "B",
                "skin_tone": "undecided", "outfit": "undecided",
                "hair": "provisional", "eye_colour": "provisional",
                "horns": "configurable_off_by_default"
            }
        },
        "stages": [asdict(stage) for stage in CHARACTER_PIPELINE],
    }
