#!/usr/bin/env python3
"""
Check upload status and recent API activity
"""

import requests
import json

def check_backend_status():
    """Check if backend is responding to GP endpoints"""
    
    print("🔍 Checking Backend Status")
    print("=" * 50)
    
    base_url = "http://localhost:5001"
    
    try:
        # Check health
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            print(f"✅ Backend healthy: {health['status']}")
            print(f"📊 MongoDB connected: {health['mongodb_connected']}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return
        
        # Check GP patients endpoint
        try:
            response = requests.get(f"{base_url}/api/v1/gp/patients", timeout=5)
            if response.status_code == 200:
                patients = response.json()
                print(f"👥 GP Patients endpoint working")
                print(f"📋 Patients returned: {len(patients.get('patients', []))}")
                
                if patients.get('patients'):
                    print("🎯 Recent patients:")
                    for patient in patients['patients'][:3]:
                        print(f"   - {patient.get('filename')} (ID: {patient.get('patient_id', 'N/A')})")
                        
            elif response.status_code == 503:
                print("⚠️  GP Patients endpoint: Database not available")
            else:
                print(f"❌ GP Patients endpoint error: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ GP endpoint connection error: {e}")
        
        # Check statistics
        try:
            response = requests.get(f"{base_url}/api/v1/gp/statistics", timeout=5)
            if response.status_code == 200:
                stats = response.json()
                print(f"📈 GP Statistics:")
                print(f"   - Total processed: {stats.get('total_processed', 0)}")
                print(f"   - Validation needed: {stats.get('validation_needed', 0)}")
            else:
                print(f"⚠️  GP Statistics: {response.status_code}")
        except:
            pass
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to backend: {e}")
        print("   Make sure backend is running on http://localhost:5001")

def check_frontend_backend_connection():
    """Check if frontend can reach backend"""
    
    print(f"\n🔌 Testing Frontend→Backend Connection")
    print("=" * 50)
    
    # Test CORS
    try:
        response = requests.options("http://localhost:5001/api/v1/gp/upload-patient-file", 
                                  headers={"Origin": "http://localhost:5173"}, 
                                  timeout=5)
        if response.status_code == 200:
            print("✅ CORS working (frontend can call backend)")
        else:
            print(f"⚠️  CORS might be an issue: {response.status_code}")
    except Exception as e:
        print(f"❌ CORS test failed: {e}")

if __name__ == "__main__":
    check_backend_status()
    check_frontend_backend_connection()
    
    print(f"\n💡 Debugging Tips:")
    print("1. Check if you see any error messages in your browser console")
    print("2. Look at the Network tab during upload to see HTTP requests")
    print("3. Make sure you're uploading from http://localhost:5173")
    print("4. Check that the backend logs show your upload request")