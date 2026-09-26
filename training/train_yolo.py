"""
SagarNetra Training — Sonar Segmentation Network Trainer.
Trains SagarNetraSegNet on 3-channel physics feature stack tiles from sagarnetra_v1.
Outputs:
  - Model weights: artifacts/models/sagarnetra_seg_quick.pt
  - Metrics JSON:  artifacts/metrics/m6_model_metrics.json
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

from backend.sagarnetra.detect.yolo_onnx import SagarNetraSegNet
from sonarforge.dataset_builder import CLASS_NAMES, CLASS_TO_ID

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class SonarSegDataset(Dataset):
    """
    Dataset loader for SagarNetra 3-channel feature stack images and YOLO polygon labels.
    """
    def __init__(self, split_dir: Path, img_size: int = 512, max_samples: Optional[int] = None):
        self.split_dir = Path(split_dir)
        self.img_dir = self.split_dir / "images"
        self.lbl_dir = self.split_dir / "labels"
        self.img_size = img_size

        self.image_files = sorted(list(self.img_dir.glob("*.png")))
        if max_samples is not None:
            self.image_files = self.image_files[:max_samples]

    def __len__(self) -> int:
        return len(self.image_files)

    def _parse_yolo_polygons(self, label_path: Path) -> List[Tuple[int, List[Tuple[float, float]]]]:
        records = []
        if not label_path.exists():
            return records

        with open(label_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 7:  # class_id + at least 3 (x, y) pairs
                    continue
                cls_id = int(parts[0])
                coords = [float(p) for p in parts[1:]]
                pts = [(coords[i] * self.img_size, coords[i + 1] * self.img_size) 
                       for i in range(0, len(coords) - 1, 2)]
                records.append((cls_id, pts))
        return records

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        img_path = self.image_files[idx]
        sample_id = img_path.stem
        lbl_path = self.lbl_dir / f"{sample_id}.txt"

        # Load RGB image (3-channel feature stack: despeckled, shadow, ridge)
        with Image.open(img_path) as pil_img:
            img_arr = np.array(pil_img.convert("RGB"), dtype=np.float32) / 255.0

        if img_arr.shape[:2] != (self.img_size, self.img_size):
            pil_resized = Image.fromarray((img_arr * 255.0).astype(np.uint8)).resize((self.img_size, self.img_size))
            img_arr = np.array(pil_resized, dtype=np.float32) / 255.0

        # [3, H, W]
        img_tensor = torch.from_numpy(img_arr).permute(2, 0, 1).float()

        # Build mask tensor [num_classes, H, W] and class label vector [num_classes]
        num_classes = len(CLASS_NAMES)
        mask_arr = np.zeros((num_classes, self.img_size, self.img_size), dtype=np.float32)
        cls_vec = np.zeros(num_classes, dtype=np.float32)

        instances = self._parse_yolo_polygons(lbl_path)
        for cls_id, pts in instances:
            if 0 <= cls_id < num_classes:
                cls_vec[cls_id] = 1.0
                mask_img = Image.new("1", (self.img_size, self.img_size), 0)
                draw = ImageDraw.Draw(mask_img)
                if len(pts) >= 3:
                    draw.polygon(pts, outline=1, fill=1)
                poly_mask = np.array(mask_img, dtype=np.float32)
                mask_arr[cls_id] = np.maximum(mask_arr[cls_id], poly_mask)

        mask_tensor = torch.from_numpy(mask_arr).float()
        cls_tensor = torch.from_numpy(cls_vec).float()

        return img_tensor, mask_tensor, cls_tensor


def dice_loss(pred_logits: torch.Tensor, target_masks: torch.Tensor, smooth: float = 1e-4) -> torch.Tensor:
    """
    Soft Dice loss over sigmoid probabilities.
    """
    probs = torch.sigmoid(pred_logits)
    intersection = (probs * target_masks).sum(dim=(-2, -1))
    cardinality = probs.sum(dim=(-2, -1)) + target_masks.sum(dim=(-2, -1))
    dice = (2.0 * intersection + smooth) / (cardinality + smooth)
    return 1.0 - dice.mean()


def compute_metrics(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
) -> Dict[str, float]:
    """
    Evaluates mIoU, Dice, and class classification accuracy on a validation dataset.
    """
    model.eval()
    total_intersection = 0.0
    total_union = 0.0
    correct_cls = 0
    total_cls = 0

    with torch.no_grad():
        for imgs, masks, cls_targets in loader:
            imgs = imgs.to(device)
            masks = masks.to(device)
            cls_targets = cls_targets.to(device)

            pred_masks, pred_cls = model(imgs)

            # Segmentation IoU
            prob_masks = torch.sigmoid(pred_masks) > 0.4
            target_bool = masks > 0.5

            intersection = (prob_masks & target_bool).sum().item()
            union = (prob_masks | target_bool).sum().item()

            total_intersection += intersection
            total_union += union

            # Classification accuracy
            cls_preds = (torch.sigmoid(pred_cls) > 0.5).float()
            correct_cls += (cls_preds == cls_targets).sum().item()
            total_cls += cls_targets.numel()

    miou = total_intersection / max(total_union, 1.0)
    cls_acc = correct_cls / max(total_cls, 1)

    return {
        "val_miou": round(float(miou), 4),
        "val_cls_acc": round(float(cls_acc), 4),
    }


def train_sonar_segmenter(
    dataset_dir: str | Path,
    output_dir: str | Path = "artifacts",
    epochs: int = 3,
    batch_size: int = 4,
    lr: float = 1e-3,
    device_name: str = "cpu",
    quick_mode: bool = False,
) -> Dict[str, any]:
    """
    Trains SagarNetraSegNet on the sagarnetra dataset.
    """
    dataset_dir = Path(dataset_dir)
    output_dir = Path(output_dir)
    models_dir = output_dir / "models"
    metrics_dir = output_dir / "metrics"
    models_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device(device_name)
    logger.info("Using compute device: %s", device)

    train_set = SonarSegDataset(dataset_dir / "train", max_samples=20 if quick_mode else None)
    val_set = SonarSegDataset(dataset_dir / "val", max_samples=10 if quick_mode else None)
    test_set = SonarSegDataset(dataset_dir / "test", max_samples=10 if quick_mode else None)

    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_set, batch_size=batch_size, shuffle=False)

    model = SagarNetraSegNet(num_classes=len(CLASS_NAMES)).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)

    cls_criterion = nn.BCEWithLogitsLoss()
    mask_bce_criterion = nn.BCEWithLogitsLoss()

    metrics_history = []

    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0

        for imgs, masks, cls_targets in train_loader:
            imgs = imgs.to(device)
            masks = masks.to(device)
            cls_targets = cls_targets.to(device)

            optimizer.zero_grad()
            pred_masks, pred_cls = model(imgs)

            loss_cls = cls_criterion(pred_cls, cls_targets)
            loss_mask_bce = mask_bce_criterion(pred_masks, masks)
            loss_mask_dice = dice_loss(pred_masks, masks)

            loss = loss_cls + 2.0 * loss_mask_bce + 1.5 * loss_mask_dice
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * len(imgs)

        train_loss = running_loss / max(len(train_set), 1)
        val_eval = compute_metrics(model, val_loader, device)

        logger.info(
            f"Epoch [{epoch:02d}/{epochs:02d}] - Train Loss: {train_loss:.4f} | "
            f"Val mIoU: {val_eval['val_miou']:.4f} | Val Acc: {val_eval['val_cls_acc']:.4f}"
        )
        metrics_history.append({
            "epoch": epoch,
            "train_loss": round(train_loss, 4),
            **val_eval,
        })

    # Final evaluation on test split
    test_eval = compute_metrics(model, test_loader, device)
    logger.info("Test split results: %s", test_eval)

    # Save model weights
    save_path = models_dir / ("sagarnetra_seg_quick.pt" if quick_mode else "sagarnetra_seg.pt")
    torch.save({
        "state_dict": model.state_dict(),
        "num_classes": len(CLASS_NAMES),
        "class_names": CLASS_NAMES,
        "input_channels": 3,
    }, save_path)
    logger.info("Saved trained model to %s", save_path)

    # Save metrics JSON
    metrics_summary = {
        "model_architecture": "SagarNetraSegNet",
        "num_parameters": sum(p.numel() for p in model.parameters()),
        "quick_mode": quick_mode,
        "epochs": epochs,
        "test_miou": test_eval["val_miou"],
        "test_cls_accuracy": test_eval["val_cls_acc"],
        "class_names": CLASS_NAMES,
        "history": metrics_history,
    }
    metrics_path = metrics_dir / "m6_model_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_summary, f, indent=2)
    logger.info("Saved metrics to %s", metrics_path)

    return metrics_summary


def main():
    parser = argparse.ArgumentParser(description="Train SagarNetra Sonar Segmentation Model")
    parser.add_argument("--dataset-dir", type=str, default="data/datasets/sagarnetra_v1")
    parser.add_argument("--output-dir", type=str, default="artifacts")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--quick", action="store_true", help="Quick mode with reduced samples and epochs")
    args = parser.parse_args()

    train_sonar_segmenter(
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        quick_mode=args.quick,
    )


if __name__ == "__main__":
    main()
