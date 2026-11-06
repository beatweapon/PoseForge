"""Conservative ranking of sampled finger-skin/handle proximity.

A good proxy score is not evidence of an anatomically plausible grasp.
Missing vertex samples must never be interpreted as zero penetration.
"""


def score_skin_samples(skin):
    hands = (skin or {}).get("hands", {})
    if set(hands) != {"left", "right"}:
        raise ValueError("Both hands require sampled skin diagnostics")
    total_score = 0.0
    total_deep = 0
    contact_candidates = 0
    invalid = []
    details = []
    for side in ("left", "right"):
        fingers = hands[side].get("fingers", {})
        for finger in ("thumb", "index"):
            row = fingers.get(finger, {})
            count = row.get("sample_count", 0)
            gap = row.get("nearest_abs_gap_m")
            deep = row.get("sampled_inside_over_2mm", 0)
            if not count or gap is None:
                invalid.append(f"{side}_{finger}:no_nearby_skin_vertices")
                total_score += 250.0
            else:
                # Distances are in millimetres. Penalize deep penetration
                # more strongly than a merely distant surface.
                total_score += min(75.0, gap * 1000.0)
                total_score += 12.0 * deep
                if row.get("sampled_within_5mm", 0) > 0:
                    contact_candidates += 1
            total_deep += deep
            details.append({"hand": side, "finger": finger,
                            "nearby_vertices": count, "nearest_gap_m": gap,
                            "penetrating_vertices": deep})
    return {
        "score": round(total_score, 3),
        "penetrating_vertices": total_deep,
        "near_surface_fingers": contact_candidates,
        "sample_gaps": invalid,
        "per_finger": details,
        "proxy_eligible": not invalid,
        # 4 close fingers and no deep penetration are necessary but
        # absolutely not sufficient for declaring a natural grip.
        "passes_screening": (not invalid and contact_candidates == 4
                             and total_deep == 0),
        "surface_contact_verified": False,
        "collision_free_verified": False,
    }


def compare_skin_candidates(rows):
    valid = [r for r in rows if r["skin_quality"]["proxy_eligible"]]
    if not valid:
        return None
    return min(valid, key=lambda r: (
        r["skin_quality"]["score"],
        r["skin_quality"]["penetrating_vertices"],
        r["variant"],
    ))["variant"]
