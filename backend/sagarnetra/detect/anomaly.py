"""
SagarNetra Detection — PatchCore-Lite Anomaly Detector.
Detects unfamiliar underwater anomalies and post-cyclone obstructions:
- Extracts multi-scale patch features using frozen convolutional representations
- Builds a coreset memory bank from seabed-only survey tiles
- Computes kNN distance in patch embedding space to produce an anomaly heatmap
- High anomaly + no known hazard/confuser class -> flags "unknown_manmade"
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class AnomalyResult:
    anomaly_score: float               # Image-level anomaly score in [0.0, 1.0]
    anomaly_map: np.ndarray            # [H, W] float32 spatial anomaly heatmap in [0.0, 1.0]
    is_unknown_manmade: bool           # True if anomaly exceeds threshold
    peak_location: Tuple[int, int]     # (row, col) coordinates of maximum anomaly peak


class PatchFeatureExtractor(nn.Module):
    """
    Lightweight feature extractor computing localized patch embeddings.
    Combines receptive fields at 16x16 and 32x32 strides.
    """
    def __init__(self, in_channels: int = 3, out_dim: int = 64):
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, 32, kernel_size=5, stride=2, padding=2)
        self.bn1 = nn.BatchNorm2d(32)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1)
        self.bn2 = nn.BatchNorm2d(64)
        self.conv3 = nn.Conv2d(64, out_dim, kernel_size=3, stride=2, padding=1)
        self.bn3 = nn.BatchNorm2d(out_dim)
        self.act = nn.ReLU(inplace=True)

        # Freeze weights to ensure stable feature representations
        for p in self.parameters():
            p.requires_grad = False

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: [B, C, H, W]
        Returns:
            patch_embeddings: [B, num_patches, out_dim]
        """
        x1 = self.act(self.bn1(self.conv1(x)))   # H/2, W/2
        x2 = self.act(self.bn2(self.conv2(x1)))  # H/4, W/4
        x3 = self.act(self.bn3(self.conv3(x2)))  # H/8, W/8

        # Upsample x3 to match x2 resolution and concatenate
        x3_up = F.interpolate(x3, size=x2.shape[-2:], mode="bilinear", align_corners=False)
        combined = torch.cat([x2, x3_up], dim=1)  # [B, 64 + out_dim, H/4, W/4]

        # Reshape to [B, H/4 * W/4, channels]
        b, c, h, w = combined.shape
        patches = combined.permute(0, 2, 3, 1).reshape(b, h * w, c)
        # Normalize patch embeddings
        patches = F.normalize(patches, p=2, dim=-1)
        return patches, (h, w)


class PatchCoreLite:
    """
    PatchCore-lite anomaly detector for side-scan sonar.
    Maintains a coreset memory bank of nominal seabed acoustic textures.
    """
    def __init__(self, memory_bank_path: Optional[str | Path] = None):
        self.extractor = PatchFeatureExtractor(in_channels=3, out_dim=64)
        self.extractor.eval()
        self.memory_bank: Optional[np.ndarray] = None  # Shape: [N_core, embedding_dim]
        self.anomaly_threshold: float = 0.45

        if memory_bank_path is not None:
            self.load_memory_bank(memory_bank_path)

    def build_memory_bank(
        self,
        nominal_feature_stacks: list[np.ndarray],
        coreset_ratio: float = 0.05,
        seed: int = 42,
    ) -> None:
        """
        Extracts patch embeddings from nominal seabed tiles and applies random
        coreset subsampling to build the memory bank.
        """
        rng = np.random.default_rng(seed)
        all_patches = []

        with torch.no_grad():
            for feat in nominal_feature_stacks:
                tensor = torch.from_numpy(feat).permute(2, 0, 1).unsqueeze(0).float()
                # Downsample to 256x256 if larger to keep memory light
                if tensor.shape[-1] > 256:
                    tensor = F.interpolate(tensor, size=(256, 256), mode="bilinear", align_corners=False)
                patches, _ = self.extractor(tensor)
                all_patches.append(patches.squeeze(0).numpy())

        if not all_patches:
            raise ValueError("No patches extracted from nominal tiles")

        stacked = np.concatenate(all_patches, axis=0)  # [Total_patches, Dim]
        n_total = len(stacked)
        n_coreset = max(int(n_total * coreset_ratio), 50)
        n_coreset = min(n_coreset, n_total)

        # Uniform random subsampling for coreset
        chosen_indices = rng.choice(n_total, size=n_coreset, replace=False)
        self.memory_bank = stacked[chosen_indices].astype(np.float32)

    def save_memory_bank(self, save_path: str | Path) -> None:
        if self.memory_bank is None:
            raise ValueError("No memory bank to save")
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, memory_bank=self.memory_bank, threshold=self.anomaly_threshold)

    def load_memory_bank(self, load_path: str | Path) -> None:
        path = Path(load_path)
        if not path.exists():
            raise FileNotFoundError(f"Memory bank file not found: {path}")
        data = np.load(path)
        self.memory_bank = data["memory_bank"]
        if "threshold" in data:
            self.anomaly_threshold = float(data["threshold"])

    def predict_anomaly(
        self,
        feature_stack: np.ndarray,
        k: int = 1,
    ) -> AnomalyResult:
        """
        Computes spatial anomaly heatmap and image-level score for a test tile.
        """
        h_orig, w_orig, _ = feature_stack.shape

        if self.memory_bank is None:
            # If no memory bank trained yet, return baseline zero anomaly
            return AnomalyResult(
                anomaly_score=0.0,
                anomaly_map=np.zeros((h_orig, w_orig), dtype=np.float32),
                is_unknown_manmade=False,
                peak_location=(0, 0),
            )

        with torch.no_grad():
            tensor = torch.from_numpy(feature_stack).permute(2, 0, 1).unsqueeze(0).float()
            if tensor.shape[-1] > 256:
                tensor = F.interpolate(tensor, size=(256, 256), mode="bilinear", align_corners=False)
            patches, (grid_h, grid_w) = self.extractor(tensor)
            query_patches = patches.squeeze(0).numpy()  # [N_query, Dim]

        # Compute minimum Euclidean distance to memory bank patches
        # ||q - m||^2 = ||q||^2 + ||m||^2 - 2 q.m = 2 - 2 q.m (since L2-normalized)
        sim = query_patches @ self.memory_bank.T  # [N_query, N_core]
        max_sim = np.max(sim, axis=1)             # Nearest neighbor cosine similarity
        dist = np.sqrt(np.maximum(2.0 - 2.0 * max_sim, 0.0))  # L2 distance

        # Reshape to 2D grid
        grid_map = dist.reshape(grid_h, grid_w).astype(np.float32)

        # Upsample back to original image size
        grid_tensor = torch.from_numpy(grid_map).unsqueeze(0).unsqueeze(0)
        up_tensor = F.interpolate(grid_tensor, size=(h_orig, w_orig), mode="bilinear", align_corners=False)
        anomaly_map = up_tensor.squeeze().numpy()

        # Score normalization to [0, 1] relative to threshold
        p99_score = float(np.percentile(anomaly_map, 99.0))
        norm_score = float(np.clip(p99_score / (self.anomaly_threshold * 1.5), 0.0, 1.0))
        norm_map = np.clip(anomaly_map / (self.anomaly_threshold * 1.5), 0.0, 1.0).astype(np.float32)

        peak_y, peak_x = np.unravel_index(np.argmax(anomaly_map), anomaly_map.shape)
        is_unknown = norm_score >= self.anomaly_threshold

        return AnomalyResult(
            anomaly_score=norm_score,
            anomaly_map=norm_map,
            is_unknown_manmade=is_unknown,
            peak_location=(int(peak_y), int(peak_x)),
        )
