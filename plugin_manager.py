# -*- coding: utf-8 -*-
"""
article_reader/plugin_manager.py — BPC 插件的更新 & 站点发现
"""

import re
import time
import subprocess
import zipfile
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import requests

from .config import (
    BPC_EXTENSION_PATH,
    BPC_UPDATE_URL,
    BPC_UPDATE_INTERVAL_SEC,
    BPC_SITES_JS,
    logger,
)


class PluginManager:
    """管理 Bypass Paywalls Clean 扩展的生命周期."""

    def __init__(self):
        self._last_update_check: float = 0.0
        self._supported_domains: Optional[list[str]] = None

    # ---- 更新 ----

    def check_update(self, force: bool = False) -> bool:
        """
        检查并更新 BPC 扩展.
        返回 True 表示已更新或无需更新.
        """
        now = time.time()
        if not force and (now - self._last_update_check) < BPC_UPDATE_INTERVAL_SEC:
            logger.debug("BPC 更新时间未到，跳过 (上次 %ds 前)", now - self._last_update_check)
            return True

        self._last_update_check = now

        if not BPC_EXTENSION_PATH.exists():
            logger.warning("BPC 扩展目录不存在, 尝试从源码下载...")
            return self._download_extension()

        # 读当前版本
        current_version = self._get_current_version()
        remote_version = self._get_remote_version()

        if remote_version and current_version != remote_version:
            logger.info("BPC 有新版本: %s -> %s, 更新中...", current_version, remote_version)
            return self._download_extension()

        logger.debug("BPC 已是最新 (%s)", current_version)
        return True

    def _get_current_version(self) -> str:
        manifest = BPC_EXTENSION_PATH / "manifest.json"
        if not manifest.exists():
            return "unknown"
        try:
            import json
            data = json.loads(manifest.read_text(encoding="utf-8"))
            return data.get("version", "unknown")
        except Exception:
            return "unknown"

    def _get_remote_version(self) -> Optional[str]:
        """从 gitflic API 获取最新版本号."""
        try:
            # gitflic 的 raw blob URL
            resp = requests.get(
                "https://gitflic.ru/project/magnolia1234/bypass-paywalls-chrome-clean/blob/raw?file=manifest.json",
                timeout=15,
            )
            if resp.status_code == 200:
                import json
                data = json.loads(resp.text)
                return data.get("version")
        except Exception as e:
            logger.warning("获取 BPC 远程版本失败: %s", e)
        return None

    def _download_extension(self) -> bool:
        """下载并解压最新 BPC 扩展."""
        try:
            # 尝试多个可能的下载源
            urls = [
                f"{BPC_UPDATE_URL}/archive/master.zip",
                f"{BPC_UPDATE_URL}/archive/main.zip",
                # gitflic 的直接下载链接格式
                "https://gitflic.ru/project/magnolia1234/bypass-paywalls-chrome-clean/file/master.zip",
            ]
            for url in urls:
                try:
                    logger.info("尝试下载 BPC: %s", url)
                    resp = requests.get(url, timeout=60, stream=True)
                    if resp.status_code != 200:
                        continue

                    with tempfile.TemporaryDirectory() as tmp:
                        zip_path = Path(tmp) / "bpc.zip"
                        with open(zip_path, "wb") as f:
                            for chunk in resp.iter_content(chunk_size=8192):
                                f.write(chunk)

                        with zipfile.ZipFile(zip_path, "r") as zf:
                            # 找到 manifest.json 所在的根目录
                            root_dir = None
                            for name in zf.namelist():
                                if name.endswith("manifest.json") and name.count("/") == 1:
                                    root_dir = name.split("/")[0]
                                    break

                            if not root_dir:
                                root_dir = zf.namelist()[0].split("/")[0]

                            # 备份旧版本
                            if BPC_EXTENSION_PATH.exists():
                                backup = BPC_EXTENSION_PATH.with_suffix(".backup")
                                if backup.exists():
                                    shutil.rmtree(backup, ignore_errors=True)
                                shutil.move(str(BPC_EXTENSION_PATH), str(backup))

                            # 解压新版本
                            BPC_EXTENSION_PATH.mkdir(parents=True, exist_ok=True)
                            for member in zf.namelist():
                                if member.startswith(root_dir + "/"):
                                    rel = member[len(root_dir) + 1:]
                                    if not rel:
                                        continue
                                    target = BPC_EXTENSION_PATH / rel
                                    if member.endswith("/"):
                                        target.mkdir(parents=True, exist_ok=True)
                                    else:
                                        target.parent.mkdir(parents=True, exist_ok=True)
                                        with zf.open(member) as src, open(target, "wb") as dst:
                                            dst.write(src.read())

                    logger.info("BPC 更新成功! 版本: %s", self._get_current_version())
                    self._supported_domains = None  # 清缓存
                    return True
                except Exception as e:
                    logger.warning("下载 %s 失败: %s", url, e)
                    continue

            logger.error("所有下载源均失败")
            return False
        except Exception as e:
            logger.error("BPC 更新异常: %s", e)
            return False

    # ---- 站点发现 ----

    def get_supported_domains(self) -> list[str]:
        """返回 BPC 支持的所有域名列表."""
        if self._supported_domains is not None:
            return self._supported_domains

        domains: list[str] = []
        if not BPC_SITES_JS.exists():
            logger.warning("sites.js 不存在: %s", BPC_SITES_JS)
            # 用 manifest.json 作为备选
            manifest = BPC_EXTENSION_PATH / "manifest.json"
            if manifest.exists():
                try:
                    import json
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                    for host in data.get("host_permissions", []):
                        m = re.search(r"\*://\*\.([^/]+)/", host)
                        if m:
                            domains.append(m.group(1))
                except Exception:
                    pass
            self._supported_domains = sorted(set(domains))
            return self._supported_domains

        content = BPC_SITES_JS.read_text(encoding="utf-8")

        # 提取 domain 字段
        for m in re.finditer(r'domain:\s*"([^"]*)"', content):
            domain = m.group(1)
            if domain == "###" or domain.startswith("#") or domain.startswith("###_"):
                continue
            domains.append(domain)

        # 提取 group 数组里的域名
        for m in re.finditer(r'group:\s*\[([^\]]+)\]', content):
            group_text = m.group(1)
            for dm in re.finditer(r'"([^"]+)"', group_text):
                domains.append(dm.group(1))

        self._supported_domains = sorted(set(domains))
        logger.info("BPC 共支持 %d 个域名", len(self._supported_domains))
        return self._supported_domains

    def is_supported(self, url: str) -> bool:
        """检查 URL 是否被 BPC 支持."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        domains = self.get_supported_domains()
        for d in domains:
            if domain == d or domain.endswith("." + d):
                return True
        return False

    def verify_extension(self) -> bool:
        """验证扩展是否可用."""
        manifest = BPC_EXTENSION_PATH / "manifest.json"
        if not manifest.exists():
            logger.error("manifest.json 不存在: %s", manifest)
            return False
        try:
            import json
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if data.get("name") != "Bypass Paywalls Clean":
                logger.warning("扩展名不匹配: %s", data.get("name"))
                return False
            logger.info("BPC 扩展 v%s 就绪", data.get("version", "unknown"))
            return True
        except Exception as e:
            logger.error("manifest.json 解析失败: %s", e)
            return False
