#!/usr/bin/env python3
"""
Clear old test documents from GP collections
"""

import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

async def clear_test_data():
    """Clear old test documents"""
    
    client = AsyncIOMotorClient(os.getenv("MONGODB_URL"))
    db = client[os.getenv("DATABASE_NAME")]
    
    print("🧹 Clearing test data...\n")
    
    # Delete test documents
    result1 = await db.gp_scanned_documents.delete_many({
        "organization_id": "test-gp-practice-001"
    })
    print(f"   Deleted {result1.deleted_count} scanned documents")
    
    result2 = await db.gp_parsed_documents.delete_many({
        "organization_id": "test-gp-practice-001"
    })
    print(f"   Deleted {result2.deleted_count} parsed documents")
    
    result3 = await db.gp_validation_sessions.delete_many({
        "organization_id": "test-gp-practice-001"
    })
    print(f"   Deleted {result3.deleted_count} validation sessions")
    
    result4 = await db.gp_patients.delete_many({
        "organization_id": "test-gp-practice-001"
    })
    print(f"   Deleted {result4.deleted_count} test patients")
    
    # Also delete any documents with hardcoded "default_org"
    result5 = await db.gp_scanned_documents.delete_many({
        "organization_id": "default_org"
    })
    print(f"   Deleted {result5.deleted_count} default_org scanned documents")
    
    result6 = await db.gp_parsed_documents.delete_many({
        "organization_id": "default_org"
    })
    print(f"   Deleted {result6.deleted_count} default_org parsed documents")
    
    result7 = await db.gp_validation_sessions.delete_many({
        "organization_id": "default_org"
    })
    print(f"   Deleted {result7.deleted_count} default_org validation sessions")
    
    print("\n✅ All test data cleared!")
    
    # Show remaining counts
    print("📊 Remaining data:")
    scanned_count = await db.gp_scanned_documents.count_documents({})
    parsed_count = await db.gp_parsed_documents.count_documents({})
    session_count = await db.gp_validation_sessions.count_documents({})
    patients_count = await db.gp_patients.count_documents({})
    
    print(f"   Scanned Documents: {scanned_count}")
    print(f"   Parsed Documents: {parsed_count}")
    print(f"   Validation Sessions: {session_count}")
    print(f"   GP Patients: {patients_count}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(clear_test_data())