from __future__ import annotations

import csv
import itertools
import re
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import scipy.io as sio

from src.models.metrics_calc import normalize_rows


class matFileConverter:
    """mat -> csv 转换器（单文件/多维）"""

    AUTO_TOKEN_SET = {"", "auto", "自动", "自动选择"}
    SPECTRUM_KEYWORDS = ["spec", "spectrum", "abs", "ext"]
    LAMBDA_KEYWORDS = ["lam", "lambda", "wave", "wavelength", "wl"]
    PARAM_KEYWORDS = [
        "index",
        "param",
        "ri",
        "radius",
        "diam",
        "height",
        "width",
        "period",
        "gap",
        "thick",
        "length",
    ]

    def _log(self, callback, message: str) -> None:
        if callback is None:
            return
        callback(message)

    def _is_auto_token(self, value: str | None) -> bool:
        if value is None:
            return True
        return value.strip().lower() in self.AUTO_TOKEN_SET

    def _collect_hdf5_datasets(self, path: str) -> dict[str, Any]:
        data: dict[str, Any] = {}
        with h5py.File(path, "r") as f:

            def visitor(name: str, obj: Any) -> None:
                if not isinstance(obj, h5py.Dataset):
                    return
                if name == "#refs#" or name.startswith("#refs#/"):
                    return
                # 只保留完整路径，避免同名短键导致列表重复和误选。
                data[name] = obj[()]

            f.visititems(visitor)
        return data

    def _collect_mat_datasets(self, path: str) -> dict[str, Any]:
        raw = sio.loadmat(path)
        return {k: v for k, v in raw.items() if not k.startswith("__")}

    def _load_data(self, path: str) -> dict[str, Any]:
        try:
            return self._collect_hdf5_datasets(path)
        except Exception:
            return self._collect_mat_datasets(path)

    def _to_scan_array(self, value: Any) -> np.ndarray | None:
        if value is None:
            return None
        arr = np.asarray(value)
        arr = np.squeeze(arr)
        if arr.ndim == 0 or arr.size <= 1:
            return None
        if np.iscomplexobj(arr):
            arr = np.real(arr)
        if arr.dtype.kind in {"O", "S", "U", "V"}:
            try:
                arr = arr.astype(float)
            except Exception:
                return None
        return arr

    def _collect_dataset_entries(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for name, raw in data.items():
            arr = self._to_scan_array(raw)
            if arr is None:
                continue

            vector_like = arr.ndim == 1 or (arr.ndim == 2 and 1 in arr.shape)
            matrix_like = arr.ndim >= 2 and min(arr.shape) > 1
            if not vector_like and not matrix_like:
                continue

            vector_len = 0
            if vector_like:
                vector_len = int(arr.size if arr.ndim == 1 else max(arr.shape))

            entries.append(
                {
                    "name": name,
                    "vector_like": vector_like,
                    "matrix_like": matrix_like,
                    "vector_len": vector_len,
                }
            )
        return entries

    def _split_name_tokens(self, text: str) -> list[str]:
        text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
        parts = re.split(r"[^A-Za-z0-9]+", text.lower())
        return [part for part in parts if part]

    def _keyword_score(self, name: str, keywords: list[str]) -> int:
        if not keywords:
            return 0
        low = name.lower()
        tail_raw = name.split("/")[-1]
        tail = tail_raw.lower()
        all_tokens = self._split_name_tokens(name)
        tail_tokens = self._split_name_tokens(tail_raw)
        score = 0

        for word in keywords:
            word = word.lower().strip()
            if not word:
                continue

            if tail == word:
                score += 10
                continue

            if word in tail_tokens:
                score += 8
                continue

            if word in all_tokens:
                score += 4
                continue

            # 短词（如 "ri"）只允许 token 精确命中，避免把 "variable" 误判为参数变量。
            if len(word) < 3:
                continue

            if tail.startswith(word):
                score += 3
                continue

            if any(token.startswith(word) for token in tail_tokens):
                score += 2
                continue

            if len(word) >= 4 and word in tail:
                score += 1

        return score

    def _rank_candidates(
        self,
        entries: list[dict[str, Any]],
        keywords: list[str],
        predicate,
        keep_unscored: bool = False,
    ) -> list[str]:
        scored: list[tuple[int, str]] = []
        for entry in entries:
            if not predicate(entry):
                continue
            scored.append((self._keyword_score(entry["name"], keywords), entry["name"]))

        if not scored:
            return []

        if not keep_unscored and any(score > 0 for score, _ in scored):
            scored = [(score, name) for score, name in scored if score > 0]

        scored.sort(key=lambda item: (-item[0], item[1].lower()))
        names: list[str] = []
        seen: set[str] = set()
        for _, name in scored:
            if name in seen:
                continue
            seen.add(name)
            names.append(name)
        return names

    def get_available_datasets(self, path: str) -> dict[str, list[str]]:
        empty = {"all": [], "spectrum": [], "lambda": [], "param": []}
        try:
            data = self._load_data(path)
            entries = self._collect_dataset_entries(data)
            if not entries:
                names = sorted(data.keys())
                return {"all": names, "spectrum": names, "lambda": names, "param": names}

            all_names = sorted((entry["name"] for entry in entries), key=str.lower)
            spec_names = self._rank_candidates(
                entries,
                self.SPECTRUM_KEYWORDS,
                lambda e: bool(e["matrix_like"]),
                keep_unscored=True,
            )
            if not spec_names:
                spec_names = self._rank_candidates(entries, [], lambda e: bool(e["matrix_like"]))

            lambda_names = self._rank_candidates(
                entries,
                self.LAMBDA_KEYWORDS,
                lambda e: bool(e["vector_like"]) and int(e["vector_len"]) >= 5,
            )
            if not lambda_names:
                lambda_names = self._rank_candidates(entries, [], lambda e: bool(e["vector_like"]))

            param_names = self._rank_candidates(entries, self.PARAM_KEYWORDS, lambda e: bool(e["vector_like"]))
            if not param_names:
                param_names = self._rank_candidates(entries, [], lambda e: bool(e["vector_like"]))

            return {
                "all": all_names,
                "spectrum": spec_names or all_names,
                "lambda": lambda_names or all_names,
                "param": param_names or all_names,
            }
        except Exception:
            return empty

    def _sanitize_filename_piece(self, text: str) -> str:
        cleaned = re.sub(r'[\\/:*?"<>|]+', "_", text).strip()
        cleaned = cleaned.replace(" ", "_")
        cleaned = re.sub(r"_+", "_", cleaned)
        return cleaned.strip("_")

    def _build_output_suffix(self, spectrum_dataset_name: str | None) -> str:
        if self._is_auto_token(spectrum_dataset_name):
            return ""
        assert spectrum_dataset_name is not None
        tail = spectrum_dataset_name.split("/")[-1].strip()
        safe_tail = self._sanitize_filename_piece(tail)
        if not safe_tail:
            return ""
        return f"_{safe_tail}"

    def build_output_csv_path(
        self,
        mat_file_path: str,
        output_dir_or_path: str,
        spectrum_dataset_name: str | None,
    ) -> Path:
        candidate = Path(output_dir_or_path)
        if candidate.suffix.lower() == ".csv":
            return candidate

        source = Path(mat_file_path)
        output_dir = candidate if output_dir_or_path else source.parent
        suffix = self._build_output_suffix(spectrum_dataset_name)
        return output_dir / f"{source.stem}{suffix}.csv"

    def _pick_key(self, keys: list[str], preferred: str | None, keywords: list[str]) -> str | None:
        if preferred and not self._is_auto_token(preferred):
            if preferred in keys:
                return preferred

            by_tail = [k for k in keys if k.split("/")[-1] == preferred]
            if by_tail:
                return by_tail[0]

            preferred_low = preferred.lower()
            by_ci = [k for k in keys if k.lower() == preferred_low or k.split("/")[-1].lower() == preferred_low]
            if by_ci:
                return by_ci[0]

        for key in sorted(keys, key=len):
            low = key.lower()
            tail = key.split("/")[-1].lower()
            if any(word in low or word in tail for word in keywords):
                return key
        return None

    def _resolve_exact_key(self, keys: list[str], preferred: str | None) -> str | None:
        if self._is_auto_token(preferred):
            return None
        if preferred is None:
            return None
        preferred = preferred.strip()
        if preferred in keys:
            return preferred

        preferred_low = preferred.lower()
        for key in keys:
            key_tail = key.split("/")[-1]
            if key_tail == preferred:
                return key
            if key.lower() == preferred_low or key_tail.lower() == preferred_low:
                return key
        return None

    def _prepare_candidates(self, data: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
        entries = self._collect_dataset_entries(data)
        keys = [entry["name"] for entry in entries]
        fallback_keys = list(data.keys())
        spec_candidates = [entry["name"] for entry in entries if entry["matrix_like"]] or keys or fallback_keys
        vector_candidates = [entry["name"] for entry in entries if entry["vector_like"]] or keys or fallback_keys
        return spec_candidates, vector_candidates, keys or fallback_keys

    def _check_batch_compatibility(
        self,
        mat_file_paths: list[str],
        spectrum_dataset_name: str | None,
        lambda_dataset_name: str | None,
        param_dataset_name: str | None,
        log_callback=None,
    ) -> None:
        if len(mat_file_paths) <= 1:
            return

        profiles: list[dict[str, Any]] = []
        for path in mat_file_paths:
            data = self._load_data(path)
            spec_candidates, vector_candidates, _ = self._prepare_candidates(data)
            if not spec_candidates:
                raise ValueError(f"预检查失败：{Path(path).name} 未检测到可用光谱变量")

            chosen_spec = self._resolve_exact_key(spec_candidates, spectrum_dataset_name)
            if not self._is_auto_token(spectrum_dataset_name) and chosen_spec is None:
                raise ValueError(
                    f"预检查失败：{Path(path).name} 中未找到光谱变量 '{spectrum_dataset_name}'"
                )

            chosen_lambda = self._resolve_exact_key(vector_candidates, lambda_dataset_name)
            if not self._is_auto_token(lambda_dataset_name) and chosen_lambda is None:
                raise ValueError(
                    f"预检查失败：{Path(path).name} 中未找到波长变量 '{lambda_dataset_name}'"
                )

            chosen_param = self._resolve_exact_key(vector_candidates, param_dataset_name)
            if not self._is_auto_token(param_dataset_name) and chosen_param is None:
                raise ValueError(
                    f"预检查失败：{Path(path).name} 中未找到参数变量 '{param_dataset_name}'"
                )

            profiles.append(
                {
                    "file": Path(path).name,
                    "spec_tails": {name.split("/")[-1].lower() for name in spec_candidates},
                    "vector_tails": {name.split("/")[-1].lower() for name in vector_candidates},
                }
            )

        base = profiles[0]
        for profile in profiles[1:]:
            if not (base["spec_tails"] & profile["spec_tails"]):
                raise ValueError(
                    f"预检查失败：{profile['file']} 与 {base['file']} 的光谱变量候选无交集，"
                    "请检查批量文件结构是否一致"
                )

            if self._is_auto_token(lambda_dataset_name):
                if base["vector_tails"] and profile["vector_tails"] and not (base["vector_tails"] & profile["vector_tails"]):
                    self._log(
                        log_callback,
                        f"[预检查警告] {profile['file']} 与 {base['file']} 的波长候选差异较大，建议手动指定波长变量",
                    )

            if self._is_auto_token(param_dataset_name):
                if base["vector_tails"] and profile["vector_tails"] and not (base["vector_tails"] & profile["vector_tails"]):
                    self._log(
                        log_callback,
                        f"[预检查警告] {profile['file']} 与 {base['file']} 的参数候选差异较大，建议手动指定参数变量",
                    )

        self._log(log_callback, f"[预检查] 批量变量一致性检查通过，共 {len(mat_file_paths)} 个文件")

    def _as_float_array(self, value: Any) -> np.ndarray | None:
        if value is None:
            return None
        arr = np.asarray(value)
        if np.iscomplexobj(arr):
            arr = np.real(arr)
        return arr.astype(float)

    def _scale_nm(self, values: np.ndarray) -> np.ndarray:
        if values.size == 0:
            return values
        max_val = float(np.nanmax(values))
        if max_val < 1e-6:
            return values * 1e9
        if max_val < 1:
            return values * 1e3
        return values

    def _orient_2d_spectra(
        self,
        spectra: np.ndarray,
        wlen: int | None,
        plen: int | None,
        log_callback=None,
    ) -> np.ndarray:
        arr = np.asarray(spectra, dtype=float)
        if arr.ndim == 1:
            return arr.reshape(1, -1)
        if arr.ndim > 2:
            arr = arr.reshape(arr.shape[0], -1)

        r, c = arr.shape
        need_t = False
        if wlen is not None:
            if r == wlen and c != wlen:
                need_t = True
            elif c == wlen:
                need_t = False
        if not need_t and plen is not None:
            if c == plen and r != plen:
                need_t = True
        if need_t:
            arr = arr.T
            self._log(log_callback, f"[警告] 自动转置光谱矩阵 -> {arr.shape}")
        return arr

    def _scale_param_values(self, values: np.ndarray, param_name: str) -> tuple[np.ndarray, str]:
        if values.size == 0:
            return values, ""
        if str(param_name).strip().lower() == "index":
            return values, ""
        max_val = float(np.nanmax(values))
        if max_val < 1e-6:
            return values * 1e9, "nm"
        if max_val < 1:
            return values * 1e3, "nm"
        return values, ""

    def convert_single_mat_to_csv(
        self,
        mat_file_path: str,
        output_file_path: str,
        spectrum_dataset_name: str | None = None,
        lambda_dataset_name: str | None = None,
        param_dataset_name: str | None = None,
        log_callback=None,
    ) -> dict[str, Any]:
        data = self._load_data(mat_file_path)
        spec_candidates, vector_candidates, _ = self._prepare_candidates(data)

        spec_key = self._pick_key(spec_candidates, spectrum_dataset_name, self.SPECTRUM_KEYWORDS)
        wl_key = self._pick_key(vector_candidates, lambda_dataset_name, self.LAMBDA_KEYWORDS)
        param_key = self._pick_key(vector_candidates, param_dataset_name, self.PARAM_KEYWORDS)

        if spec_key is None:
            raise ValueError("未找到光谱数据集")

        self._log(log_callback, f"匹配结果: spectrum={spec_key}, lambda={wl_key}, param={param_key}")

        spectra = self._as_float_array(data.get(spec_key))
        wavelengths = self._as_float_array(data.get(wl_key)) if wl_key else None
        params = self._as_float_array(data.get(param_key)) if param_key else None

        wlen = int(np.asarray(wavelengths).size) if wavelengths is not None else None
        plen = int(np.asarray(params).size) if params is not None else None
        spectra = self._orient_2d_spectra(spectra, wlen, plen, log_callback)

        n_samples, n_wavs = spectra.shape

        if wavelengths is None:
            wavelengths = np.arange(n_wavs, dtype=float)
        else:
            wavelengths = np.asarray(wavelengths, dtype=float).reshape(-1)
            wavelengths = self._scale_nm(wavelengths)
            if len(wavelengths) > n_wavs:
                wavelengths = wavelengths[:n_wavs]
            elif len(wavelengths) < n_wavs:
                wavelengths = np.pad(wavelengths, (0, n_wavs - len(wavelengths)), mode="edge")

        if params is None:
            params = np.zeros(n_samples, dtype=float)
            param_name = "Parameter"
        else:
            params = np.asarray(params, dtype=float).reshape(-1)
            param_name = param_key.split("/")[-1] if param_key else "Parameter"
            params, _ = self._scale_param_values(params, param_name)
            if len(params) > n_samples:
                params = params[:n_samples]
            elif len(params) < n_samples:
                params = np.pad(params, (0, n_samples - len(params)), mode="edge")

        target = Path(output_file_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        header = wavelengths.tolist() + [param_name]
        with target.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for i in range(n_samples):
                writer.writerow(spectra[i].tolist() + [params[i]])

        n_dir = target.parent / "Ncsv"
        n_dir.mkdir(parents=True, exist_ok=True)
        norm_path = n_dir / f"{target.stem}N.csv"
        norm = normalize_rows(spectra)
        with norm_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for i in range(n_samples):
                writer.writerow(norm[i].tolist() + [params[i]])

        self._log(log_callback, f"已输出: {target}")
        self._log(log_callback, f"归一化输出: {norm_path}")
        return {
            "success": True,
            "output_csv": str(target),
            "normalized_csv": str(norm_path),
            "used_datasets": {
                "spectrum": spec_key,
                "lambda": wl_key,
                "param": param_key,
            },
        }

    def batch_convert_single_mat_to_csv(
        self,
        mat_file_paths: list[str],
        output_dir: str,
        **kwargs,
    ) -> dict[str, Any]:
        success = 0
        failed = 0
        details: list[dict[str, Any]] = []
        spec_name = kwargs.get("spectrum_dataset_name")
        lambda_name = kwargs.get("lambda_dataset_name")
        param_name = kwargs.get("param_dataset_name")
        log_callback = kwargs.get("log_callback")

        self._check_batch_compatibility(
            mat_file_paths=mat_file_paths,
            spectrum_dataset_name=spec_name,
            lambda_dataset_name=lambda_name,
            param_dataset_name=param_name,
            log_callback=log_callback,
        )

        for path in mat_file_paths:
            source = Path(path)
            output = self.build_output_csv_path(str(source), output_dir, spec_name)
            try:
                result = self.convert_single_mat_to_csv(
                    mat_file_path=str(source),
                    output_file_path=str(output),
                    **kwargs,
                )
                success += 1
                details.append({"file": str(source), "result": result, "ok": True})
            except Exception as exc:
                failed += 1
                details.append({"file": str(source), "error": str(exc), "ok": False})

        return {"success_count": success, "failed_count": failed, "details": details}

    def convert_multidim_mat_to_csv(
        self,
        mat_file_path: str,
        output_dir: str,
        spectrum_dataset_name: str | None,
        lambda_dataset_name: str | None,
        param_dataset_names: list[str],
        log_callback=None,
    ) -> dict[str, Any]:
        data = self._load_data(mat_file_path)
        spec_candidates, vector_candidates, _ = self._prepare_candidates(data)

        spec_key = self._pick_key(spec_candidates, spectrum_dataset_name, self.SPECTRUM_KEYWORDS)
        wl_key = self._pick_key(vector_candidates, lambda_dataset_name, self.LAMBDA_KEYWORDS)
        if spec_key is None:
            raise ValueError("未找到光谱数据集")

        selected_params: list[str] = []
        for name in param_dataset_names:
            if name in vector_candidates:
                selected_params.append(name)
            else:
                match = next((k for k in vector_candidates if k.split("/")[-1] == name), None)
                if match:
                    selected_params.append(match)
        if not selected_params:
            raise ValueError("请至少选择一个参数数据集")

        self._log(
            log_callback,
            f"匹配结果: spectrum={spec_key}, lambda={wl_key}, params={selected_params}",
        )

        spectra = self._as_float_array(data[spec_key])
        if spectra is None or spectra.ndim < 2:
            raise ValueError("光谱数据维度不足（至少二维）")

        wavelengths = self._as_float_array(data.get(wl_key)) if wl_key else None
        if wavelengths is not None:
            wavelengths = np.asarray(wavelengths, dtype=float).reshape(-1)
            wavelengths = self._scale_nm(wavelengths)

            axis_match = [i for i, size in enumerate(spectra.shape) if size == len(wavelengths)]
            if axis_match and axis_match[-1] != spectra.ndim - 1:
                spectra = np.moveaxis(spectra, axis_match[-1], -1)

        n_wavs = int(spectra.shape[-1])
        if wavelengths is None:
            wavelengths = np.arange(n_wavs, dtype=float)
        else:
            if len(wavelengths) > n_wavs:
                wavelengths = wavelengths[:n_wavs]
            elif len(wavelengths) < n_wavs:
                wavelengths = np.pad(wavelengths, (0, n_wavs - len(wavelengths)), mode="edge")

        spectra_flat = spectra.reshape(-1, n_wavs, order="F")
        total_rows = len(spectra_flat)

        param_arrays = [np.asarray(data[name]).reshape(-1, order="F") for name in selected_params]
        lengths = [len(arr) for arr in param_arrays]

        if all(length == total_rows for length in lengths):
            param_matrix = np.column_stack([arr[:total_rows] for arr in param_arrays])
        else:
            self._log(
                log_callback,
                f"[警告] 光谱展平行数={total_rows}，参数长度={lengths}，将按参数组合重建并对齐行数",
            )
            rows = []
            for combo in itertools.islice(itertools.product(*param_arrays), total_rows):
                rows.append(combo)
            param_matrix = np.asarray(rows, dtype=object)

        min_len = min(total_rows, len(param_matrix))
        if min_len <= 0:
            raise ValueError("转换失败：光谱或参数数据为空，无法生成输出")
        if min_len < total_rows or min_len < len(param_matrix):
            self._log(
                log_callback,
                f"[警告] 数据行数不一致：光谱={total_rows}，参数={len(param_matrix)}，已截断到 {min_len} 行",
            )
        spectra_flat = spectra_flat[:min_len]
        param_matrix = param_matrix[:min_len]

        for col, name in enumerate(selected_params):
            col_values = []
            for value in param_matrix[:, col]:
                try:
                    col_values.append(float(value))
                except Exception:
                    col_values = []
                    break
            if not col_values:
                continue
            unit_name = name.split("/")[-1]
            scaled, _ = self._scale_param_values(np.asarray(col_values, dtype=float), unit_name)
            param_matrix[:, col] = scaled

        target = self.build_output_csv_path(mat_file_path, output_dir, spectrum_dataset_name)
        target.parent.mkdir(parents=True, exist_ok=True)

        header = wavelengths.tolist() + [name.split("/")[-1] for name in selected_params]
        with target.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for i in range(min_len):
                writer.writerow(spectra_flat[i].tolist() + param_matrix[i].tolist())

        n_dir = target.parent / "Ncsv"
        n_dir.mkdir(parents=True, exist_ok=True)
        norm_path = n_dir / f"{target.stem}N.csv"
        norm = normalize_rows(spectra_flat)
        with norm_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for i in range(min_len):
                writer.writerow(norm[i].tolist() + param_matrix[i].tolist())

        self._log(log_callback, f"多维 csv 输出: {target}")
        return {
            "success": True,
            "output_csv": str(target),
            "normalized_csv": str(norm_path),
            "used_datasets": {
                "spectrum": spec_key,
                "lambda": wl_key,
                "params": selected_params,
            },
        }
