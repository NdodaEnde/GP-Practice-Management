#!/usr/bin/env python3
"""
Backend API Testing for GP Document Processing and Patient Creation
Tests the complete GP document workflow including:
- Document extraction and parsing
- Patient creation with complete data mapping
- Encounter creation with vitals integration
- Patient EHR data verification
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
BACKEND_URL = "https://docucare-health.preview.emergentagent.com/api"
MONGO_URL = "mongodb://localhost:27017"
DATABASE_NAME = "surgiscan_documents"
MICROSERVICE_URL = "http://localhost:5001"

class PatientCreationTester:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.mongo_client = MongoClient(MONGO_URL)
        self.db = self.mongo_client["surgiscan_db"]  # Use the main database
        self.test_results = []
        self.test_document_id = "b772f6a3-22c1-48d9-9668-df0f03ee8d4d"  # Specific document from review
        self.test_mongo_id = None
        self.parsed_document_data = None
        self.created_patient_id = None
        self.created_encounter_id = None
        
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
        """Test MongoDB connection and check for parsed documents"""
        try:
            # Test connection
            self.mongo_client.admin.command('ping')
            
            # Check if parsed_documents collection exists
            collections = self.db.list_collection_names()
            has_parsed_collection = 'parsed_documents' in collections
            
            if has_parsed_collection:
                parsed_count = self.db.parsed_documents.count_documents({})
                self.log_test("MongoDB Connection", True, f"Connected. Found {parsed_count} parsed documents")
                return True, parsed_count
            else:
                self.log_test("MongoDB Connection", True, "Connected but no parsed_documents collection found")
                return True, 0
                
        except Exception as e:
            self.log_test("MongoDB Connection", False, f"MongoDB connection failed: {str(e)}")
            return False, 0
    
    def find_test_document(self):
        """Find a suitable document for testing extraction"""
        try:
            # Look for documents with status 'parsed' or 'extracted'
            response = requests.get(
                f"{self.backend_url}/gp/documents",
                params={"limit": 10},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                documents = result.get('documents', [])
                
                # Find a document with status 'parsed' or 'extracted'
                suitable_docs = [doc for doc in documents if doc.get('status') in ['parsed', 'extracted']]
                
                if suitable_docs:
                    test_doc = suitable_docs[0]
                    self.test_document_id = test_doc['id']
                    self.log_test("Find Test Document", True, 
                                f"Found suitable document: {self.test_document_id} (status: {test_doc['status']})")
                    return True
                else:
                    self.log_test("Find Test Document", False, 
                                f"No suitable documents found. Available statuses: {[doc.get('status') for doc in documents]}")
                    return False
            else:
                self.log_test("Find Test Document", False, f"Failed to list documents: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Find Test Document", False, f"Error finding test document: {str(e)}")
            return False
    
    def test_list_digitised_documents(self):
        """Test GET /api/gp/documents - List digitised documents"""
        try:
            # Test listing all documents
            response = requests.get(
                f"{self.backend_url}/gp/documents",
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                expected_fields = ['status', 'documents', 'total']
                
                if all(field in result for field in expected_fields):
                    if result['status'] == 'success':
                        documents = result['documents']
                        total = result['total']
                        
                        self.log_test("List Digitised Documents", True, 
                                    f"Successfully retrieved {total} documents")
                        
                        # Check document structure
                        if documents and len(documents) > 0:
                            first_doc = documents[0]
                            doc_fields = ['id', 'status', 'filename', 'upload_date']
                            present_fields = [f for f in doc_fields if f in first_doc]
                            
                            if len(present_fields) >= 3:
                                self.log_test("Document Structure", True, 
                                            f"Documents have proper structure ({len(present_fields)}/{len(doc_fields)} fields)")
                                
                                # Check for parsed/extracted documents
                                parsed_docs = [doc for doc in documents if doc.get('status') in ['parsed', 'extracted']]
                                if parsed_docs:
                                    self.log_test("Parsed Documents Available", True, 
                                                f"Found {len(parsed_docs)} documents ready for extraction")
                                else:
                                    self.log_test("Parsed Documents Available", False, 
                                                "No documents with 'parsed' or 'extracted' status found")
                            else:
                                self.log_test("Document Structure", False, 
                                            f"Documents missing required fields ({len(present_fields)}/{len(doc_fields)})")
                        
                        return True, result
                    else:
                        self.log_test("List Digitised Documents", False, 
                                    f"Document listing failed: {result.get('status')}")
                        return False, result
                else:
                    missing_fields = [f for f in expected_fields if f not in result]
                    self.log_test("List Digitised Documents", False, 
                                f"Missing fields in response: {missing_fields}")
                    return False, result
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("List Digitised Documents", False, error_msg)
                return False, None
                
        except Exception as e:
            self.log_test("List Digitised Documents", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_extract_document_data(self):
        """Test POST /api/gp/documents/{document_id}/extract - Extract structured data"""
        try:
            if not self.test_document_id:
                self.log_test("Extract Document Data", False, "No test document available")
                return False, None
            
            # Test document extraction
            response = requests.post(
                f"{self.backend_url}/gp/documents/{self.test_document_id}/extract",
                timeout=60  # Extraction might take longer
            )
            
            if response.status_code == 200:
                result = response.json()
                expected_fields = ['status', 'message', 'document_id', 'extracted_data']
                
                if all(field in result for field in expected_fields):
                    if result['status'] == 'success':
                        extracted_data = result['extracted_data']
                        
                        self.log_test("Extract Document Data", True, 
                                    f"Successfully extracted data from document {self.test_document_id}")
                        
                        # Verify extracted data structure
                        expected_sections = ['demographics', 'chronic_summary', 'vitals', 'clinical_notes']
                        present_sections = [section for section in expected_sections if section in extracted_data]
                        
                        if len(present_sections) >= 3:
                            self.log_test("Extracted Data Structure", True, 
                                        f"Extracted data contains {len(present_sections)}/{len(expected_sections)} expected sections: {present_sections}")
                            
                            # Check demographics specifically (main issue from review)
                            demographics = extracted_data.get('demographics', {})
                            if demographics and isinstance(demographics, dict) and len(demographics) > 0:
                                self.log_test("Demographics Extraction", True, 
                                            f"Demographics data extracted successfully: {list(demographics.keys())}")
                            else:
                                self.log_test("Demographics Extraction", False, 
                                            "Demographics data is empty or missing - this causes 'No demographic data extracted' error")
                            
                            # Check conditions/chronic_summary
                            chronic_summary = extracted_data.get('chronic_summary', {})
                            if chronic_summary and isinstance(chronic_summary, dict):
                                conditions = chronic_summary.get('chronic_conditions', [])
                                if conditions:
                                    self.log_test("Conditions Extraction", True, 
                                                f"Found {len(conditions)} chronic conditions")
                                else:
                                    self.log_test("Conditions Extraction", False, 
                                                "No chronic conditions found in extraction")
                            
                            # Check vitals
                            vitals = extracted_data.get('vitals', {})
                            if vitals and isinstance(vitals, dict):
                                vital_records = vitals.get('vital_signs_records', [])
                                if vital_records:
                                    self.log_test("Vitals Extraction", True, 
                                                f"Found {len(vital_records)} vital signs records")
                                else:
                                    self.log_test("Vitals Extraction", False, 
                                                "No vital signs records found")
                        else:
                            self.log_test("Extracted Data Structure", False, 
                                        f"Missing expected sections. Found: {present_sections}, Expected: {expected_sections}")
                        
                        # Verify MongoDB update
                        parsed_doc = self.db.parsed_documents.find_one({'document_id': self.test_document_id})
                        if parsed_doc and parsed_doc.get('structured_extraction'):
                            self.log_test("MongoDB Update Verification", True, 
                                        "Structured extraction saved to MongoDB successfully")
                        else:
                            self.log_test("MongoDB Update Verification", False, 
                                        "Structured extraction not found in MongoDB")
                        
                        return True, result
                    else:
                        self.log_test("Extract Document Data", False, 
                                    f"Extraction failed: {result.get('message', 'Unknown error')}")
                        return False, result
                else:
                    missing_fields = [f for f in expected_fields if f not in result]
                    self.log_test("Extract Document Data", False, 
                                f"Missing fields in response: {missing_fields}")
                    return False, result
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("Extract Document Data", False, error_msg)
                return False, None
                
        except Exception as e:
            self.log_test("Extract Document Data", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_get_parsed_document(self):
        """Test GET /api/gp/parsed-document/{mongo_id} - Retrieve parsed data"""
        try:
            if not self.test_document_id:
                self.log_test("Get Parsed Document", False, "No test document available")
                return False, None
            
            # First, get the mongo_id from the parsed document
            parsed_doc = self.db.parsed_documents.find_one({'document_id': self.test_document_id})
            if not parsed_doc:
                self.log_test("Get Parsed Document", False, "No parsed document found in MongoDB")
                return False, None
            
            mongo_id = str(parsed_doc['_id'])
            self.test_mongo_id = mongo_id
            
            # Test retrieving parsed document data
            response = requests.get(
                f"{self.backend_url}/gp/parsed-document/{mongo_id}",
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                expected_fields = ['status', 'data']
                
                if all(field in result for field in expected_fields):
                    if result['status'] == 'success':
                        data = result['data']
                        
                        self.log_test("Get Parsed Document", True, 
                                    f"Successfully retrieved parsed document data")
                        
                        # Verify data prioritization (structured_extraction over extracted_data)
                        if parsed_doc.get('structured_extraction'):
                            # Should return structured_extraction
                            structured_data = parsed_doc['structured_extraction']
                            if data == structured_data:
                                self.log_test("Data Prioritization", True, 
                                            "Correctly prioritizes structured_extraction over extracted_data")
                            else:
                                self.log_test("Data Prioritization", False, 
                                            "Not returning structured_extraction data as expected")
                        
                        # Verify data structure for GPValidationInterface
                        expected_sections = ['demographics', 'chronic_summary', 'vitals', 'clinical_notes']
                        present_sections = [section for section in expected_sections if section in data]
                        
                        if len(present_sections) >= 3:
                            self.log_test("GPValidationInterface Compatibility", True, 
                                        f"Data structure compatible with GPValidationInterface: {present_sections}")
                            
                            # Detailed check of demographics (main issue)
                            demographics = data.get('demographics', {})
                            if demographics:
                                demo_fields = list(demographics.keys())
                                self.log_test("Demographics Data Path", True, 
                                            f"Demographics accessible at correct path: {demo_fields}")
                                
                                # Log the actual structure for debugging
                                print(f"DEBUG - Demographics structure: {demographics}")
                            else:
                                self.log_test("Demographics Data Path", False, 
                                            "Demographics data not found at expected path - this causes frontend 'No demographic data extracted' error")
                        else:
                            self.log_test("GPValidationInterface Compatibility", False, 
                                        f"Data structure missing required sections. Found: {present_sections}")
                        
                        self.parsed_document_data = data
                        return True, result
                    else:
                        self.log_test("Get Parsed Document", False, 
                                    f"Failed to retrieve parsed document: {result.get('status')}")
                        return False, result
                else:
                    missing_fields = [f for f in expected_fields if f not in result]
                    self.log_test("Get Parsed Document", False, 
                                f"Missing fields in response: {missing_fields}")
                    return False, result
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("Get Parsed Document", False, error_msg)
                return False, None
                
        except Exception as e:
            self.log_test("Get Parsed Document", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_data_structure_validation(self):
        """Validate that extracted data structure matches GPValidationInterface expectations"""
        try:
            if not self.parsed_document_data:
                self.log_test("Data Structure Validation", False, "No parsed document data available")
                return False, None
            
            data = self.parsed_document_data
            
            # Test Demographics Tab Requirements
            demographics = data.get('demographics', {})
            if demographics and isinstance(demographics, dict):
                # Check for common demographic fields
                demo_fields = ['patient_name', 'first_name', 'last_name', 'dob', 'age', 'gender', 'id_number']
                found_fields = [field for field in demo_fields if field in demographics]
                
                if found_fields:
                    self.log_test("Demographics Tab Validation", True, 
                                f"Demographics contains {len(found_fields)} fields: {found_fields}")
                else:
                    self.log_test("Demographics Tab Validation", False, 
                                f"Demographics exists but contains no standard fields. Keys: {list(demographics.keys())}")
            else:
                self.log_test("Demographics Tab Validation", False, 
                            "Demographics section missing or not a dictionary - causes 'No demographic data extracted'")
            
            # Test Conditions Tab Requirements
            chronic_summary = data.get('chronic_summary', {})
            if chronic_summary and isinstance(chronic_summary, dict):
                conditions = chronic_summary.get('chronic_conditions', [])
                medications = chronic_summary.get('current_medications', []) or chronic_summary.get('likely_current_medications', [])
                
                if conditions or medications:
                    self.log_test("Conditions Tab Validation", True, 
                                f"Found {len(conditions)} conditions and {len(medications)} medications")
                else:
                    self.log_test("Conditions Tab Validation", False, 
                                "No chronic conditions or medications found")
            else:
                self.log_test("Conditions Tab Validation", False, 
                            "Chronic summary section missing or invalid")
            
            # Test Vitals Tab Requirements
            vitals = data.get('vitals', {})
            if vitals and isinstance(vitals, dict):
                vital_records = vitals.get('vital_signs_records', [])
                if vital_records:
                    first_record = vital_records[0] if vital_records else {}
                    vital_fields = ['blood_pressure', 'heart_rate', 'temperature', 'weight', 'height']
                    found_vitals = [field for field in vital_fields if field in first_record]
                    
                    if found_vitals:
                        self.log_test("Vitals Tab Validation", True, 
                                    f"Found {len(found_vitals)} vital signs: {found_vitals}")
                    else:
                        self.log_test("Vitals Tab Validation", False, 
                                    f"Vital records exist but no standard fields found. Keys: {list(first_record.keys())}")
                else:
                    self.log_test("Vitals Tab Validation", False, 
                                "No vital signs records found")
            else:
                self.log_test("Vitals Tab Validation", False, 
                            "Vitals section missing or invalid")
            
            # Test Clinical Notes Tab Requirements
            clinical_notes = data.get('clinical_notes', {})
            if clinical_notes:
                if isinstance(clinical_notes, dict):
                    notes_content = str(clinical_notes)
                elif isinstance(clinical_notes, str):
                    notes_content = clinical_notes
                else:
                    notes_content = str(clinical_notes)
                
                if len(notes_content.strip()) > 10:  # Has meaningful content
                    self.log_test("Clinical Notes Tab Validation", True, 
                                f"Clinical notes available ({len(notes_content)} characters)")
                else:
                    self.log_test("Clinical Notes Tab Validation", False, 
                                "Clinical notes too short or empty")
            else:
                self.log_test("Clinical Notes Tab Validation", False, 
                            "Clinical notes section missing")
            
            # Overall validation
            valid_sections = 0
            if demographics: valid_sections += 1
            if chronic_summary: valid_sections += 1
            if vitals: valid_sections += 1
            if clinical_notes: valid_sections += 1
            
            if valid_sections >= 3:
                self.log_test("Overall Data Structure", True, 
                            f"Data structure valid for GPValidationInterface ({valid_sections}/4 sections)")
                return True, data
            else:
                self.log_test("Overall Data Structure", False, 
                            f"Insufficient data sections for GPValidationInterface ({valid_sections}/4 sections)")
                return False, data
                
        except Exception as e:
            self.log_test("Data Structure Validation", False, f"Validation failed: {str(e)}")
            return False, None
    
    
    def run_complete_document_extract_test(self):
        """Run the complete Document Extract Button test"""
        print("\n" + "="*80)
        print("DOCUMENT EXTRACT BUTTON PHASE 1.7 - COMPLETE WORKFLOW TEST")
        print("="*80)
        
        # Step 1: Test backend connectivity
        if not self.test_backend_health():
            print("\n❌ Cannot proceed - Backend is not accessible")
            return False
        
        # Step 2: Test MongoDB connectivity
        mongo_ok, parsed_count = self.test_mongodb_connection()
        if not mongo_ok:
            print("\n⚠️  MongoDB not accessible - Document storage may not work")
        
        # Step 3: Find test document
        print("\n📄 Finding test document...")
        document_found = self.find_test_document()
        if not document_found:
            print("\n❌ Cannot proceed - No suitable documents found for testing")
            return False
        
        # Step 4: Test Scenario 1 - List Documents
        print("\n📋 Testing Scenario 1: List Digitised Documents...")
        list_docs_success, _ = self.test_list_digitised_documents()
        
        # Step 5: Test Scenario 2 - Extract Document Data
        print("\n🔍 Testing Scenario 2: Extract Document Data...")
        extract_success, _ = self.test_extract_document_data()
        
        # Step 6: Test Scenario 3 - Retrieve Parsed Document
        print("\n📖 Testing Scenario 3: Retrieve Parsed Document...")
        retrieve_success, _ = self.test_get_parsed_document()
        
        # Step 7: Test Scenario 4 - Data Structure Validation
        print("\n✅ Testing Scenario 4: Data Structure Validation...")
        validation_success, _ = self.test_data_structure_validation()
        
        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        # Determine overall success
        critical_tests = [
            list_docs_success, extract_success, retrieve_success
        ]
        critical_success = all(critical_tests)
        
        secondary_tests = [
            validation_success
        ]
        all_tests_passed = critical_success and all(secondary_tests)
        
        if critical_success:
            if all_tests_passed:
                print("✅ ALL TESTS PASSED - Document Extract Button functionality is working correctly")
                print("✅ CRITICAL: All core document extraction features are functional")
            else:
                print("✅ CRITICAL TESTS PASSED - Core document extraction workflow is working")
                print("⚠️  Some data structure issues may affect frontend display")
        else:
            print("❌ CRITICAL TESTS FAILED - Document extraction system has issues")
            failed_tests = []
            if not list_docs_success: failed_tests.append("List Documents")
            if not extract_success: failed_tests.append("Extract Document Data")
            if not retrieve_success: failed_tests.append("Retrieve Parsed Document")
            print(f"❌ Failed components: {', '.join(failed_tests)}")
        
        return critical_success
    
    def cleanup_test_data(self):
        """Clean up test data"""
        try:
            # Note: We don't clean up documents as they are existing data
            if self.test_document_id:
                print(f"🧹 Test document {self.test_document_id} used for testing (not cleaned up)")
            
            if self.test_mongo_id:
                print(f"🧹 Test mongo document {self.test_mongo_id} used for testing (not cleaned up)")
            
            print("🧹 Document extraction tests completed")
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
    tester = DocumentExtractTester()
    
    try:
        # Run the complete workflow test
        success = tester.run_complete_document_extract_test()
        
        # Print detailed results
        print("\n" + "="*80)
        print("DETAILED TEST RESULTS")
        print("="*80)
        
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
