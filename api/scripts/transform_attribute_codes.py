"""Transform seed data JSON files to fix attribute code conflicts.

Renames attribute codes that appear in multiple files with different group_code
values, and normalizes group_code for shared boolean attributes.

Usage: python scripts/transform_attribute_codes.py
"""

import json
import os
import re

SEED_DIR = os.path.join(os.path.dirname(__file__), "seed_data")

# === Rename map: (filename, old_code) -> new_code ===
# Category 1 & 3: truly different attributes sharing same code

RENAME_MAP = {
    # -- closure_type (keep only for dresses, rename for all others) --
    ("08_attributes_bags.json", "closure_type"): "bag_closure_type",
    ("11_attributes_belts_leather_goods.json", "closure_type"): "belt_closure_type",
    ("15_attributes_athletic_sneakers.json", "closure_type"): "shoe_closure_type",
    ("16_attributes_boots.json", "closure_type"): "shoe_closure_type",
    ("17_attributes_heels_dress_shoes.json", "closure_type"): "shoe_closure_type",
    ("18_attributes_sandals_slippers.json", "closure_type"): "shoe_closure_type",
    ("25_attributes_tops.json", "closure_type"): "top_closure_type",
    ("26_attributes_bottoms.json", "closure_type"): "bottom_closure_type",
    ("27_attributes_outerwear.json", "closure_type"): "outerwear_closure_type",
    ("31_attributes_abayas.json", "closure_type"): "abaya_closure_type",
    ("36_attributes_skirts.json", "closure_type"): "skirt_closure_type",
    # Keep closure_type only in: 24_dresses
    # -- fit_type (keep for dresses, rename for others) --
    ("25_attributes_tops.json", "fit_type"): "top_fit_type",
    ("26_attributes_bottoms.json", "fit_type"): "bottom_fit_type",
    ("27_attributes_outerwear.json", "fit_type"): "outerwear_fit_type",
    ("28_attributes_activewear.json", "fit_type"): "activewear_fit_type",
    ("36_attributes_skirts.json", "fit_type"): "skirt_fit_type",
    ("37_attributes_suits_formalwear.json", "fit_type"): "suit_fit_type",
    # Keep fit_type in: 24_dresses
    # -- sleeve_style (keep for dresses, rename for others) --
    ("25_attributes_tops.json", "sleeve_style"): "top_sleeve_style",
    ("27_attributes_outerwear.json", "sleeve_style"): "outerwear_sleeve_style",
    ("28_attributes_activewear.json", "sleeve_style"): "activewear_sleeve_style",
    ("29_attributes_swimwear.json", "sleeve_style"): "swimwear_sleeve_style",
    ("30_attributes_lingerie_sleepwear.json", "sleeve_style"): "lingerie_sleeve_style",
    ("31_attributes_abayas.json", "sleeve_style"): "abaya_sleeve_style",
    # Keep sleeve_style in: 24_dresses
    # -- neckline (keep for dresses, rename for others) --
    ("25_attributes_tops.json", "neckline"): "top_neckline",
    ("27_attributes_outerwear.json", "neckline"): "outerwear_neckline",
    ("30_attributes_lingerie_sleepwear.json", "neckline"): "lingerie_neckline",
    ("31_attributes_abayas.json", "neckline"): "abaya_neckline",
    # Keep neckline in: 24_dresses
    # -- heel_height --
    ("16_attributes_boots.json", "heel_height"): "boot_heel_height",
    # Keep heel_height in: 17_heels_dress_shoes
    ("18_attributes_sandals_slippers.json", "heel_height"): "sandal_heel_height",
    # -- heel_type --
    # Keep heel_type in: 17_heels_dress_shoes
    ("18_attributes_sandals_slippers.json", "heel_type"): "sandal_heel_type",
    # -- toe_style --
    ("16_attributes_boots.json", "toe_style"): "boot_toe_style",
    ("17_attributes_heels_dress_shoes.json", "toe_style"): "heel_toe_style",
    ("18_attributes_sandals_slippers.json", "toe_style"): "sandal_toe_style",
    # -- waist_rise --
    # Keep waist_rise in: 26_bottoms
    ("36_attributes_skirts.json", "waist_rise"): "skirt_waist_rise",
    # -- waistband_style --
    # Keep waistband_style in: 26_bottoms
    ("36_attributes_skirts.json", "waistband_style"): "skirt_waistband_style",
    # -- fabric_type --
    # Keep fabric_type in: 31_abayas
    ("32_attributes_scarves_hijabs.json", "fabric_type"): "scarf_fabric_type",
    # -- clasp_type --
    # Keep clasp_type in: 19_necklaces_pendants
    ("20_attributes_bracelets_anklets.json", "clasp_type"): "bracelet_clasp_type",
    ("23_attributes_other_jewelry.json", "clasp_type"): "other_jewelry_clasp_type",
    # -- case_diameter --
    # Keep case_diameter in: 14_specialty_accessories
    ("34_attributes_watches.json", "case_diameter"): "watch_case_diameter",
    # -- movement_type --
    # Keep movement_type in: 14_specialty_accessories
    ("34_attributes_watches.json", "movement_type"): "watch_movement_type",
    # -- season --
    # Keep season in: 05_fashion
    ("13_attributes_textile_accessories.json", "season"): "textile_season",
    ("16_attributes_boots.json", "season"): "boot_season",
    # -- water_resistance --
    ("14_attributes_specialty_accessories.json", "water_resistance"): "specialty_water_resistance",
    ("27_attributes_outerwear.json", "water_resistance"): "outerwear_water_resistance",
    ("34_attributes_watches.json", "water_resistance"): "watch_water_resistance",
    # -- frame_shape --
    # Keep frame_shape in: 12_head_accessories
    ("35_attributes_eyewear.json", "frame_shape"): "eyewear_frame_shape",
    # -- occasion --
    # Keep occasion in: 05_fashion
    ("17_attributes_heels_dress_shoes.json", "occasion"): "heel_occasion",
    ("18_attributes_sandals_slippers.json", "occasion"): "sandal_occasion",
    # -- lining_type --
    # Keep lining_type in: 29_swimwear
    ("37_attributes_suits_formalwear.json", "lining_type"): "suit_lining_type",
    # -- gender_target --
    # Keep gender_target in: 33_fragrance
    ("34_attributes_watches.json", "gender_target"): "watch_gender_target",
    ("35_attributes_eyewear.json", "gender_target"): "eyewear_gender_target",
    # -- adjustable_size --
    ("11_attributes_belts_leather_goods.json", "adjustable_size"): "belt_adjustable_size",
    ("12_attributes_head_accessories.json", "adjustable_size"): "headwear_adjustable_size",
    ("13_attributes_textile_accessories.json", "adjustable_size"): "textile_adjustable_size",
    # -- adjustable_strap --
    ("08_attributes_bags.json", "adjustable_strap"): "bag_adjustable_strap",
    ("18_attributes_sandals_slippers.json", "adjustable_strap"): "sandal_adjustable_strap",
    # -- lightweight --
    ("08_attributes_bags.json", "lightweight"): "bag_lightweight",
    ("15_attributes_athletic_sneakers.json", "lightweight"): "shoe_lightweight",
    ("17_attributes_heels_dress_shoes.json", "lightweight"): "shoe_lightweight",
    ("18_attributes_sandals_slippers.json", "lightweight"): "shoe_lightweight",
    # -- lining_material --
    ("08_attributes_bags.json", "lining_material"): "bag_lining_material",
    ("13_attributes_textile_accessories.json", "lining_material"): "textile_lining_material",
    ("15_attributes_athletic_sneakers.json", "lining_material"): "shoe_lining_material",
    ("16_attributes_boots.json", "lining_material"): "shoe_lining_material",
    ("17_attributes_heels_dress_shoes.json", "lining_material"): "shoe_lining_material",
    # -- dimensions --
    ("08_attributes_bags.json", "dimensions"): "bag_dimensions",
    ("11_attributes_belts_leather_goods.json", "dimensions"): "belt_dimensions",
    # -- one_size --
    ("11_attributes_belts_leather_goods.json", "one_size"): "belt_one_size",
    ("12_attributes_head_accessories.json", "one_size"): "headwear_one_size",
    ("14_attributes_specialty_accessories.json", "one_size"): "specialty_one_size",
    # -- hypoallergenic --
    ("11_attributes_belts_leather_goods.json", "hypoallergenic"): "belt_hypoallergenic",
    ("12_attributes_head_accessories.json", "hypoallergenic"): "headwear_hypoallergenic",
    ("13_attributes_textile_accessories.json", "hypoallergenic"): "textile_hypoallergenic",
    ("19_attributes_necklaces_pendants.json", "hypoallergenic"): "jewelry_hypoallergenic",
    ("20_attributes_bracelets_anklets.json", "hypoallergenic"): "jewelry_hypoallergenic",
    ("21_attributes_earrings.json", "hypoallergenic"): "jewelry_hypoallergenic",
    ("22_attributes_rings.json", "hypoallergenic"): "jewelry_hypoallergenic",
    ("23_attributes_other_jewelry.json", "hypoallergenic"): "jewelry_hypoallergenic",
    # -- waterproof --
    ("08_attributes_bags.json", "waterproof"): "bag_waterproof",
    ("11_attributes_belts_leather_goods.json", "waterproof"): "belt_waterproof",
    ("15_attributes_athletic_sneakers.json", "waterproof"): "shoe_waterproof",
    ("16_attributes_boots.json", "waterproof"): "shoe_waterproof",
    ("17_attributes_heels_dress_shoes.json", "waterproof"): "shoe_waterproof",
    ("18_attributes_sandals_slippers.json", "waterproof"): "shoe_waterproof",
    # -- Category 3: Beauty/body-care crossovers --
    # vegan: keep in 08_bags, rename others
    ("09_attributes_beauty.json", "vegan"): "beauty_vegan",
    ("17_attributes_heels_dress_shoes.json", "vegan"): "shoe_vegan",
    ("38_attributes_body_care.json", "vegan"): "body_care_vegan",
    # cruelty_free
    ("09_attributes_beauty.json", "cruelty_free"): "beauty_cruelty_free",
    ("38_attributes_body_care.json", "cruelty_free"): "body_care_cruelty_free",
    # organic
    ("09_attributes_beauty.json", "organic"): "beauty_organic",
    ("38_attributes_body_care.json", "organic"): "body_care_organic",
    # skin_type
    ("09_attributes_beauty.json", "skin_type"): "beauty_skin_type",
    ("38_attributes_body_care.json", "skin_type"): "body_care_skin_type",
    # formulation
    ("09_attributes_beauty.json", "formulation"): "beauty_formulation",
    ("38_attributes_body_care.json", "formulation"): "body_care_formulation",
    # fragrance_family
    ("09_attributes_beauty.json", "fragrance_family"): "beauty_fragrance_family",
    # Keep fragrance_family in: 33_fragrance
    # volume_ml
    ("09_attributes_beauty.json", "volume_ml"): "beauty_volume_ml",
    ("33_attributes_fragrance.json", "volume_ml"): "fragrance_volume_ml",
    ("38_attributes_body_care.json", "volume_ml"): "body_care_volume_ml",
    # weight_g
    ("09_attributes_beauty.json", "weight_g"): "beauty_weight_g",
    ("11_attributes_belts_leather_goods.json", "weight_g"): "belt_weight_g",
    ("14_attributes_specialty_accessories.json", "weight_g"): "specialty_weight_g",
    # uv_protection
    ("12_attributes_head_accessories.json", "uv_protection"): "headwear_uv_protection",
    ("35_attributes_eyewear.json", "uv_protection"): "eyewear_uv_protection",
}


def transform_file(fpath: str) -> list[dict]:
    """Read, transform, and write back a JSON attribute file. Returns changed attrs."""
    with open(fpath) as f:
        data = json.load(f)

    fname = os.path.basename(fpath)
    changed = []

    for attr in data.get("attributes", []):
        old_code = attr["code"]
        key = (fname, old_code)
        if key in RENAME_MAP:
            new_code = RENAME_MAP[key]
            if old_code != new_code:
                changed.append({"file": fname, "old": old_code, "new": new_code})
                attr["code"] = new_code

        # Also rename any reference to the old code inside the file
        # (e.g., validation_rules that reference other attributes by code)
        # Not needed for current use case

    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return changed


def main():
    all_changes = []
    for fname in sorted(os.listdir(SEED_DIR)):
        if not re.match(r"\d+_attributes_.+\.json$", fname):
            continue
        fpath = os.path.join(SEED_DIR, fname)
        changes = transform_file(fpath)
        all_changes.extend(changes)

    changed_files = set(c["file"] for c in all_changes)

    print(f"Total attribute renames applied: {len(all_changes)}")
    print(f"Files modified: {len(changed_files)}")
    for fname in sorted(changed_files):
        file_changes = [c for c in all_changes if c["file"] == fname]
        print(f"\n  {fname}:")
        for c in file_changes:
            print(f"    {c['old']} → {c['new']}")


if __name__ == "__main__":
    main()
