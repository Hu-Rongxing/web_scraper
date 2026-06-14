#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_pipelines.py - 五级管线完整测试脚本

测试管线1-5的完整功能：
- 管线1: HTTP轻量（curl_cffi）
- 管线2: 基础渲染（CloakBrowser Pool A）
- 管线3: 高防护（CloakBrowser Pool B）
- 管线4: 付费墙（CloakBrowser Pool C）
- 管线5: 兜底链路（nodriver）
"""

import asyncio
import sys
from path_setup import add_src_to_path

import pytest

pytestmark = pytest.mark.asyncio

# 添加项目根目录到路径
add_src_to_path()

from article_reader import (
    PipelineManager,
    Pipeline5Manager,
    PipelineLevel,
)


async def test_pipeline_1():
    """测试管线1: HTTP轻量"""
    print("\n" + "="*60)
    print("测试管线1: HTTP轻量 (curl_cffi)")
    print("="*60)
    
    manager = PipelineManager()
    await manager.start()
    
    try:
        # 测试简单静态页面
        url = "https://httpbin.org/html"
        print(f"\n抓取URL: {url}")
        
        result = await manager.fetch(
            url=url,
            pipeline_level=PipelineLevel.HTTP,
            extract_strategy="trafilatura"
        )
        
        print(f"成功: {result.success}")
        print(f"方法: {result.method}")
        print(f"耗时: {result.elapsed_ms:.2f}ms")
        print(f"内容长度: {result.length}")
        print(f"标题: {result.title[:50] if result.title else 'N/A'}")
        
        if result.content:
            print(f"内容预览: {result.content[:100]}...")
        
        return result.success
    finally:
        await manager.shutdown()


async def test_pipeline_2():
    """测试管线2: 基础渲染"""
    print("\n" + "="*60)
    print("测试管线2: 基础渲染 (CloakBrowser Pool A)")
    print("="*60)
    
    manager = PipelineManager()
    await manager.start()
    
    try:
        # 测试需要JS渲染的页面
        url = "https://httpbin.org/html"
        print(f"\n抓取URL: {url}")
        
        result = await manager.fetch(
            url=url,
            pipeline_level=PipelineLevel.BASIC_RENDER,
            extract_strategy="trafilatura"
        )
        
        print(f"成功: {result.success}")
        print(f"方法: {result.method}")
        print(f"耗时: {result.elapsed_ms:.2f}ms")
        print(f"内容长度: {result.length}")
        print(f"标题: {result.title[:50] if result.title else 'N/A'}")
        
        if result.content:
            print(f"内容预览: {result.content[:100]}...")
        
        return result.success
    finally:
        await manager.shutdown()


async def test_pipeline_3():
    """测试管线3: 高防护"""
    print("\n" + "="*60)
    print("测试管线3: 高防护 (CloakBrowser Pool B)")
    print("="*60)
    
    manager = PipelineManager()
    await manager.start()
    
    try:
        # 测试有反爬保护的页面
        url = "https://httpbin.org/html"
        print(f"\n抓取URL: {url}")
        
        result = await manager.fetch(
            url=url,
            pipeline_level=PipelineLevel.HIGH_PROTECT,
            extract_strategy="trafilatura"
        )
        
        print(f"成功: {result.success}")
        print(f"方法: {result.method}")
        print(f"耗时: {result.elapsed_ms:.2f}ms")
        print(f"内容长度: {result.length}")
        print(f"标题: {result.title[:50] if result.title else 'N/A'}")
        
        if result.content:
            print(f"内容预览: {result.content[:100]}...")
        
        return result.success
    finally:
        await manager.shutdown()


async def test_pipeline_4():
    """测试管线4: 付费墙"""
    print("\n" + "="*60)
    print("测试管线4: 付费墙 (CloakBrowser Pool C)")
    print("="*60)
    
    manager = PipelineManager()
    await manager.start()
    
    try:
        # 测试付费墙页面（示例）
        url = "https://httpbin.org/html"
        print(f"\n抓取URL: {url}")
        
        result = await manager.fetch(
            url=url,
            pipeline_level=PipelineLevel.PAYWALL,
            extract_strategy="trafilatura"
        )
        
        print(f"成功: {result.success}")
        print(f"方法: {result.method}")
        print(f"耗时: {result.elapsed_ms:.2f}ms")
        print(f"内容长度: {result.length}")
        print(f"标题: {result.title[:50] if result.title else 'N/A'}")
        
        if result.content:
            print(f"内容预览: {result.content[:100]}...")
        
        return result.success
    finally:
        await manager.shutdown()


async def test_pipeline_5():
    """测试管线5: 兜底链路"""
    print("\n" + "="*60)
    print("测试管线5: 兜底链路 (nodriver)")
    print("="*60)
    
    manager = Pipeline5Manager()
    await manager.start()
    
    try:
        # 测试兜底链路
        url = "https://httpbin.org/html"
        print(f"\n抓取URL: {url}")
        
        result = await manager.fetch(
            url=url,
            extract_strategy="trafilatura"
        )
        
        print(f"成功: {result.success}")
        print(f"方法: {result.method}")
        print(f"耗时: {result.elapsed_ms:.2f}ms")
        print(f"内容长度: {result.length}")
        print(f"标题: {result.title[:50] if result.title else 'N/A'}")
        
        if result.content:
            print(f"内容预览: {result.content[:100]}...")
        
        return result.success
    finally:
        await manager.shutdown()


async def test_auto_escalation():
    """测试自动升级机制"""
    print("\n" + "="*60)
    print("测试自动升级: 管线1 → 管线2 → 管线3 → 管线4")
    print("="*60)
    
    manager = PipelineManager()
    await manager.start()
    
    try:
        # 使用一个可能需要升级的URL
        url = "https://httpbin.org/html"
        print(f"\n抓取URL: {url}")
        
        result = await manager.fetch(
            url=url,
            pipeline_level=PipelineLevel.HTTP,  # 从管线1开始
            extract_strategy="trafilatura"
        )
        
        print(f"成功: {result.success}")
        print(f"最终管线级别: {result.pipeline_level}")
        print(f"方法: {result.method}")
        print(f"耗时: {result.elapsed_ms:.2f}ms")
        print(f"内容长度: {result.length}")
        
        return result.success
    finally:
        await manager.shutdown()


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("五级管线完整测试")
    print("="*60)
    
    results = {}
    
    # 测试各个管线
    results["管线1"] = await test_pipeline_1()
    results["管线2"] = await test_pipeline_2()
    results["管线3"] = await test_pipeline_3()
    results["管线4"] = await test_pipeline_4()
    results["管线5"] = await test_pipeline_5()
    results["自动升级"] = await test_auto_escalation()
    
    # 打印总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    for name, success in results.items():
        status = "✓ 通过" if success else "✗ 失败"
        print(f"{name}: {status}")
    
    total = len(results)
    passed = sum(1 for s in results.values() if s)
    print(f"\n总计: {passed}/{total} 通过")
    
    return all(results.values())


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
