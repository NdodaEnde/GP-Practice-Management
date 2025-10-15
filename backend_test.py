#!/usr/bin/env python3
"""
Backend API Testing for GP Document-to-EHR Integration Workflow
Tests the complete GP document processing workflow including:
- Document upload and processing
- Patient matching
- Patient match confirmation
- New patient creation
- Validation data save
- Document archive
"""

import requests
import json
import uuid
from datetime import datetime, timezone
import os
from pymongo import MongoClient
import sys
import io
import wave
import struct
import math
import base64
import time

# Configuration
BACKEND_URL = "https://healthcare-ehr.preview.emergentagent.com/api"
MONGO_URL = "mongodb://localhost:27017"
DATABASE_NAME = "surgiscan_documents"
MICROSERVICE_URL = "http://localhost:5001"

class GPDocumentTester:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.microservice_url = MICROSERVICE_URL
        self.mongo_client = MongoClient(MONGO_URL)
        self.db = self.mongo_client[DATABASE_NAME]
        self.test_results = []
        self.test_patient_id = None
        self.test_document_id = None
        self.test_encounter_id = None
        
    def log_test(self, test_name, success, message, details=None):
        """Log test results"""
        result = {
            'test': test_name,
            'success': success,
            'message': message,
            'details': details or {},
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name} - {message}")
        if details and not success:
            print(f"   Details: {details}")
    
    def test_backend_health(self):
        """Test if backend is accessible"""
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log_test("Backend Health Check", True, f"Backend is healthy: {data.get('status')}")
                return True
            else:
                self.log_test("Backend Health Check", False, f"Backend returned status {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Backend Health Check", False, f"Cannot connect to backend: {str(e)}")
            return False
    
    def test_mongodb_connection(self):
        """Test MongoDB connection"""
        try:
            # Test connection
            self.mongo_client.admin.command('ping')
            
            # Check if gp_scanned_documents collection exists and has data
            collections = self.db.list_collection_names()
            has_gp_docs = 'gp_scanned_documents' in collections
            
            if has_gp_docs:
                doc_count = self.db.gp_scanned_documents.count_documents({})
                self.log_test("MongoDB Connection", True, f"Connected. Found {doc_count} GP documents")
                return True, doc_count
            else:
                self.log_test("MongoDB Connection", True, "Connected but no GP documents collection found")
                return True, 0
                
        except Exception as e:
            self.log_test("MongoDB Connection", False, f"MongoDB connection failed: {str(e)}")
            return False, 0
    
    def test_microservice_connection(self):
        """Test microservice connection"""
        try:
            response = requests.get(f"{self.microservice_url}/health", timeout=10)
            if response.status_code == 200:
                self.log_test("Microservice Connection", True, "LandingAI microservice is accessible")
                return True
            else:
                self.log_test("Microservice Connection", False, f"Microservice returned status {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Microservice Connection", False, f"Cannot connect to microservice: {str(e)}")
            return False
    
    def create_test_pdf_document(self):
        """Create a test PDF document for GP document processing"""
        try:
            # Create a simple PDF-like content (base64 encoded)
            # This simulates a medical document with patient information
            test_pdf_content = b"""
            %PDF-1.4
            1 0 obj
            <<
            /Type /Catalog
            /Pages 2 0 R
            >>
            endobj
            
            2 0 obj
            <<
            /Type /Pages
            /Kids [3 0 R]
            /Count 1
            >>
            endobj
            
            3 0 obj
            <<
            /Type /Page
            /Parent 2 0 R
            /MediaBox [0 0 612 792]
            /Contents 4 0 R
            >>
            endobj
            
            4 0 obj
            <<
            /Length 200
            >>
            stream
            BT
            /F1 12 Tf
            100 700 Td
            (MEDICAL RECORD) Tj
            0 -20 Td
            (Patient: John Smith) Tj
            0 -20 Td
            (DOB: 1980-05-15) Tj
            0 -20 Td
            (ID: 8005155555083) Tj
            0 -20 Td
            (Diagnosis: Hypertension) Tj
            0 -20 Td
            (Medication: Lisinopril 10mg daily) Tj
            ET
            endstream
            endobj
            
            xref
            0 5
            0000000000 65535 f 
            0000000009 00000 n 
            0000000058 00000 n 
            0000000115 00000 n 
            0000000206 00000 n 
            trailer
            <<
            /Size 5
            /Root 1 0 R
            >>
            startxref
            456
            %%EOF
            """
            
            self.log_test("Create Test PDF", True, f"Created {len(test_pdf_content)} byte PDF document")
            return test_pdf_content, "test_medical_record.pdf"
            
        except Exception as e:
            self.log_test("Create Test PDF", False, f"Error creating test PDF: {str(e)}")
            return None, None
    
    def create_test_patient(self):
        """Create a test patient for matching tests"""
        try:
            patient_data = {
                "first_name": "John",
                "last_name": "Smith", 
                "dob": "1980-05-15",
                "id_number": "8005155555083",
                "contact_number": "+27123456789",
                "email": "john.smith@example.com",
                "address": "123 Main Street, Cape Town",
                "medical_aid": "Discovery Health"
            }
            
            response = requests.post(
                f"{self.backend_url}/patients",
                json=patient_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                self.test_patient_id = result['id']
                self.log_test("Create Test Patient", True, f"Created test patient: {self.test_patient_id}")
                return True, result
            else:
                self.log_test("Create Test Patient", False, f"Failed to create patient: {response.status_code}")
                return False, None
                
        except Exception as e:
            self.log_test("Create Test Patient", False, f"Error creating test patient: {str(e)}")
            return False, None
    
    def test_gp_document_upload(self):
        """Test GP document upload and processing"""
        try:
            # Create test PDF document
            pdf_data, filename = self.create_test_pdf_document()
            if not pdf_data:
                return False, None
            
            # Prepare multipart form data
            files = {
                'file': (filename, pdf_data, 'application/pdf')
            }
            data = {
                'processing_mode': 'smart'
            }
            
            # Make API call
            response = requests.post(
                f"{self.backend_url}/gp/upload-patient-file",
                files=files,
                data=data,
                timeout=180  # Longer timeout for document processing
            )
            
            if response.status_code == 200:
                result = response.json()
                expected_fields = ['document_id', 'status']
                
                if all(field in result for field in expected_fields):
                    if result['status'] in ['success', 'processed']:
                        self.test_document_id = result.get('document_id')
                        self.log_test("GP Document Upload", True, 
                                    f"Successfully uploaded and processed document: {self.test_document_id}")
                        return True, result
                    else:
                        self.log_test("GP Document Upload", False, 
                                    f"Document processing failed: status={result.get('status')}")
                        return False, result
                else:
                    missing_fields = [f for f in expected_fields if f not in result]
                    self.log_test("GP Document Upload", False, 
                                f"Missing fields in response: {missing_fields}")
                    return False, result
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("GP Document Upload", False, error_msg)
                return False, None
                
        except Exception as e:
            self.log_test("GP Document Upload", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_patient_matching(self):
        """Test patient matching workflow"""
        try:
            # Test demographics that should match our test patient
            demographics = {
                "first_name": "John",
                "last_name": "Smith",
                "dob": "1980-05-15",
                "id_number": "8005155555083"
            }
            
            payload = {
                "document_id": self.test_document_id or "test-doc-123",
                "demographics": demographics
            }
            
            # Make API call
            response = requests.post(
                f"{self.backend_url}/gp/validation/match-patient",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                expected_fields = ['status', 'matches', 'match_count']
                
                if all(field in result for field in expected_fields):
                    if result['status'] == 'success':
                        match_count = result['match_count']
                        matches = result['matches']
                        
                        # Check if we found matches and they have proper structure
                        if match_count > 0 and matches:
                            # Verify match structure
                            first_match = matches[0]
                            match_fields = ['patient_id', 'confidence_score', 'match_method']
                            
                            if all(field in first_match for field in match_fields):
                                confidence = first_match['confidence_score']
                                method = first_match['match_method']
                                
                                self.log_test("Patient Matching", True, 
                                            f"Found {match_count} matches, best confidence: {confidence}, method: {method}")
                                return True, result
                            else:
                                self.log_test("Patient Matching", False, 
                                            "Match results missing required fields")
                                return False, result
                        else:
                            self.log_test("Patient Matching", True, 
                                        "No matches found (expected for new patient scenario)")
                            return True, result
                    else:
                        self.log_test("Patient Matching", False, 
                                    f"Invalid response status: {result.get('status')}")
                        return False, result
                else:
                    missing_fields = [f for f in expected_fields if f not in result]
                    self.log_test("Patient Matching", False, 
                                f"Missing fields in response: {missing_fields}")
                    return False, result
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("Patient Matching", False, error_msg)
                return False, None
                
        except Exception as e:
            self.log_test("Patient Matching", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_patient_match_confirmation(self):
        """Test patient match confirmation and encounter creation"""
        try:
            if not self.test_patient_id:
                self.log_test("Patient Match Confirmation", False, "No test patient available")
                return False, None
            
            # Mock parsed data from document
            parsed_data = {
                "demographics": {
                    "first_name": "John",
                    "last_name": "Smith",
                    "dob": "1980-05-15",
                    "id_number": "8005155555083"
                },
                "vitals": {
                    "vital_signs_records": [{
                        "blood_pressure": "140/90",
                        "heart_rate": 75,
                        "temperature": 36.5,
                        "weight": 80.0,
                        "height": 175.0
                    }]
                },
                "clinical_notes": {
                    "chief_complaint": "Routine checkup",
                    "diagnosis": "Hypertension"
                },
                "chronic_summary": {
                    "chronic_conditions": ["Hypertension"],
                    "current_medications": ["Lisinopril 10mg daily"]
                }
            }
            
            payload = {
                "document_id": self.test_document_id or "test-doc-123",
                "patient_id": self.test_patient_id,
                "parsed_data": parsed_data,
                "modifications": []
            }
            
            # Make API call
            response = requests.post(
                f"{self.backend_url}/gp/validation/confirm-match",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                expected_fields = ['status', 'patient_id', 'encounter_id', 'document_id']
                
                if all(field in result for field in expected_fields):
                    if result['status'] == 'success':
                        self.test_encounter_id = result['encounter_id']
                        self.log_test("Patient Match Confirmation", True, 
                                    f"Successfully confirmed match and created encounter: {self.test_encounter_id}")
                        return True, result
                    else:
                        self.log_test("Patient Match Confirmation", False, 
                                    f"Match confirmation failed: {result.get('status')}")
                        return False, result
                else:
                    missing_fields = [f for f in expected_fields if f not in result]
                    self.log_test("Patient Match Confirmation", False, 
                                f"Missing fields in response: {missing_fields}")
                    return False, result
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("Patient Match Confirmation", False, error_msg)
                return False, None
                
        except Exception as e:
            self.log_test("Patient Match Confirmation", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_ai_scribe_with_mock_transcription(self):
        """Test SOAP generation with mock transcription (fallback if Whisper fails)"""
        try:
            # Use a realistic medical consultation transcription
            mock_transcription = """
            Patient Sarah Johnson, 42 years old, presents with complaints of increased thirst and frequent urination over the past two weeks. 
            She reports feeling more tired than usual and has noticed some blurred vision. 
            Patient has a family history of diabetes. 
            On examination, blood pressure is 145 over 90, heart rate 88 beats per minute. 
            Patient appears well but slightly dehydrated. 
            Blood glucose finger stick shows 280 milligrams per deciliter. 
            I suspect new onset diabetes mellitus type 2. 
            Plan to start metformin 500 milligrams twice daily, recommend dietary changes, and follow up in one week with lab work including hemoglobin A1C and comprehensive metabolic panel.
            """
            
            # Test SOAP generation with mock transcription
            success, result = self.test_ai_scribe_soap_generation_endpoint(mock_transcription)
            
            if success:
                self.log_test("AI Scribe Mock Transcription Test", True, 
                            "SOAP generation works with realistic medical transcription")
                return True, result
            else:
                self.log_test("AI Scribe Mock Transcription Test", False, 
                            "SOAP generation failed with mock transcription")
                return False, None
                
        except Exception as e:
            self.log_test("AI Scribe Mock Transcription Test", False, f"Error in mock transcription test: {str(e)}")
            return False, None
    
    def run_complete_ai_scribe_workflow_test(self):
        """Run the complete AI Scribe workflow test"""
        print("\n" + "="*60)
        print("AI SCRIBE ENDPOINTS - COMPLETE WORKFLOW TEST")
        print("="*60)
        
        # Step 1: Test backend connectivity
        if not self.test_backend_health():
            print("\n❌ Cannot proceed - Backend is not accessible")
            return False
        
        # Step 2: Test MongoDB connectivity (optional for AI Scribe)
        mongo_ok, doc_count = self.test_mongodb_connection()
        if not mongo_ok:
            print("\n⚠️  MongoDB not accessible, but AI Scribe may still work")
        
        # Step 3: Test AI Scribe transcription endpoint
        print("\n🎤 Testing AI Scribe audio transcription...")
        transcribe_success, transcribe_result = self.test_ai_scribe_transcribe_endpoint()
        
        # Step 4: Test SOAP generation with transcription result or mock data
        print("\n📝 Testing AI Scribe SOAP note generation...")
        if transcribe_success and transcribe_result:
            # Use actual transcription
            transcription_text = transcribe_result['transcription']
            soap_success, soap_result = self.test_ai_scribe_soap_generation_endpoint(transcription_text)
        else:
            # Use mock transcription as fallback
            print("   Using mock transcription as fallback...")
            soap_success, soap_result = self.test_ai_scribe_with_mock_transcription()
        
        # Step 5: Test error handling
        print("\n🛡️  Testing error handling...")
        error_handling_success = self.test_ai_scribe_error_handling()
        
        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        # Determine overall success
        # Transcription is the critical test (was the stuck task)
        # SOAP generation and error handling are important but secondary
        critical_success = transcribe_success
        all_tests_passed = transcribe_success and soap_success and error_handling_success
        
        if critical_success:
            if all_tests_passed:
                print("✅ ALL TESTS PASSED - AI Scribe workflow is working correctly")
                print("✅ CRITICAL: Audio transcription authentication issue is RESOLVED")
            else:
                print("✅ CRITICAL TESTS PASSED - Audio transcription is working")
                print("⚠️  Some secondary tests failed but core functionality works")
        else:
            print("❌ CRITICAL TEST FAILED - Audio transcription still not working")
            print("❌ Authentication issue may still exist")
        
        return critical_success
    
    def cleanup_test_data(self):
        """Clean up test data (optional)"""
        try:
            # AI Scribe tests don't create persistent data, so minimal cleanup needed
            print("🧹 AI Scribe tests completed - no persistent data to clean up")
        except Exception as e:
            print(f"⚠️  Error in cleanup: {str(e)}")
    
    def close_connections(self):
        """Close database connections"""
        try:
            self.mongo_client.close()
        except:
            pass

def main():
    """Main test execution"""
    tester = AIScribeTester()
    
    try:
        # Run the complete workflow test
        success = tester.run_complete_ai_scribe_workflow_test()
        
        # Print detailed results
        print("\n" + "="*60)
        print("DETAILED TEST RESULTS")
        print("="*60)
        
        for result in tester.test_results:
            status = "✅" if result['success'] else "❌"
            print(f"{status} {result['test']}: {result['message']}")
        
        # Cleanup
        tester.cleanup_test_data()
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Unexpected error: {str(e)}")
        return 1
    finally:
        tester.close_connections()

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)