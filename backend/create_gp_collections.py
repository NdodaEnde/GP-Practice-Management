#!/usr/bin/env python3
"""
Create GP-specific collections in surgiscan database
"""

import os
import asyncio
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

load_dotenv()

async def create_gp_collections():
    """Create GP-specific collections in surgiscan database"""
    
    try:
        # Connect to MongoDB
        mongodb_url = os.getenv("MONGODB_URL")
        db_name = os.getenv("DATABASE_NAME", "surgiscan")
        
        print(f"📡 Connecting to MongoDB...")
        print(f"   Database: {db_name}")
        
        client = AsyncIOMotorClient(mongodb_url)
        db = client[db_name]
        
        # Test connection
        await client.admin.command('ping')
        print(f"✅ Connected to MongoDB!")
        
        # Get existing collections
        existing = await db.list_collection_names()
        print(f"\n📋 Existing collections: {len(existing)}")
        
        # Define GP collections
        gp_collections = {
            "gp_patients": "Validated GP chronic patient records",
            "gp_scanned_documents": "Original scanned patient files (PDFs/images)",
            "gp_parsed_documents": "LandingAI parsed document data",
            "gp_validation_sessions": "Human validation session state"
        }
        
        print(f"\n🔨 Creating GP collections...\n")
        
        # Create collections
        for collection_name, description in gp_collections.items():
            if collection_name not in existing:
                await db.create_collection(collection_name)
                print(f"   ✅ Created: {collection_name}")
                print(f"      → {description}")
            else:
                print(f"   ℹ️  Exists: {collection_name}")
        
        print(f"\n📊 Creating indexes...\n")
        
        # Create indexes for gp_patients
        await db.gp_patients.create_index("patient_id")
        await db.gp_patients.create_index("id_number")
        await db.gp_patients.create_index([("organization_id", 1), ("id_number", 1)])
        print(f"   ✅ Indexed: gp_patients")
        
        # Create indexes for gp_scanned_documents
        await db.gp_scanned_documents.create_index("patient_id")
        await db.gp_scanned_documents.create_index("organization_id")
        await db.gp_scanned_documents.create_index("uploaded_at")
        print(f"   ✅ Indexed: gp_scanned_documents")
        
        # Create indexes for gp_parsed_documents
        await db.gp_parsed_documents.create_index("document_id")
        await db.gp_parsed_documents.create_index("patient_id")
        await db.gp_parsed_documents.create_index("parsed_at")
        print(f"   ✅ Indexed: gp_parsed_documents")
        
        # Create indexes for gp_validation_sessions
        await db.gp_validation_sessions.create_index("session_id")
        await db.gp_validation_sessions.create_index("patient_id")
        await db.gp_validation_sessions.create_index("status")
        print(f"   ✅ Indexed: gp_validation_sessions")
        
        print(f"\n🎉 SUCCESS! All GP collections created in '{db_name}' database!")
        print(f"\n📊 Final collection count: {len(await db.list_collection_names())}")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(create_gp_collections())