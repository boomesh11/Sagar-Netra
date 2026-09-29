"""
Unit and integration tests for Milestone 6:
- SagarNetraSegNet forward pass and output dimensions
- SonarDetector inference wrapper
- PatchCoreLite anomaly detector and memory bank
- TorchScript export and numerical parity verification
- SonarSegDataset data loader
"""
from pathlib import Path
import numpy as np
from PIL import Image
import pytest
import torch

from backend.sagarnetra.detect.anomaly import PatchCoreLite, PatchFeatureExtractor
from backend.sagarnetra.detect.yolo_onnx import SagarNetraSegNet, SonarDetector
from training.export_onnx import export_and_verify
from training.train_yolo import SonarSegDataset, dice_loss
from sonarforge.dataset_builder import CLASS_NAMES


def test_segnet_forward_pass():
    """Validates that SagarNetraSegNet outputs correct tensor dimensions."""
    model = SagarNetraSegNet(num_classes=10)
    model.eval()

    dummy_input = torch.randn(2, 3, 512, 512, dtype=torch.float32)
    with torch.no_grad():
        mask_logits, cls_logits = model(dummy_input)

    assert mask_logits.shape == (2, 10, 512, 512), f"Unexpected mask shape: {mask_logits.shape}"
    assert cls_logits.shape == (2, 10), f"Unexpected class shape: {cls_logits.shape}"


def test_sonar_detector_predict():
    """Validates end-to-end inference using SonarDetector."""
    detector = SonarDetector()
    dummy_feature_stack = np.random.uniform(0.0, 1.0, size=(512, 512, 3)).astype(np.float32)

    detections = detector.predict(dummy_feature_stack, conf_threshold=0.1, mask_threshold=0.3)
    assert isinstance(detections, list)

    for det in detections:
        assert 0 <= det.class_id < len(CLASS_NAMES)
        assert det.class_name in CLASS_NAMES
        assert 0.0 <= det.confidence <= 1.0
        assert len(det.bbox) == 4
        assert det.mask.shape == (512, 512)
        assert det.mask.dtype == bool


def test_patchcore_feature_extractor():
    """Validates patch embeddings and normalization."""
    extractor = PatchFeatureExtractor(in_channels=3, out_dim=64)
    extractor.eval()

    dummy_input = torch.randn(1, 3, 256, 256, dtype=torch.float32)
    with torch.no_grad():
        patches, grid_shape = extractor(dummy_input)

    assert patches.dim() == 3  # [B, N_patches, Dim]
    assert patches.shape[0] == 1
    assert grid_shape == (64, 64)
    # Check L2 normalization
    norms = torch.norm(patches, p=2, dim=-1)
    assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)


def test_patchcore_lite_memory_bank_and_predict(tmp_path: Path):
    """Validates building memory bank, saving/loading, and anomaly prediction."""
    detector = PatchCoreLite()

    # Generate 2 synthetic feature stacks
    tile1 = np.random.uniform(0.2, 0.5, size=(256, 256, 3)).astype(np.float32)
    tile2 = np.random.uniform(0.2, 0.5, size=(256, 256, 3)).astype(np.float32)

    detector.build_memory_bank([tile1, tile2], coreset_ratio=0.1, seed=42)
    assert detector.memory_bank is not None
    assert detector.memory_bank.shape[0] > 0

    # Save and reload
    save_file = tmp_path / "test_bank.npz"
    detector.save_memory_bank(save_file)
    assert save_file.exists()

    detector2 = PatchCoreLite(memory_bank_path=save_file)
    assert detector2.memory_bank is not None

    # Predict anomaly on test tile
    test_tile = np.random.uniform(0.2, 0.5, size=(256, 256, 3)).astype(np.float32)
    result = detector2.predict_anomaly(test_tile)

    assert 0.0 <= result.anomaly_score <= 1.0
    assert result.anomaly_map.shape == (256, 256)
    assert len(result.peak_location) == 2


def test_torchscript_export_and_parity(tmp_path: Path):
    """Validates TorchScript tracing and numerical parity check."""
    report = export_and_verify(
        model_path=tmp_path / "non_existent.pt",  # Will use initialized model
        output_dir=tmp_path,
    )
    assert report["torchscript_exported"] is True
    assert report["parity_verified"] is True
    assert report["torchscript_mask_parity_max_diff"] < 1e-3
    assert report["torchscript_cls_parity_max_diff"] < 1e-3


def test_sonar_seg_dataset_loader(tmp_path: Path):
    """Validates SonarSegDataset loading using temporary synthetic dataset directory."""
    img_dir = tmp_path / "images"
    lbl_dir = tmp_path / "labels"
    img_dir.mkdir(parents=True)
    lbl_dir.mkdir(parents=True)

    # Create dummy 512x512 3-channel test PNG
    test_img = Image.fromarray(np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8))
    test_img.save(img_dir / "test_tile_001.png")

    # Create dummy YOLO polygon label (class 0, 4 polygon points)
    with open(lbl_dir / "test_tile_001.txt", "w", encoding="utf-8") as f:
        f.write("0 0.2 0.2 0.5 0.2 0.5 0.6 0.2 0.6\n")

    ds = SonarSegDataset(tmp_path, img_size=512, max_samples=3)
    assert len(ds) == 1

    img_tensor, mask_tensor, cls_tensor = ds[0]
    assert img_tensor.shape == (3, 512, 512)
    assert mask_tensor.shape == (10, 512, 512)
    assert cls_tensor.shape == (10,)
    assert cls_tensor[0] == 1.0
    assert 0.0 <= img_tensor.min() and img_tensor.max() <= 1.0
    assert 0.0 <= mask_tensor.min() and mask_tensor.max() <= 1.0


def test_dice_loss():
    """Validates soft Dice loss calculation."""
    pred = torch.zeros(1, 1, 64, 64)
    target = torch.ones(1, 1, 64, 64)
    loss = dice_loss(pred, target)
    assert loss.item() > 0.0

    # Perfect prediction should yield near-zero loss
    pred_perfect = torch.ones(1, 1, 64, 64) * 20.0  # sigmoid(20) ~ 1.0
    loss_perfect = dice_loss(pred_perfect, target)
    assert loss_perfect.item() < 0.05
