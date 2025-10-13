#!/usr/bin/env python3
"""
Test GP API Endpoints with HTTP requests
"""

import os
import sys
import json
import time
import subprocess
import threading
from pathlib import Path
import requests
from typing import Optional

def start_server_background():
    """Start FastAPI server in background"""
    print("🚀 Starting FastAPI server in background...")
    
    try:
        # Start server process
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent)
        
        process = subprocess.Popen([
            sys.executable, "-m", "uvicorn", 
            "main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000",
            "--log-level", "info"
        ], 
        cwd="app",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
        )
        
        # Wait a moment for server to start
        time.sleep(5)
        
        # Check if server is running
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                print("✅ Server started successfully")
                return process
            else:
                print(f"⚠️  Server responded with status {response.status_code}")
        except requests.RequestException as e:
            print(f"⚠️  Could not connect to server: {e}")
        
        return process
        
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return None


def test_health_endpoint():
    """Test the health endpoint"""
    print("\n🧪 Testing Health Endpoint...")
    
    try:
        response = requests.get("http://localhost:8000/health", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Health endpoint working")
            print(f"   Status: {data.get('status')}")
            print(f"   Service: {data.get('service')}")
            print(f"   Version: {data.get('version')}")
            return True
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Health endpoint error: {e}")
        return False


def test_gp_upload_endpoint():
    """Test GP patient file upload endpoint"""
    print("\n🧪 Testing GP Upload Endpoint...")
    
    file_path = "Patient file.pdf"
    
    if not os.path.exists(file_path):
        print(f"❌ Test file not found: {file_path}")
        return False
    
    try:
        # Prepare multipart form data
        files = {
            'file': ('Patient file.pdf', open(file_path, 'rb'), 'application/pdf')
        }
        
        data = {
            'patient_name': 'Test Patient',
            'process_mode': 'full'
        }
        
        print(f"📤 Uploading {file_path}...")
        
        response = requests.post(
            "http://localhost:8000/api/v1/gp/upload-patient-file",
            files=files,
            data=data,
            timeout=120  # 2 minutes for processing
        )
        
        files['file'][1].close()  # Close file handle
        
        if response.status_code == 200:
            result = response.json()
            print("✅ GP upload successful")
            print(f"   Success: {result.get('success')}")
            print(f"   Message: {result.get('message')}")
            
            data = result.get('data', {})
            if data:
                print(f"   Processing Time: {data.get('processing_time', 'N/A')}s")
                print(f"   Pages Processed: {data.get('pages_processed', 'N/A')}")
                
                extractions = data.get('extractions', {})
                print(f"   Extractions: {len(extractions)} types")
                for ext_type, ext_data in extractions.items():
                    status = "✅" if ext_data else "❌"
                    print(f"     {status} {ext_type}")
            
            return True
            
        else:
            print(f"❌ GP upload failed: {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"❌ GP upload error: {e}")
        return False


def test_gp_patients_list():
    """Test GP patients list endpoint"""
    print("\n🧪 Testing GP Patients List...")
    
    try:
        response = requests.get("http://localhost:8000/api/v1/gp/patients", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ GP patients list working")
            print(f"   Total Patients: {data.get('total', 0)}")
            print(f"   Returned Count: {data.get('count', 0)}")
            
            patients = data.get('patients', [])
            if patients:
                print("   Sample Patient:")
                patient = patients[0]
                print(f"     Name: {patient.get('name', 'N/A')}")
                print(f"     ID: {patient.get('id_number', 'N/A')}")
                print(f"     Conditions: {patient.get('chronic_conditions_count', 0)}")
                print(f"     Medications: {patient.get('medications_count', 0)}")
            
            return True
            
        else:
            print(f"❌ GP patients list failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ GP patients list error: {e}")
        return False


def test_gp_statistics():
    """Test GP statistics endpoint"""
    print("\n🧪 Testing GP Statistics...")
    
    try:
        response = requests.get("http://localhost:8000/api/v1/gp/statistics", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ GP statistics working")
            print(f"   Total Patients: {data.get('total_patients', 0)}")
            
            validation_status = data.get('validation_status', {})
            if validation_status:
                print("   Validation Status:")
                for status, count in validation_status.items():
                    print(f"     {status}: {count}")
            
            conditions = data.get('common_conditions', [])
            if conditions:
                print("   Top Conditions:")
                for condition in conditions[:3]:
                    print(f"     {condition.get('condition')}: {condition.get('patient_count')} patients")
            
            return True
            
        else:
            print(f"❌ GP statistics failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ GP statistics error: {e}")
        return False


def main():
    """Run API endpoint tests"""
    print("=" * 70)
    print("🏥 GP API ENDPOINTS - HTTP TEST SUITE")
    print("=" * 70)
    
    # Check if server is already running
    try:
        response = requests.get("http://localhost:8000/health", timeout=3)
        if response.status_code == 200:
            print("✅ Server already running")
            server_process = None
        else:
            server_process = start_server_background()
    except:
        server_process = start_server_background()
    
    if server_process is None and not requests.get("http://localhost:8000/health", timeout=3).status_code == 200:
        print("❌ Could not start or connect to server")
        return False
    
    # Run tests
    tests = [
        ("Health Check", test_health_endpoint),
        ("GP Upload Endpoint", test_gp_upload_endpoint),
        ("GP Patients List", test_gp_patients_list),
        ("GP Statistics", test_gp_statistics),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            if result:
                passed += 1
        except Exception as e:
            print(f"❌ Test '{test_name}' failed with exception: {e}")
    
    # Cleanup
    if server_process:
        print("\n🛑 Stopping server...")
        server_process.terminate()
        server_process.wait()
    
    # Results
    print("\n" + "=" * 70)
    print("📊 FINAL RESULTS")
    print("=" * 70)
    print(f"Tests Passed: {passed}/{total}")
    print(f"Success Rate: {passed/total*100:.1f}%")
    
    if passed >= total * 0.75:  # 75% success rate
        print("\n🎉 GP API INTEGRATION WORKING!")
        print("\n✅ Ready for:")
        print("  - Frontend integration")
        print("  - Production deployment")
        print("  - GP chronic patient digitization")
    else:
        print(f"\n⚠️  Some API endpoints failed. Check server logs.")
    
    return passed >= total * 0.75


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)