"""Pure Python semantic-to-MPFB bone map; shared by inspection and posing."""
import re

FINGERS = ("thumb", "index", "middle", "ring", "pinky")
PARTS = {"right_wrist": "wrist.R", "left_wrist": "wrist.L",
         "right_upper_arm": "upperarm01.R", "left_upper_arm": "upperarm01.L",
         "right_forearm": "lowerarm01.R", "left_forearm": "lowerarm01.L"}

def semantic_bones(names):
    names = set(names)
    result = {label: actual for label, actual in PARTS.items() if actual in names}
    for side, suffix in (("right", "R"), ("left", "L")):
        for i, finger in enumerate(FINGERS, 1):
            for joint in (1, 2, 3):
                actual = f"finger{i}-{joint}.{suffix}"
                if actual in names:
                    result[f"{side}_{finger}_{joint}"] = actual
    return result

def classify_bones(names):
    result = {"head": [], "spine": [], "upper_arm": [], "forearm": [],
              "hand": [], "thumb": [], "index": [], "middle": [], "ring": [],
              "pinky": [], "thigh": [], "shin": [], "foot": []}
    aliases = {"head": ("head",), "spine": ("spine", "chest", "hips", "pelvis"),
               "upper_arm": ("upperarm", "upper_arm"), "forearm": ("forearm", "lowerarm"),
               "hand": ("hand", "wrist"), "thigh": ("thigh", "upperleg", "upleg"),
               "shin": ("shin", "lowerleg", "calf"), "foot": ("foot", "ankle")}
    for name in names:
        norm = name.casefold().replace(" ", "").replace("-", "_")
        m = re.fullmatch(r"finger([1-5])_[1-3]\.[lr]", norm)
        if m:
            result[FINGERS[int(m.group(1)) - 1]].append(name)
        for group, words in aliases.items():
            if any(word in norm for word in words):
                result[group].append(name)
    return result


ARM_CHAINS = {
    side: [f"lowerarm02.{suffix}", f"lowerarm01.{suffix}",
           f"upperarm02.{suffix}", f"upperarm01.{suffix}",
           f"shoulder01.{suffix}", f"clavicle.{suffix}"]
    for side, suffix in (("right", "R"), ("left", "L"))
}

def arm_chain(side, names):
    if side not in ARM_CHAINS:
        raise ValueError(f"Unknown hand side: {side}")
    available = set(names)
    missing = [n for n in ARM_CHAINS[side] if n not in available]
    if missing:
        raise ValueError("Incomplete MPFB arm chain: " + ", ".join(missing))
    return list(ARM_CHAINS[side])

def wrist_bone_name(side):
    if side not in ARM_CHAINS:
        raise ValueError(f"Unknown hand side: {side}")
    return "wrist." + ("R" if side == "right" else "L")
