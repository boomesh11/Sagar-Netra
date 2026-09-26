"""
SagarNetra Detection — Stage B Sonar Segmentation Network & ONNX Inference Wrapper.
Lightweight segmentation architecture trained on the 3-channel physics feature stack
(ch0: despeckled intensity, ch1: shadow probability, ch2: Sato ridge).
Outputs bounding boxes, class probabilities, and pixel-level segmentation masks.
Supports PyTorch, TorchScript, and ONNX Runtime backends.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from sonarforge.dataset_builder import CLASS_NAMES, CLASS_TO_ID


@dataclass
class SegmentDetection:
    class_id: int
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]    # (row_min, row_max, col_min, col_max)
    mask: np.ndarray                   # [H, W] bool segmentation mask
    is_confuser: bool                  # True if rock, ripple, seagrass, or fish school


class ConvBlock(nn.Module):
    def __init__(self, in_c: int, out_c: int, stride: int = 1):
        super().__init__()
        self.conv = nn.Conv2d(in_c, out_c, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn = nn.BatchNorm2d(out_c)
        self.act = nn.SiLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.bn(self.conv(x)))


class SagarNetraSegNet(nn.Module):
    """
    Lightweight 3-channel Sonar Segmentation Network.
    Optimized for 512x512 feature stacks with low CPU inference latency (< 50 ms).
    """
    def __init__(self, num_classes: int = 10):
        super().__init__()
        self.num_classes = num_classes

        # Encoder (downsampling from 512 -> 256 -> 128 -> 64)
        self.stem = ConvBlock(3, 16, stride=2)       # 256x256
        self.stage1 = ConvBlock(16, 32, stride=2)     # 128x128
        self.stage2 = ConvBlock(32, 64, stride=2)     # 64x64
        self.stage3 = ConvBlock(64, 128, stride=2)    # 32x32

        # Decoder (upsampling back to original resolution)
        self.up1 = nn.ConvTranspose2d(128, 64, kernel_size=2, stride=2)  # 64x64
        self.dec1 = ConvBlock(128, 64)

        self.up2 = nn.ConvTranspose2d(64, 32, kernel_size=2, stride=2)   # 128x128
        self.dec2 = ConvBlock(64, 32)

        self.up3 = nn.ConvTranspose2d(32, 16, kernel_size=2, stride=2)   # 256x256
        self.dec3 = ConvBlock(32, 16)

        self.up4 = nn.ConvTranspose2d(16, 16, kernel_size=2, stride=2)   # 512x512

        # Classification & Mask Heads
        self.mask_head = nn.Conv2d(16, num_classes, kernel_size=1)
        self.cls_head = nn.Sequential(
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten(),
            nn.Linear(128, num_classes),
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: [B, 3, H, W] input tensor
        Returns:
            mask_logits: [B, num_classes, H, W]
            class_logits: [B, num_classes]
        """
        # Encoder
        x0 = self.stem(x)        # 256
        x1 = self.stage1(x0)     # 128
        x2 = self.stage2(x1)     # 64
        x3 = self.stage3(x2)     # 32

        cls_logits = self.cls_head(x3)

        # Decoder with skip connections
        d1 = self.up1(x3)
        d1 = torch.cat([d1, x2], dim=1)
        d1 = self.dec1(d1)

        d2 = self.up2(d1)
        d2 = torch.cat([d2, x1], dim=1)
        d2 = self.dec2(d2)

        d3 = self.up3(d2)
        d3 = torch.cat([d3, x0], dim=1)
        d3 = self.dec3(d3)

        d4 = self.up4(d3)
        mask_logits = self.mask_head(d4)

        return mask_logits, cls_logits


class SonarDetector:
    """
    Inference runner wrapping PyTorch, TorchScript, or ONNX Runtime models.
    """
    def __init__(self, model_path: Optional[str | Path] = None, device: str = "cpu"):
        self.device = torch.device(device)
        self.model: Optional[nn.Module] = None
        self.ort_session = None

        if model_path is not None:
            self.load(model_path)
        else:
            # Initialize default untrained model
            self.model = SagarNetraSegNet(num_classes=len(CLASS_NAMES)).to(self.device)
            self.model.eval()

    def load(self, model_path: str | Path) -> None:
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")

        if path.suffix == ".onnx":
            try:
                import onnxruntime as ort
                self.ort_session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
                return
            except ImportError:
                pass  # Fall back to PyTorch if available

        if path.suffix in [".pt", ".pth"]:
            state = torch.load(path, map_location=self.device, weights_only=True)
            self.model = SagarNetraSegNet(num_classes=len(CLASS_NAMES)).to(self.device)
            if isinstance(state, dict) and "state_dict" in state:
                self.model.load_state_dict(state["state_dict"])
            elif isinstance(state, dict):
                self.model.load_state_dict(state)
            self.model.eval()
        elif path.suffix == ".torchscript":
            self.model = torch.jit.load(str(path), map_location=self.device)
            self.model.eval()

    def predict(
        self,
        feature_stack: np.ndarray,
        conf_threshold: float = 0.25,
        mask_threshold: float = 0.40,
    ) -> List[SegmentDetection]:
        """
        Runs segmentation inference on a [H, W, 3] float32 feature stack.
        
        Returns:
            List of SegmentDetection objects with masks and bounding boxes.
        """
        h_orig, w_orig, c = feature_stack.shape
        # Prepare tensor [1, 3, 512, 512]
        tensor = torch.from_numpy(feature_stack).permute(2, 0, 1).unsqueeze(0).float()
        if (h_orig, w_orig) != (512, 512):
            tensor = F.interpolate(tensor, size=(512, 512), mode="bilinear", align_corners=False)

        if self.ort_session is not None:
            # ONNX Runtime execution
            ort_inputs = {self.ort_session.get_inputs()[0].name: tensor.numpy()}
            ort_outs = self.ort_session.run(None, ort_inputs)
            mask_logits = torch.from_numpy(ort_outs[0])
            cls_logits = torch.from_numpy(ort_outs[1])
        else:
            with torch.no_grad():
                tensor = tensor.to(self.device)
                mask_logits, cls_logits = self.model(tensor)
                mask_logits = mask_logits.cpu()
                cls_logits = cls_logits.cpu()

        # Resize mask logits back to original tile size if necessary
        if (h_orig, w_orig) != (512, 512):
            mask_logits = F.interpolate(mask_logits, size=(h_orig, w_orig), mode="bilinear", align_corners=False)

        probs = torch.sigmoid(cls_logits[0]).numpy()
        mask_probs = torch.sigmoid(mask_logits[0]).numpy()

        from scipy.ndimage import label, find_objects

        detections: List[SegmentDetection] = []

        for class_id in range(len(CLASS_NAMES)):
            cls_conf = float(probs[class_id])
            class_name = CLASS_NAMES[class_id]
            is_confuser = class_id >= 6

            # Check class-specific mask
            binary_mask = mask_probs[class_id] > mask_threshold
            if not np.any(binary_mask):
                continue

            labeled_mask, num_features = label(binary_mask)
            slices = find_objects(labeled_mask)

            for s_idx, s in enumerate(slices, 1):
                if s is None:
                    continue
                r_slice, c_slice = s
                comp_mask = (labeled_mask[s] == s_idx)
                area = int(np.sum(comp_mask))
                if area < 10:  # Minimum area threshold
                    continue

                full_mask = (labeled_mask == s_idx)
                bbox = (r_slice.start, r_slice.stop, c_slice.start, c_slice.stop)

                # Local peak confidence
                peak_conf = float(np.max(mask_probs[class_id][s][comp_mask]))
                final_conf = max(cls_conf, peak_conf)

                if final_conf >= conf_threshold:
                    detections.append(SegmentDetection(
                        class_id=class_id,
                        class_name=class_name,
                        confidence=final_conf,
                        bbox=bbox,
                        mask=full_mask,
                        is_confuser=is_confuser,
                    ))

        return detections
