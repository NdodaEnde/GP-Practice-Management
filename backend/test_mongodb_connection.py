#!/usr/bin/env python3
"""
Test MongoDB connection to diagnose issues
"""

import os
import asyncio
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

async def test_mongodb_connection():
    """Test MongoDB connection with detailed diagnostics"""
    
    print("🔍 MongoDB Connection Diagnostics")
    print("=" * 50)
    
    # Get connection details
    mongodb_url = os.getenv("MONGODB_URL")
    database_name = os.getenv("DATABASE_NAME", "surgiscan_documents")
    
    print(f"📡 URL: {mongodb_url[:50]}...")
    print(f"🗄️  Database: {database_name}")
    print()
    
    if not mongodb_url:
        print("❌ MONGODB_URL environment variable not found!")
        return False
    
    try:
        print("🔌 Attempting connection...")
        client = AsyncIOMotorClient(mongodb_url, serverSelectionTimeoutMS=10000)
        
        # Test connection with ping
        print("🏓 Testing connection with ping...")
        await client.admin.command('ping')
        print("✅ Connection successful!")
        
        # Test database access
        print(f"🔍 Testing database access: {database_name}")
        db = client[database_name]
        
        # List collections
        collections = await db.list_collection_names()
        print(f"📊 Collections found: {collections or 'None'}")
        
        # Test write operation
        print("✍️  Testing write operation...")
        test_collection = db.test_connection
        result = await test_collection.insert_one({
            "test": True,
            "timestamp": os.environ.get("HOSTNAME", "unknown"),
            "connection_test": True
        })
        print(f"✅ Write successful! Document ID: {result.inserted_id}")
        
        # Clean up test document
        await test_collection.delete_one({"_id": result.inserted_id})
        print("🧹 Test document cleaned up")
        
        client.close()
        print("\n🎉 MongoDB connection is working perfectly!")
        return True
        
    except Exception as e:
        print(f"\n❌ MongoDB connection failed!")
        print(f"💥 Error: {e}")
        print(f"🔧 Error type: {type(e).__name__}")
        
        # Specific diagnostics
        error_str = str(e).lower()
        if "authentication" in error_str:
            print("🔑 This looks like an authentication error. Check username/password.")
        elif "timeout" in error_str:
            print("⏰ This looks like a network timeout. Check network connectivity.")
        elif "ssl" in error_str:
            print("🔒 This looks like an SSL error. Check certificate validation.")
        
        return False

if __name__ == "__main__":
    success = asyncio.run(test_mongodb_connection())
    exit(0 if success else 1)