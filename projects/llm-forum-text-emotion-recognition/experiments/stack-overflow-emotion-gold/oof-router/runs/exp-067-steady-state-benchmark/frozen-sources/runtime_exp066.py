#!/usr/bin/env python3
"""Headless seed-42 Phase A runtime. This module performs no persistent writes."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Protocol

import numpy as np


LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
FEATURE_NAMES = (
    "m1_probability_love",
    "m1_probability_joy",
    "m1_probability_surprise",
    "m1_probability_anger",
    "m1_probability_sadness",
    "m1_probability_fear",
    "m1_mean_binary_entropy",
    "m1_max_binary_entropy",
    "m1_minimum_threshold_margin",
    "m1_predicted_cardinality",
    "m1_highest_probability",
    "m1_lowest_probability",
    "character_length",
    "m1_token_length",
)
PARAMETER_KEYS = {
    "scaler_mean", "scaler_var", "scaler_scale", "classes", "coef", "intercept"
}


class M1Backend(Protocol):
    def predict_probabilities(self, text: str) -> tuple[np.ndarray, int]: ...


class M3Backend(Protocol):
    def predict_probabilities(self, text: str) -> np.ndarray: ...


def stable_sigmoid64(values: np.ndarray | float) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    result = np.empty_like(array)
    positive = array >= 0
    result[positive] = 1.0 / (1.0 + np.exp(-array[positive]))
    exponent = np.exp(array[~positive])
    result[~positive] = exponent / (1.0 + exponent)
    return result


def stable_sigmoid32(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=np.float32)
    result = np.empty_like(array, dtype=np.float32)
    positive = array >= 0
    result[positive] = np.float32(1.0) / (np.float32(1.0) + np.exp(-array[positive]))
    exponent = np.exp(array[~positive])
    result[~positive] = exponent / (np.float32(1.0) + exponent)
    return result


def build_features(
    m1_probabilities: np.ndarray,
    m1_threshold: float,
    character_length: int,
    m1_token_length: int,
) -> np.ndarray:
    probabilities = np.asarray(m1_probabilities, dtype=np.float64)
    if probabilities.shape != (6,) or not np.all(np.isfinite(probabilities)):
        raise ValueError("M1 probabilities must be one finite six-vector")
    if np.any((probabilities < 0) | (probabilities > 1)):
        raise ValueError("M1 probabilities outside [0,1]")
    if type(character_length) is not int or type(m1_token_length) is not int:
        raise TypeError("Runtime lengths must be plain integers")
    if character_length < 0 or m1_token_length <= 0:
        raise ValueError("Runtime lengths are invalid")
    clipped = np.clip(probabilities, 1e-15, 1.0 - 1e-15)
    entropy = -(clipped * np.log(clipped) + (1.0 - clipped) * np.log1p(-clipped))
    result = np.concatenate(
        [
            probabilities,
            np.asarray(
                [
                    np.mean(entropy),
                    np.max(entropy),
                    np.min(np.abs(probabilities - float(m1_threshold))),
                    np.sum(probabilities >= float(m1_threshold)),
                    np.max(probabilities),
                    np.min(probabilities),
                    character_length,
                    m1_token_length,
                ],
                dtype=np.float64,
            ),
        ]
    )
    if result.shape != (14,) or not np.all(np.isfinite(result)):
        raise ValueError("Runtime feature contract failed")
    return result


class RouterBundle:
    def __init__(self, manifest: dict[str, Any], arrays: dict[str, np.ndarray]) -> None:
        if set(arrays) != PARAMETER_KEYS:
            raise ValueError("Router parameter key drift")
        if manifest.get("labels") != list(LABEL_ORDER):
            raise ValueError("Router label order drift")
        if manifest.get("features") != list(FEATURE_NAMES):
            raise ValueError("Router feature order drift")
        self.m1_threshold = float(manifest["thresholds"]["m1"])
        self.m3_threshold = float(manifest["thresholds"]["m3"])
        self.cutoff = float(manifest["operating_point"]["cutoff"])
        self.scaler_mean = np.asarray(arrays["scaler_mean"], dtype=np.float64)
        self.scaler_scale = np.asarray(arrays["scaler_scale"], dtype=np.float64)
        self.classes = np.asarray(arrays["classes"], dtype=np.int64)
        self.coef = np.asarray(arrays["coef"], dtype=np.float64)
        self.intercept = np.asarray(arrays["intercept"], dtype=np.float64)
        if (
            self.scaler_mean.shape != (14,)
            or self.scaler_scale.shape != (14,)
            or self.coef.shape != (1, 14)
            or self.intercept.shape != (1,)
            or not np.array_equal(self.classes, np.asarray([0, 1], dtype=np.int64))
            or np.any(self.scaler_scale <= 0)
        ):
            raise ValueError("Router numeric shape/class/scale drift")
        for value in (self.scaler_mean, self.scaler_scale, self.coef, self.intercept):
            if not np.all(np.isfinite(value)):
                raise ValueError("Router parameter contains non-finite values")

    def route(self, feature_vector: np.ndarray) -> tuple[np.ndarray, float, bool]:
        features = np.asarray(feature_vector, dtype=np.float64)
        if features.shape != (14,):
            raise ValueError("Router requires one 14-vector")
        standardized = (features - self.scaler_mean) / self.scaler_scale
        logit = float(standardized @ self.coef[0] + self.intercept[0])
        score = float(stable_sigmoid64(logit))
        return standardized, score, bool(score >= self.cutoff)


class TorchM1Backend:
    def __init__(self, checkpoint: Path, max_length: int = 256) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        torch.set_num_threads(1)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            if torch.get_num_interop_threads() != 1:
                raise
        self._torch = torch
        self.max_length = int(max_length)
        self.tokenizer = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            checkpoint, local_files_only=True
        )
        self.model.to(torch.device("cpu"))
        self.model.eval()
        if int(self.model.config.num_labels) != 6:
            raise ValueError("M1 output label count drift")
        id2label = [self.model.config.id2label[index] for index in range(6)]
        if id2label != list(LABEL_ORDER):
            raise ValueError("M1 checkpoint label order drift")

    def predict_probabilities(self, text: str) -> tuple[np.ndarray, int]:
        batch = self.tokenizer(
            [text],
            add_special_tokens=True,
            max_length=self.max_length,
            truncation=True,
            padding=True,
            return_attention_mask=True,
            return_tensors="pt",
        )
        token_length = int(batch["attention_mask"][0].sum().item())
        with self._torch.inference_mode():
            logits = self.model(**batch).logits
            probabilities = (
                self._torch.sigmoid(logits).detach().cpu().numpy().astype(np.float32, copy=False)
            )
        if probabilities.shape != (1, 6) or not np.all(np.isfinite(probabilities)):
            raise ValueError("M1 runtime output drift")
        return np.ascontiguousarray(probabilities[0], dtype=np.float32), token_length


def qwen_prompt_ids(tokenizer: Any, prompt: dict[str, Any], text: str, limit: int) -> list[int]:
    def apply(value: str) -> list[int]:
        output = tokenizer.apply_chat_template(
            [
                {"role": "system", "content": prompt["system"]},
                {
                    "role": "user",
                    "content": prompt["user_prefix"] + value + prompt["user_suffix"],
                },
            ],
            tokenize=True,
            return_dict=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        if not isinstance(output, list) or any(type(token) is not int for token in output):
            raise TypeError("M3 tokenizer output drift")
        return output

    full = apply(text)
    if len(full) <= limit:
        selected = full
    else:
        target_ids = tokenizer.encode(text, add_special_tokens=False)
        low, high, selected = 0, len(target_ids), apply("")
        while low <= high:
            middle = (low + high) // 2
            candidate = apply(tokenizer.decode(target_ids[:middle], skip_special_tokens=False))
            if len(candidate) <= limit:
                selected, low = candidate, middle + 1
            else:
                high = middle - 1
    if not selected or len(selected) > limit:
        raise ValueError("M3 runtime length contract failed")
    if not tokenizer.decode(selected).endswith("<think>\n\n</think>\n\n"):
        raise ValueError("M3 empty-think suffix drift")
    return selected


class MlxM3Backend:
    def __init__(
        self,
        base_path: Path,
        adapter_path: Path,
        head_path: Path,
        prompt_path: Path,
        max_length: int = 384,
    ) -> None:
        import mlx.core as mx
        import mlx.nn as nn
        from mlx_lm import load
        from mlx_lm.tuner import linear_to_lora_layers
        from mlx.utils import tree_flatten
        from safetensors.numpy import load_file as load_safetensors

        adapter_arrays = load_safetensors(str(adapter_path))
        head_arrays = load_safetensors(str(head_path))
        if len(adapter_arrays) != 224:
            raise ValueError("M3 adapter tensor count drift")
        if sum(int(value.size) for value in adapter_arrays.values()) != 7_340_032:
            raise ValueError("M3 adapter parameter count drift")
        if set(head_arrays) != {"weight", "bias"}:
            raise ValueError("M3 head tensor keys drift")
        if head_arrays["weight"].shape != (6, 2560) or head_arrays["bias"].shape != (6,):
            raise ValueError("M3 head tensor shape drift")
        self._mx = mx
        self.max_length = int(max_length)
        self.prompt = json.loads(prompt_path.read_text(encoding="utf-8"))
        self.model, self.tokenizer = load(str(base_path), lazy=False)
        self.model.freeze()
        self.model.eval()
        mx.random.seed(42)
        self.head = nn.Linear(2560, 6, bias=True)

        class Wrapper(nn.Module):
            def __init__(inner_self, backbone: Any, head: Any) -> None:
                super().__init__()
                inner_self.backbone = backbone
                inner_self.head = head

            def __call__(inner_self, input_ids: Any) -> Any:
                hidden = inner_self.backbone.model(input_ids)
                return inner_self.head(hidden[:, -1, :].astype(inner_self.head.weight.dtype))

        self.wrapper = Wrapper(self.model, self.head)
        mx.random.seed(100042)
        linear_to_lora_layers(
            self.model,
            16,
            {
                "rank": 8,
                "scale": 20.0,
                "dropout": 0.0,
                "keys": [
                    "self_attn.q_proj",
                    "self_attn.k_proj",
                    "self_attn.v_proj",
                    "self_attn.o_proj",
                    "mlp.gate_proj",
                    "mlp.up_proj",
                    "mlp.down_proj",
                ],
            },
        )
        insertions: list[tuple[int, str]] = []
        for name, module in self.model.named_modules():
            if type(module).__name__ != "LoRALinear":
                continue
            match = re.search(r"(?:^|\.)layers\.(\d+)\.(.+)$", name)
            if not match:
                raise ValueError("M3 unexpected LoRA module path")
            insertions.append((int(match.group(1)), match.group(2)))
        expected = sorted(
            (block, target)
            for block in range(20, 36)
            for target in (
                "self_attn.q_proj",
                "self_attn.k_proj",
                "self_attn.v_proj",
                "self_attn.o_proj",
                "mlp.gate_proj",
                "mlp.up_proj",
                "mlp.down_proj",
            )
        )
        if sorted(insertions) != expected:
            raise ValueError("M3 LoRA insertion contract drift")
        self.model.load_weights(str(adapter_path), strict=False)
        self.head.load_weights(str(head_path), strict=True)
        self.model.eval()
        parameters = [value for _, value in tree_flatten(self.model.trainable_parameters())]
        parameters.extend(value for _, value in tree_flatten(self.head.trainable_parameters()))
        mx.eval(*parameters)

    def predict_probabilities(self, text: str) -> np.ndarray:
        ids = qwen_prompt_ids(self.tokenizer, self.prompt, text, self.max_length)
        logits = self.wrapper(self._mx.array([ids], dtype=self._mx.int32)).astype(
            self._mx.float32
        )
        self._mx.eval(logits)
        values = np.asarray(logits, dtype=np.float32)
        if values.shape != (1, 6) or not np.all(np.isfinite(values)):
            raise ValueError("M3 runtime logits drift")
        probabilities = stable_sigmoid32(values)[0]
        if not np.all(np.isfinite(probabilities)):
            raise ValueError("M3 runtime probability drift")
        return np.ascontiguousarray(probabilities, dtype=np.float32)


class PhaseARuntime:
    def __init__(self, bundle: RouterBundle, m1: M1Backend, m3: M3Backend) -> None:
        self.bundle = bundle
        self.m1 = m1
        self.m3 = m3

    def _record(
        self, text: str, *, allow_qwen: bool, force_m3_evaluation: bool
    ) -> dict[str, Any]:
        if type(text) is not str:
            raise TypeError("predict() requires one Python str")
        m1_probabilities, token_length = self.m1.predict_probabilities(text)
        feature_vector = build_features(
            m1_probabilities, self.bundle.m1_threshold, len(text), token_length
        )
        standardized, route_score, route_eligible = self.bundle.route(feature_vector)
        evaluate_m3 = bool(force_m3_evaluation or (allow_qwen and route_eligible))
        m3_probabilities = self.m3.predict_probabilities(text) if evaluate_m3 else None
        use_m3 = bool(route_eligible and allow_qwen)
        selected_probabilities = m3_probabilities if use_m3 else m1_probabilities
        threshold = self.bundle.m3_threshold if use_m3 else self.bundle.m1_threshold
        prediction = (selected_probabilities >= threshold).astype(np.uint8)
        active_labels = [
            label for label, value in zip(LABEL_ORDER, prediction.tolist()) if value == 1
        ]
        return {
            "m1_probabilities": m1_probabilities,
            "m3_probabilities": m3_probabilities,
            "features": feature_vector,
            "standardized_features": standardized,
            "route_score": route_score,
            "route_eligible": route_eligible,
            "selected_path": 1 if use_m3 else 0,
            "final_prediction": prediction,
            "active_labels": active_labels,
            "neutral": bool(not active_labels),
            "m1_token_length": token_length,
            "character_length": len(text),
        }

    def parity_record(self, text: str) -> dict[str, Any]:
        return self._record(text, allow_qwen=True, force_m3_evaluation=True)

    def predict(
        self,
        text: str,
        allow_qwen: bool = True,
        include_diagnostics: bool = False,
    ) -> dict[str, Any]:
        if type(allow_qwen) is not bool or type(include_diagnostics) is not bool:
            raise TypeError("predict() flags must be bool")
        record = self._record(
            text, allow_qwen=allow_qwen, force_m3_evaluation=False
        )
        result: dict[str, Any] = {
            "prediction": record["final_prediction"].astype(int).tolist(),
            "active_labels": record["active_labels"],
            "neutral": record["neutral"],
            "used_path": "m3" if record["selected_path"] == 1 else "m1",
            "degraded": False,
        }
        if include_diagnostics:
            result["diagnostics"] = {
                "m1_probabilities": record["m1_probabilities"].tolist(),
                "m3_probabilities": (
                    None
                    if record["m3_probabilities"] is None
                    else record["m3_probabilities"].tolist()
                ),
                "features": record["features"].tolist(),
                "standardized_features": record["standardized_features"].tolist(),
                "route_score": record["route_score"],
                "route_eligible": record["route_eligible"],
                "m1_token_length": record["m1_token_length"],
                "character_length": record["character_length"],
            }
        return result


def load_bundle(bundle_path: Path, parameters_path: Path) -> RouterBundle:
    manifest = json.loads(bundle_path.read_text(encoding="utf-8"))
    with np.load(parameters_path, allow_pickle=False) as archive:
        if set(archive.files) != PARAMETER_KEYS:
            raise ValueError("Router NPZ key drift")
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    return RouterBundle(manifest, arrays)


def build_real_runtime(config: dict[str, Any], project_root: Path) -> PhaseARuntime:
    assets = config["runtime_assets"]
    bundle = load_bundle(
        project_root / assets["bundle_manifest"]["path"],
        project_root / assets["bundle_parameters"]["path"],
    )
    m1 = TorchM1Backend(project_root / assets["m1_checkpoint_root"], max_length=256)
    m3 = MlxM3Backend(
        project_root / assets["m3_base_root"],
        project_root / assets["m3_adapter"]["path"],
        project_root / assets["m3_head"]["path"],
        project_root / assets["m3_prompt"]["path"],
        max_length=384,
    )
    return PhaseARuntime(bundle, m1, m3)
