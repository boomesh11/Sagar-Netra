import os
import glob
import numpy as np
from PIL import Image
from scipy.ndimage import label, find_objects

def prepare_real_dataset():
    train_img_dir = r"D:\PS2\AI4Shipwrecks_train_images"
    train_lbl_dir = r"D:\PS2\AI4Shipwrecks_train_labels"
    test_img_dir = r"D:\PS2\AI4Shipwrecks_test_images"
    test_lbl_dir = r"D:\PS2\AI4Shipwrecks_test_labels"

    out_base = r"D:\SIHPS2\data\datasets\real_ai4shipwrecks_yolo"
    for split in ["train", "val", "test"]:
        os.makedirs(os.path.join(out_base, split, "images"), exist_ok=True)
        os.makedirs(os.path.join(out_base, split, "labels"), exist_ok=True)

    # Validation sites (held out from train to guarantee zero spatial leakage)
    val_sites = ["Oscar_T_Flint", "Pewabic", "WP_Rend", "Montana"]

    tile_size = 640
    counts = {"train": 0, "val": 0, "test": 0, "negatives": 0}

    def process_split(img_dir, lbl_dir, default_split):
        images = glob.glob(os.path.join(img_dir, "*.png"))
        print(f"Processing {len(images)} raw waterfall records for {default_split}...")

        for img_path in images:
            basename = os.path.basename(img_path)
            site_name = basename.rsplit("_", 1)[0]
            lbl_path = os.path.join(lbl_dir, basename)

            if not os.path.exists(lbl_path):
                continue

            # Determine split
            if default_split == "test":
                split = "test"
            else:
                split = "val" if any(vs.lower() in site_name.lower() for vs in val_sites) else "train"

            try:
                img = Image.open(img_path).convert("L")
                lbl = Image.open(lbl_path)

                img_arr = np.array(img)
                lbl_arr = np.array(lbl)
            except Exception as e:
                print(f"Error reading {basename}: {e}")
                continue

            h, w = img_arr.shape

            # Connected component analysis for shipwreck annotations
            labeled_mask, num_features = label(lbl_arr > 0)
            slices = find_objects(labeled_mask)

            has_positives = False
            for obj_idx, s in enumerate(slices):
                if s is None:
                    continue
                # Bounding box of the wreck in full-scale coordinates
                ymin, ymax = s[0].start, s[0].stop
                xmin, xmax = s[1].start, s[1].stop
                box_w = xmax - xmin
                box_h = ymax - ymin

                # Filter out tiny spurious noise specks (< 100 pixels)
                if np.sum(labeled_mask[s] == (obj_idx + 1)) < 80:
                    continue

                has_positives = True
                cy = (ymin + ymax) // 2
                cx = (xmin + xmax) // 2

                # Generate multiple jitter crops around the target for robust coverage
                jitters = [(0, 0)]
                if split == "train":
                    jitters = [(0, 0), (-40, -40), (40, 40), (0, 60), (60, 0)]

                for j_idx, (jx, jy) in enumerate(jitters):
                    t_cx = max(tile_size // 2, min(w - tile_size // 2, cx + jx))
                    t_cy = max(tile_size // 2, min(h - tile_size // 2, cy + jy))

                    t_xmin = t_cx - tile_size // 2
                    t_ymin = t_cy - tile_size // 2
                    t_xmax = t_xmin + tile_size
                    t_ymax = t_ymin + tile_size

                    # Crop image tile
                    tile = img_arr[t_ymin:t_ymax, t_xmin:t_xmax]

                    # Map wreck box to tile coordinates
                    b_xmin = max(0, min(tile_size, xmin - t_xmin))
                    b_xmax = max(0, min(tile_size, xmax - t_xmin))
                    b_ymin = max(0, min(tile_size, ymin - t_ymin))
                    b_ymax = max(0, min(tile_size, ymax - t_ymin))

                    if b_xmax - b_xmin < 10 or b_ymax - b_ymin < 10:
                        continue

                    # Normalized YOLO format (class 0: wreck_debris)
                    y_cx = ((b_xmin + b_xmax) / 2.0) / tile_size
                    y_cy = ((b_ymin + b_ymax) / 2.0) / tile_size
                    y_w = (b_xmax - b_xmin) / tile_size
                    y_h = (b_ymax - b_ymin) / tile_size

                    tile_name = f"{site_name}_{os.path.splitext(basename)[0]}_crop{obj_idx}_{j_idx}"
                    tile_img_path = os.path.join(out_base, split, "images", f"{tile_name}.png")
                    tile_lbl_path = os.path.join(out_base, split, "labels", f"{tile_name}.txt")

                    Image.fromarray(tile).save(tile_img_path)
                    with open(tile_lbl_path, "w") as f:
                        f.write(f"0 {y_cx:.6f} {y_cy:.6f} {y_w:.6f} {y_h:.6f}\n")

                    counts[split] += 1

            # Extract 1-2 negative background tiles (flat seabed / water column) for background learning
            if not has_positives or split == "train":
                neg_x = min(w - tile_size, max(0, int(w * 0.15)))
                neg_y = min(h - tile_size, max(0, int(h * 0.3)))
                neg_tile = img_arr[neg_y:neg_y + tile_size, neg_x:neg_x + tile_size]
                if neg_tile.shape == (tile_size, tile_size):
                    neg_name = f"neg_{os.path.splitext(basename)[0]}"
                    tile_img_path = os.path.join(out_base, split, "images", f"{neg_name}.png")
                    tile_lbl_path = os.path.join(out_base, split, "labels", f"{neg_name}.txt")
                    Image.fromarray(neg_tile).save(tile_img_path)
                    with open(tile_lbl_path, "w") as f:
                        pass # Empty file indicates pure negative background
                    counts["negatives"] += 1

    process_split(train_img_dir, train_lbl_dir, "train")
    process_split(test_img_dir, test_lbl_dir, "test")

    # Write YOLO dataset.yaml
    yaml_content = f"""path: {out_base.replace('\\', '/')}
train: train/images
val: val/images
test: test/images

nc: 1
names: ['wreck_debris']
"""
    with open(os.path.join(out_base, "dataset.yaml"), "w") as f:
        f.write(yaml_content)

    print("\n=== Real Dataset Preparation Complete ===")
    print(f"Output directory: {out_base}")
    print(f"Train tiles: {counts['train']}")
    print(f"Val tiles: {counts['val']}")
    print(f"Test tiles: {counts['test']}")
    print(f"Seabed negatives: {counts['negatives']}")

if __name__ == "__main__":
    prepare_real_dataset()
