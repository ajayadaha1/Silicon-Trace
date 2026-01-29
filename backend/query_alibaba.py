"""Query ALIBABA failures from Silicon Trace"""
import asyncio
from sqlmodel import select, col
from sqlalchemy import cast, String
from database import async_session
from models import Asset

async def query_alibaba_failures():
    async with async_session() as session:
        # Query ALIBABA assets
        print("\n" + "="*70)
        print("ALIBABA FAILURES - DETAILED RESULTS")
        print("="*70 + "\n")
        
        # Query using raw_data JSON field with correct syntax
        query = select(Asset).where(
            cast(Asset.raw_data['Customer'], String).ilike('%alibaba%')
        ).limit(100)
        
        result = await session.execute(query)
        results = result.scalars().all()
        
        if not results:
            print("No ALIBABA records found in database.")
            return
        
        print(f"📊 SUMMARY:")
        print(f"   Total ALIBABA Assets: {len(results)}\n")
        
        # Group by failure type
        failure_types = {}
        for asset in results:
            data = asset.raw_data
            failtype = data.get('Failtype', 'Unknown')
            if failtype not in failure_types:
                failure_types[failtype] = []
            failure_types[failtype].append(asset)
        
        print(f"🔴 FAILURE BREAKDOWN:\n")
        for failtype, assets in sorted(failure_types.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"   {failtype}: {len(assets)} asset(s)")
        
        print(f"\n📋 DETAILED ASSET LIST:\n")
        for i, asset in enumerate(results, 1):
            data = asset.raw_data
            print(f"{i}. Serial: {asset.serial_number}")
            print(f"   Customer: {data.get('Customer', 'N/A')}")
            print(f"   Fail Type: {data.get('Failtype', 'N/A')}")
            print(f"   Priority: {data.get('Priority', 'N/A')}")
            print(f"   Ticket: {data.get('Ticket', 'N/A')}")
            print(f"   Mfg Date Code: {data.get('Mfg Date Code', 'N/A')}")
            print(f"   Part Status: {data.get('Part status', 'N/A')}")
            print()

if __name__ == "__main__":
    asyncio.run(query_alibaba_failures())
