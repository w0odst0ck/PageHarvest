"""
缺口分析 — 配置管理

整合自 product-gap-analyzer，适配 PageHarvest 数据目录结构。

典型场景：
  选品清单 → PageHarvest data/{平台}/上架清单/{门类}/00-选品推荐合集.csv
  在售商品 → 河姆渡 XLSX（需外部提供或放在 data/河姆渡/ 下）
"""

import os


class GapConfig:
    """缺口分析全局配置"""

    # ── 选品清单 ────────────────────────────────────────────────
    listing_folder: str = ""           # 选品清单根目录（空则从命令行指定）
    listing_file_pattern: str = "*.csv"

    # ── 在售商品 ────────────────────────────────────────────────
    inventory_file: str = ""           # 在售商品文件路径（空则自动发现）
    inventory_file_pattern: str = "*.xlsx"

    # ── 输出 ─────────────────────────────────────────────────────
    output_folder: str = ""            # 空 → 输出到 listing_folder
    output_prefix: str = "缺品清单"

    # ── 匹配键 ───────────────────────────────────────────────────
    key_hint: str | None = None        # None = 自动检测

    # ── 模糊匹配 ─────────────────────────────────────────────────
    fuzzy_threshold: int = 55          # 跨平台标题相似度阈值 (0-100)
    batch_size: int = 10000
    high_missing_warn_pct: float = 0.80

    # ── 默认选品清单路径（PageHarvest 数据目录）────────────────
    _data_dir: str = ""

    def __init__(self, data_dir: str = ""):
        self._data_dir = data_dir

    @classmethod
    def from_env(cls, data_dir: str = "") -> "GapConfig":
        """从环境变量构造配置"""
        cfg = cls(data_dir=data_dir)
        cfg.listing_folder = os.getenv("GAP_LISTING_FOLDER", cfg.listing_folder)
        cfg.inventory_file = os.getenv("GAP_INVENTORY_FILE", cfg.inventory_file)
        cfg.output_prefix = os.getenv("GAP_OUTPUT_PREFIX", cfg.output_prefix)
        return cfg

    def resolve_listing_folder(self) -> str:
        """解析选品清单目录（优先命令行 > 环境变量 > 默认路径）"""
        if self.listing_folder:
            return self.listing_folder
        # 尝试在 PageHarvest data/ 下找
        if self._data_dir:
            # 按平台猜测：震坤行上架清单
            candidates = [
                os.path.join(self._data_dir, "ZKH", "震坤行", "上架清单"),
                os.path.join(self._data_dir, "ZKH", "上架清单"),
                os.path.join(self._data_dir, "震坤行", "上架清单"),
            ]
            for p in candidates:
                if os.path.isdir(p):
                    return p
        return ""

    def resolve_inventory_file(self) -> str:
        """解析在售商品文件路径"""
        if self.inventory_file and os.path.exists(self.inventory_file):
            return self.inventory_file
        # 自动发现
        search_dirs = [self._data_dir] if self._data_dir else []
        # 如果 listing_folder 已设置，也搜那里
        if self.listing_folder and os.path.isdir(self.listing_folder):
            parent = os.path.dirname(self.listing_folder)
            if parent not in search_dirs:
                search_dirs.append(parent)
        # 常见路径
        search_dirs.extend([
            os.path.expanduser("~/Downloads"),
            "D:\\Downloads",
            "C:\\Users\\DELL\\Downloads",
        ])
        for d in search_dirs:
            if not d or not os.path.isdir(d):
                continue
            pattern = "河姆渡-all-*.xlsx"
            candidates = []
            for f in os.listdir(d):
                if f.startswith("河姆渡") and f.endswith(".xlsx"):
                    candidates.append(os.path.join(d, f))
            if candidates:
                return sorted(candidates)[-1]  # 最新的
        return ""

    @property
    def resolved_output_folder(self) -> str:
        return self.output_folder or self.resolve_listing_folder()
