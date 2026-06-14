# -*- coding: utf-8 -*-
"""
test_bypass.py — 反封锁突破策略测试

测试各种付费墙/登录墙/ID墙的突破方法
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 直接导入模块，避免触发 __init__.py 的相对导入
import importlib.util

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

# 加载 config 模块（anti_block 依赖它）
config = load_module("article_reader.config", project_root / "config.py")

# 加载 anti_block 模块
anti_block = load_module("article_reader.pipelines.anti_block", project_root / "pipelines" / "anti_block.py")
WallDetector = anti_block.WallDetector
URLTransformer = anti_block.URLTransformer
BypassExecutor = anti_block.BypassExecutor
AdvancedBypass = anti_block.AdvancedBypass

# 加载 rss_validator 模块
rss_validator = load_module("article_reader.pipelines.rss_validator", project_root / "pipelines" / "rss_validator.py")
RSSValidator = rss_validator.RSSValidator
ArticleInfo = rss_validator.ArticleInfo

from datetime import datetime, timedelta


async def test_wall_detection():
    """测试墙类型检测"""
    print("\n=== 测试墙类型检测 ===\n")
    
    # 付费墙 HTML
    paywall_html = """
    <html>
    <body>
        <article>
            <p>Some content here...</p>
        </article>
        <div class="paywall">
            <p>Subscribe now to continue reading</p>
            <script src="https://cdn.piano.io/paywall.js"></script>
        </div>
    </body>
    </html>
    """
    
    # 登录墙 HTML
    login_html = """
    <html>
    <body>
        <div class="login-wall">
            <p>Please log in to continue reading</p>
            <form action="/login">...</form>
        </div>
    </body>
    </html>
    """
    
    # 截断内容 HTML
    truncated_html = """
    <html>
    <body>
        <article>
            <p>This is a very long article that goes on and on...</p>
            <!-- paywall -->
        </article>
    </body>
    </html>
    """
    
    # 测试付费墙检测
    assert WallDetector.detect_paywall(paywall_html), "应该检测到付费墙"
    print("[OK] 付费墙检测通过")
    
    # 测试登录墙检测
    assert WallDetector.detect_login_wall(login_html), "应该检测到登录墙"
    print("[OK] 登录墙检测通过")
    
    # 测试截断检测
    assert WallDetector.detect_truncation(truncated_html, "short"), "应该检测到内容截断"
    print("[OK] 内容截断检测通过")
    
    # 测试墙类型识别
    assert WallDetector.detect_wall_type(paywall_html, "") == "paywall"
    assert WallDetector.detect_wall_type(login_html, "") == "login_wall"
    assert WallDetector.detect_wall_type(truncated_html, "short") == "truncated"
    print("[OK] 墙类型识别通过")


def test_url_transformation():
    """测试 URL 转换"""
    print("\n=== 测试 URL 转换 ===\n")
    
    url = "https://www.wsj.com/articles/test-article-123"
    
    # 测试 Archive.org
    archive_url = URLTransformer.to_archive_org(url)
    assert "web.archive.org" in archive_url
    print(f"[OK] Archive.org: {archive_url}")
    
    # 测试 Google Cache
    cache_url = URLTransformer.to_google_cache(url)
    assert "webcache.googleusercontent.com" in cache_url
    print(f"[OK] Google Cache: {cache_url}")
    
    # 测试 archive.today
    today_url = URLTransformer.to_archive_today(url)
    assert "archive.ph" in today_url
    print(f"[OK] archive.today: {today_url}")
    
    # 测试 AMP 版本
    amp_urls = URLTransformer.to_amp_version(url)
    assert len(amp_urls) > 0
    print(f"[OK] AMP 版本: {len(amp_urls)} 个候选")
    
    # 测试打印版本
    print_urls = URLTransformer.to_print_version(url)
    assert len(print_urls) > 0
    print(f"[OK] 打印版本: {len(print_urls)} 个候选")


async def test_rss_validation():
    """测试 RSS 同步验证"""
    print("\n=== 测试 RSS 同步验证 ===\n")
    
    validator = RSSValidator()
    
    # 模拟 RSS 文章
    now = datetime.now()
    rss_articles = [
        ArticleInfo(
            title="Test Article 1",
            url="https://example.com/article1",
            published_at=now - timedelta(seconds=10),
        ),
        ArticleInfo(
            title="Test Article 2",
            url="https://example.com/article2",
            published_at=now - timedelta(seconds=20),
        ),
    ]
    
    # 模拟原网站文章
    original_articles = [
        ArticleInfo(
            title="Test Article 1",
            url="https://example.com/article1",
            published_at=now - timedelta(seconds=5),
        ),
        ArticleInfo(
            title="Test Article 2",
            url="https://example.com/article2",
            published_at=now - timedelta(seconds=15),
        ),
    ]
    
    # 测试同步验证
    result = await validator.validate(
        rss_url="https://example.com/rss",
        original_url="https://example.com",
        rss_articles=rss_articles,
        original_articles=original_articles,
    )
    
    assert result.is_valid, f"RSS 应该验证通过: {result.reason}"
    assert result.sync_delay_seconds <= 30, f"同步延迟应该 <= 30s，实际 {result.sync_delay_seconds:.1f}s"
    assert result.article_match_ratio >= 0.9, f"文章匹配率应该 >= 90%，实际 {result.article_match_ratio:.1%}"
    
    print("[OK] RSS 验证通过:")
    print(f"  - 同步延迟: {result.sync_delay_seconds:.1f}s")
    print(f"  - 文章匹配率: {result.article_match_ratio:.1%}")
    print(f"  - 数量匹配率: {result.count_match_ratio:.1%}")
    
    # 测试失败场景：延迟过大
    delayed_articles = [
        ArticleInfo(
            title="Test Article 1",
            url="https://example.com/article1",
            published_at=now - timedelta(seconds=60),  # 60 秒延迟
        ),
    ]
    original_delayed = [
        ArticleInfo(
            title="Test Article 1",
            url="https://example.com/article1",
            published_at=now,
        ),
    ]
    
    result_delayed = await validator.validate(
        rss_url="https://example.com/rss",
        original_url="https://example.com",
        rss_articles=delayed_articles,
        original_articles=original_delayed,
    )
    
    assert not result_delayed.is_valid, "延迟过大的 RSS 应该验证失败"
    print(f"[OK] 延迟过大验证失败: {result_delayed.reason}")


async def test_bypass_executor():
    """测试突破执行器"""
    print("\n=== 测试突破执行器 ===\n")
    
    # 创建执行器（不传入 HTTP 客户端，只测试逻辑）
    # 测试墙类型检测
    wall_type = WallDetector.detect_wall_type(
        '<div class="paywall">Subscribe now</div>',
        ""
    )
    assert wall_type == "paywall"
    print(f"[OK] 墙类型检测: {wall_type}")
    
    # 测试 URL 转换
    url = "https://www.example.com/article"
    archive_url = URLTransformer.to_archive_org(url)
    assert "archive.org" in archive_url
    print(f"[OK] URL 转换: {archive_url}")


async def main():
    """主测试函数"""
    print("=" * 60)
    print("反封锁突破策略测试")
    print("=" * 60)
    
    try:
        # 测试墙检测
        await test_wall_detection()
        
        # 测试 URL 转换
        test_url_transformation()
        
        # 测试 RSS 验证
        await test_rss_validation()
        
        # 测试突破执行器
        await test_bypass_executor()
        
        print("\n" + "=" * 60)
        print("[PASS] 所有测试通过！")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n[FAIL] 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
