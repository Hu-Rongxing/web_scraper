# -*- coding: utf-8 -*-
"""Bypass Paywalls Clean extension management."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

from .config import (
    BPC_CHROME_ZIP_URL,
    BPC_EXTENSION_PATH,
    BPC_FIREFOX_EXTENSION_PATH,
    BPC_FIREFOX_ZIP_URL,
    BPC_SITES_JS,
    BPC_UPDATE_INTERVAL_SEC,
    BPC_UPDATE_URL,
    logger,
)


class PluginManager:
    """Manage the repo-local Bypass Paywalls Clean extension."""

    def __init__(self):
        self._last_update_check: float = 0.0
        self._supported_domains: Optional[list[str]] = None

    def check_update(self, force: bool = False) -> bool:
        """Check and update the Chrome extension, and ensure Firefox exists."""
        now = time.time()
        if not force and (now - self._last_update_check) < BPC_UPDATE_INTERVAL_SEC:
            logger.debug("BPC update check skipped; last check %.0fs ago", now - self._last_update_check)
            return True

        self._last_update_check = now

        if not BPC_EXTENSION_PATH.exists():
            logger.warning("BPC Chrome extension missing: %s", BPC_EXTENSION_PATH)
            return self._download_extension(BPC_EXTENSION_PATH, [BPC_CHROME_ZIP_URL])

        current_version = self._get_current_version(BPC_EXTENSION_PATH)
        remote_version = self._get_remote_version()
        if remote_version and current_version != remote_version:
            logger.info("BPC Chrome update available: %s -> %s", current_version, remote_version)
            return self._download_extension(BPC_EXTENSION_PATH, [BPC_CHROME_ZIP_URL])

        if not BPC_FIREFOX_EXTENSION_PATH.exists():
            logger.warning("BPC Firefox extension missing: %s", BPC_FIREFOX_EXTENSION_PATH)
            return self._download_extension(BPC_FIREFOX_EXTENSION_PATH, [BPC_FIREFOX_ZIP_URL])

        logger.debug("BPC extension is current: %s", current_version)
        return True

    def _get_current_version(self, extension_path: Path = BPC_EXTENSION_PATH) -> str:
        manifest = extension_path / "manifest.json"
        if not manifest.exists():
            return "unknown"
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            return data.get("version", "unknown")
        except Exception:
            return "unknown"

    def _get_remote_version(self) -> Optional[str]:
        """Fetch the latest Chrome manifest version from known upstreams."""
        urls = [
            "https://gitflic.ru/project/magnolia1234/bpc_uploads/blob/raw?file=manifest.json",
            "https://gitflic.ru/project/magnolia1234/bypass-paywalls-chrome-clean/blob/raw?file=manifest.json",
        ]
        for url in urls:
            try:
                resp = requests.get(url, timeout=15)
                if resp.status_code == 200:
                    data = json.loads(resp.text)
                    version = data.get("version")
                    if version:
                        return version
            except Exception as exc:
                logger.debug("BPC remote version lookup failed for %s: %s", url, exc)
        return None

    def _download_extension(
        self,
        extension_path: Path = BPC_EXTENSION_PATH,
        extra_urls: Optional[list[str]] = None,
    ) -> bool:
        """Download and replace an unpacked BPC extension directory."""
        urls = [
            *(extra_urls or []),
            f"{BPC_UPDATE_URL}/archive/master.zip",
            f"{BPC_UPDATE_URL}/archive/main.zip",
            "https://gitflic.ru/project/magnolia1234/bypass-paywalls-chrome-clean/file/master.zip",
        ]
        for url in dict.fromkeys(urls):
            try:
                logger.info("Downloading BPC from %s", url)
                resp = requests.get(url, timeout=60, stream=True)
                if resp.status_code != 200:
                    continue
                if not self._looks_like_zip(resp):
                    logger.warning("BPC download was not a zip: %s", url)
                    continue

                with tempfile.TemporaryDirectory() as tmp:
                    zip_path = Path(tmp) / "bpc.zip"
                    with open(zip_path, "wb") as fh:
                        for chunk in resp.iter_content(chunk_size=8192):
                            if chunk:
                                fh.write(chunk)

                    with zipfile.ZipFile(zip_path, "r") as zf:
                        root_dir = self._zip_root_dir(zf)
                        if extension_path.exists():
                            backup = extension_path.with_suffix(".backup")
                            if backup.exists():
                                shutil.rmtree(backup, ignore_errors=True)
                            shutil.move(str(extension_path), str(backup))

                        extension_path.mkdir(parents=True, exist_ok=True)
                        for member in zf.namelist():
                            if not member.startswith(root_dir + "/"):
                                continue
                            rel = member[len(root_dir) + 1:]
                            if not rel:
                                continue
                            target = extension_path / rel
                            if member.endswith("/"):
                                target.mkdir(parents=True, exist_ok=True)
                            else:
                                target.parent.mkdir(parents=True, exist_ok=True)
                                with zf.open(member) as src, open(target, "wb") as dst:
                                    dst.write(src.read())

                self._supported_domains = None
                logger.info("BPC updated at %s, version=%s", extension_path, self._get_current_version(extension_path))
                return True
            except Exception as exc:
                logger.warning("BPC download failed from %s: %s", url, exc)

        logger.error("All BPC download sources failed")
        return False

    @staticmethod
    def _looks_like_zip(resp: requests.Response) -> bool:
        ctype = resp.headers.get("content-type", "").lower()
        content_disposition = resp.headers.get("content-disposition", "").lower()
        url_path = urlparse(resp.url).path.lower()
        return "zip" in ctype or "zip" in content_disposition or url_path.endswith(".zip")

    @staticmethod
    def _zip_root_dir(zf: zipfile.ZipFile) -> str:
        for name in zf.namelist():
            if name.endswith("manifest.json") and name.count("/") == 1:
                return name.split("/")[0]
        return zf.namelist()[0].split("/")[0]

    def get_supported_domains(self) -> list[str]:
        """Return domains listed by BPC's sites.js or manifest host permissions."""
        if self._supported_domains is not None:
            return self._supported_domains

        domains: list[str] = []
        if BPC_SITES_JS.exists():
            content = BPC_SITES_JS.read_text(encoding="utf-8")
            for match in re.finditer(r'domain:\s*"([^"]*)"', content):
                domain = match.group(1)
                if domain == "###" or domain.startswith("#") or domain.startswith("###_"):
                    continue
                domains.append(domain)
            for match in re.finditer(r"group:\s*\[([^\]]+)\]", content):
                for domain_match in re.finditer(r'"([^"]+)"', match.group(1)):
                    domains.append(domain_match.group(1))
        else:
            logger.warning("sites.js missing: %s", BPC_SITES_JS)
            manifest = BPC_EXTENSION_PATH / "manifest.json"
            if manifest.exists():
                try:
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                    for host in data.get("host_permissions", []) or data.get("permissions", []):
                        match = re.search(r"\*://\*\.([^/]+)/", host)
                        if match:
                            domains.append(match.group(1))
                except Exception:
                    pass

        self._supported_domains = sorted(set(domains))
        logger.info("BPC supports %d domains", len(self._supported_domains))
        return self._supported_domains

    def is_supported(self, url: str) -> bool:
        """Return whether the URL's domain is listed by BPC."""
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        for supported in self.get_supported_domains():
            if domain == supported or domain.endswith("." + supported):
                return True
        return False

    def verify_extension(self) -> bool:
        """Verify the configured Chrome BPC extension directory."""
        manifest = BPC_EXTENSION_PATH / "manifest.json"
        if not manifest.exists():
            logger.error("manifest.json missing: %s", manifest)
            return False
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if data.get("name") != "Bypass Paywalls Clean":
                logger.warning("Unexpected BPC extension name: %s", data.get("name"))
                return False
            logger.info("BPC extension ready: version=%s path=%s", data.get("version", "unknown"), BPC_EXTENSION_PATH)
            return True
        except Exception as exc:
            logger.error("manifest.json parse failed: %s", exc)
            return False
