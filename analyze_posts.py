#!/usr/bin/env python3
"""
Script to analyze the extracted Instagram post URLs
"""
import asyncio
from main import analyze_posts_only

async def main():
    print("🔍 Starting post analysis...")
    await analyze_posts_only()

if __name__ == "__main__":
    asyncio.run(main())
