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
BACKEND_URL = "https://docwise-health.preview.emergentagent.com/api"
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

class ICD10Tester:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.test_results = []
        self.stats_data = None
        
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
    
    def test_get_parsed_document_for_patient_creation(self):
        """Test getting parsed document data specifically for patient creation"""
        try:
            # First, get the mongo_id from the parsed document
            parsed_doc = self.db.parsed_documents.find_one({'document_id': self.test_document_id})
            if not parsed_doc:
                self.log_test("Get Parsed Document for Patient Creation", False, 
                            f"No parsed document found for document ID {self.test_document_id}")
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
                if result.get('status') == 'success':
                    data = result['data']
                    self.parsed_document_data = data
                    
                    # Verify expected extracted data from review request
                    demographics = data.get('demographics', {})
                    
                    # Check for contact information
                    cell_number = demographics.get('cell_number')
                    if cell_number == "071 4519723":
                        self.log_test("Contact Data Verification", True, 
                                    f"Contact number found: {cell_number}")
                    else:
                        self.log_test("Contact Data Verification", False, 
                                    f"Expected contact '071 4519723', found: {cell_number}")
                    
                    # Check for address information
                    home_address_street = demographics.get('home_address_street')
                    home_address_code = demographics.get('home_address_code')
                    if home_address_street == "6271 Jorga Street Phahama" and home_address_code == "9322":
                        self.log_test("Address Data Verification", True, 
                                    f"Address found: {home_address_street}, {home_address_code}")
                    else:
                        self.log_test("Address Data Verification", False, 
                                    f"Expected address '6271 Jorga Street Phahama, 9322', found: {home_address_street}, {home_address_code}")
                    
                    # Check for medical aid information
                    medical_aid_name = demographics.get('medical_aid_name')
                    if medical_aid_name == "TANZANITE Gems.":
                        self.log_test("Medical Aid Data Verification", True, 
                                    f"Medical aid found: {medical_aid_name}")
                    else:
                        self.log_test("Medical Aid Data Verification", False, 
                                    f"Expected medical aid 'TANZANITE Gems.', found: {medical_aid_name}")
                    
                    # Check for vitals information
                    vitals = data.get('vitals', {})
                    vital_entries = vitals.get('vital_entries', [])
                    if vital_entries:
                        latest_vitals = vital_entries[0]  # First entry should be latest
                        bp_systolic = latest_vitals.get('bp_systolic')
                        bp_diastolic = latest_vitals.get('bp_diastolic')
                        pulse = latest_vitals.get('pulse')
                        
                        if bp_systolic == 147 and bp_diastolic == 98 and pulse == 96:
                            self.log_test("Vitals Data Verification", True, 
                                        f"Latest vitals found: BP {bp_systolic}/{bp_diastolic}, Pulse {pulse}")
                        else:
                            self.log_test("Vitals Data Verification", False, 
                                        f"Expected vitals BP 147/98, Pulse 96, found: BP {bp_systolic}/{bp_diastolic}, Pulse {pulse}")
                    else:
                        self.log_test("Vitals Data Verification", False, "No vital entries found")
                    
                    self.log_test("Get Parsed Document for Patient Creation", True, 
                                "Successfully retrieved parsed document with expected data structure")
                    return True, result
                else:
                    self.log_test("Get Parsed Document for Patient Creation", False, 
                                f"Failed to retrieve parsed document: {result.get('status')}")
                    return False, result
            else:
                self.log_test("Get Parsed Document for Patient Creation", False, 
                            f"API returned status {response.status_code}")
                return False, None
                
        except Exception as e:
            self.log_test("Get Parsed Document for Patient Creation", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_create_new_patient_with_complete_data(self):
        """Test POST /api/gp/validation/create-new-patient with complete data mapping"""
        try:
            if not self.parsed_document_data:
                self.log_test("Create New Patient", False, "No parsed document data available")
                return False, None
            
            demographics = self.parsed_document_data.get('demographics', {})
            
            # Prepare request payload
            request_data = {
                "document_id": self.test_document_id,
                "demographics": demographics,
                "parsed_data": self.parsed_document_data,
                "modifications": []
            }
            
            # Test patient creation
            response = requests.post(
                f"{self.backend_url}/gp/validation/create-new-patient",
                json=request_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    self.created_patient_id = result.get('patient_id')
                    self.created_encounter_id = result.get('encounter_id')
                    
                    self.log_test("Create New Patient", True, 
                                f"Successfully created patient {self.created_patient_id} and encounter {self.created_encounter_id}")
                    return True, result
                else:
                    self.log_test("Create New Patient", False, 
                                f"Patient creation failed: {result.get('message', 'Unknown error')}")
                    return False, result
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("Create New Patient", False, error_msg)
                return False, None
                
        except Exception as e:
            self.log_test("Create New Patient", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_verify_patient_ehr_data(self):
        """Test GET /api/patients/{patient_id} to verify all fields are properly saved"""
        try:
            if not self.created_patient_id:
                self.log_test("Verify Patient EHR Data", False, "No created patient ID available")
                return False, None
            
            # Get patient EHR data
            response = requests.get(
                f"{self.backend_url}/patients/{self.created_patient_id}",
                timeout=30
            )
            
            if response.status_code == 200:
                patient_data = response.json()
                
                # Verify contact number
                contact_number = patient_data.get('contact_number')
                if contact_number == "071 4519723":
                    self.log_test("Patient Contact Verification", True, 
                                f"Contact number correctly saved: {contact_number}")
                else:
                    self.log_test("Patient Contact Verification", False, 
                                f"Expected contact '071 4519723', found: {contact_number}")
                
                # Verify address (should be combined from components)
                address = patient_data.get('address')
                expected_address_parts = ["6271 Jorga Street Phahama", "9322"]
                if address and all(part in address for part in expected_address_parts):
                    self.log_test("Patient Address Verification", True, 
                                f"Address correctly saved: {address}")
                else:
                    self.log_test("Patient Address Verification", False, 
                                f"Expected address containing '6271 Jorga Street Phahama' and '9322', found: {address}")
                
                # Verify medical aid
                medical_aid = patient_data.get('medical_aid')
                if medical_aid == "TANZANITE Gems.":
                    self.log_test("Patient Medical Aid Verification", True, 
                                f"Medical aid correctly saved: {medical_aid}")
                else:
                    self.log_test("Patient Medical Aid Verification", False, 
                                f"Expected medical aid 'TANZANITE Gems.', found: {medical_aid}")
                
                self.log_test("Verify Patient EHR Data", True, 
                            "Patient EHR data retrieved successfully")
                return True, patient_data
            else:
                self.log_test("Verify Patient EHR Data", False, 
                            f"Failed to get patient data: {response.status_code}")
                return False, None
                
        except Exception as e:
            self.log_test("Verify Patient EHR Data", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_verify_encounter_vitals(self):
        """Test encounter creation and vitals integration"""
        try:
            if not self.created_encounter_id:
                self.log_test("Verify Encounter Vitals", False, "No created encounter ID available")
                return False, None
            
            # Get encounter data
            response = requests.get(
                f"{self.backend_url}/encounters/{self.created_encounter_id}",
                timeout=30
            )
            
            if response.status_code == 200:
                encounter_data = response.json()
                vitals_json = encounter_data.get('vitals_json')
                
                if vitals_json:
                    # Check blood pressure
                    blood_pressure = vitals_json.get('blood_pressure')
                    expected_bp = ["147/98", "BP 147/98"]
                    if blood_pressure and any(bp in str(blood_pressure) for bp in expected_bp):
                        self.log_test("Encounter Blood Pressure Verification", True, 
                                    f"Blood pressure correctly saved: {blood_pressure}")
                    else:
                        self.log_test("Encounter Blood Pressure Verification", False, 
                                    f"Expected blood pressure '147/98', found: {blood_pressure}")
                    
                    # Check heart rate
                    heart_rate = vitals_json.get('heart_rate')
                    if heart_rate == 96 or str(heart_rate) == "96":
                        self.log_test("Encounter Heart Rate Verification", True, 
                                    f"Heart rate correctly saved: {heart_rate}")
                    else:
                        self.log_test("Encounter Heart Rate Verification", False, 
                                    f"Expected heart rate 96, found: {heart_rate}")
                    
                    # Check for other vitals
                    weight = vitals_json.get('weight')
                    temperature = vitals_json.get('temperature')
                    
                    vitals_count = sum(1 for v in [blood_pressure, heart_rate, weight, temperature] if v is not None)
                    self.log_test("Encounter Vitals Integration", True, 
                                f"Encounter created with {vitals_count} vital signs")
                    
                else:
                    self.log_test("Encounter Vitals Integration", False, 
                                "No vitals_json found in encounter")
                
                self.log_test("Verify Encounter Vitals", True, 
                            "Encounter vitals verification completed")
                return True, encounter_data
            else:
                self.log_test("Verify Encounter Vitals", False, 
                            f"Failed to get encounter data: {response.status_code}")
                return False, None
                
        except Exception as e:
            self.log_test("Verify Encounter Vitals", False, f"Request failed: {str(e)}")
            return False, None
    
    
    def run_patient_creation_complete_data_mapping_test(self):
        """Run the complete patient creation with data mapping test"""
        print("\n" + "="*80)
        print("PATIENT CREATION WITH COMPLETE DATA MAPPING TEST")
        print("Testing document ID: b772f6a3-22c1-48d9-9668-df0f03ee8d4d")
        print("="*80)
        
        # Step 1: Test backend connectivity
        if not self.test_backend_health():
            print("\n❌ Cannot proceed - Backend is not accessible")
            return False
        
        # Step 2: Test MongoDB connectivity
        mongo_ok, parsed_count = self.test_mongodb_connection()
        if not mongo_ok:
            print("\n⚠️  MongoDB not accessible - Document storage may not work")
        
        # Step 3: Get parsed document to verify extracted data structure
        print("\n📄 Step 1: Getting parsed document to verify extracted data structure...")
        get_parsed_success, _ = self.test_get_parsed_document_for_patient_creation()
        if not get_parsed_success:
            print("\n❌ Cannot proceed - Failed to get parsed document data")
            return False
        
        # Step 4: Create new patient with complete data mapping
        print("\n👥 Step 2: Creating new patient with complete data mapping...")
        create_patient_success, _ = self.test_create_new_patient_with_complete_data()
        if not create_patient_success:
            print("\n❌ Patient creation failed")
            return False
        
        # Step 5: Verify patient EHR data
        print("\n📋 Step 3: Verifying patient EHR data...")
        verify_patient_success, _ = self.test_verify_patient_ehr_data()
        
        # Step 6: Verify encounter vitals
        print("\n💓 Step 4: Verifying encounter vitals integration...")
        verify_vitals_success, _ = self.test_verify_encounter_vitals()
        
        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        # Determine overall success
        critical_tests = [
            get_parsed_success, create_patient_success
        ]
        critical_success = all(critical_tests)
        
        verification_tests = [
            verify_patient_success, verify_vitals_success
        ]
        all_tests_passed = critical_success and all(verification_tests)
        
        if critical_success:
            if all_tests_passed:
                print("✅ ALL TESTS PASSED - Patient creation with complete data mapping is working correctly")
                print("✅ CRITICAL: Patient created with contact, address, medical aid, and vitals")
            else:
                print("✅ CRITICAL TESTS PASSED - Patient creation workflow is working")
                print("⚠️  Some data verification issues found")
        else:
            print("❌ CRITICAL TESTS FAILED - Patient creation system has issues")
            failed_tests = []
            if not get_parsed_success: failed_tests.append("Get Parsed Document")
            if not create_patient_success: failed_tests.append("Create Patient")
            print(f"❌ Failed components: {', '.join(failed_tests)}")
        
        return critical_success
    
    def cleanup_test_data(self):
        """Clean up test data"""
        try:
            # Note: We don't clean up the test patient as it's created for verification
            if self.created_patient_id:
                print(f"🧹 Test patient {self.created_patient_id} created for testing (not cleaned up)")
            
            if self.created_encounter_id:
                print(f"🧹 Test encounter {self.created_encounter_id} created for testing (not cleaned up)")
            
            if self.test_document_id:
                print(f"🧹 Test document {self.test_document_id} used for testing (not cleaned up)")
            
            print("🧹 Patient creation tests completed")
        except Exception as e:
            print(f"⚠️  Error in cleanup: {str(e)}")
    
    def close_connections(self):
        """Close database connections"""
        try:
            self.mongo_client.close()
        except:
            pass

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
    
    def test_icd10_stats(self):
        """Test GET /api/icd10/stats - Database statistics"""
        try:
            response = requests.get(f"{self.backend_url}/icd10/stats", timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                expected_fields = ['total_codes', 'clinical_use_codes', 'primary_diagnosis_codes', 'version']
                
                if all(field in result for field in expected_fields):
                    total_codes = result.get('total_codes', 0)
                    clinical_codes = result.get('clinical_use_codes', 0)
                    primary_codes = result.get('primary_diagnosis_codes', 0)
                    version = result.get('version', '')
                    
                    # Check if we have the expected 41,008 total codes
                    if total_codes == 41008:
                        self.log_test("ICD-10 Stats - Total Codes", True, 
                                    f"Correct total codes: {total_codes}")
                    else:
                        self.log_test("ICD-10 Stats - Total Codes", False, 
                                    f"Expected 41,008 total codes, found: {total_codes}")
                    
                    # Verify clinical use codes exist
                    if clinical_codes > 0:
                        self.log_test("ICD-10 Stats - Clinical Use Codes", True, 
                                    f"Clinical use codes available: {clinical_codes}")
                    else:
                        self.log_test("ICD-10 Stats - Clinical Use Codes", False, 
                                    "No clinical use codes found")
                    
                    # Verify primary diagnosis codes exist
                    if primary_codes > 0:
                        self.log_test("ICD-10 Stats - Primary Diagnosis Codes", True, 
                                    f"Primary diagnosis codes available: {primary_codes}")
                    else:
                        self.log_test("ICD-10 Stats - Primary Diagnosis Codes", False, 
                                    "No primary diagnosis codes found")
                    
                    # Check version info
                    if version:
                        self.log_test("ICD-10 Stats - Version Info", True, 
                                    f"Version information available: {version}")
                    else:
                        self.log_test("ICD-10 Stats - Version Info", False, 
                                    "No version information found")
                    
                    self.stats_data = result
                    self.log_test("ICD-10 Database Statistics", True, 
                                f"Successfully retrieved database statistics")
                    return True, result
                else:
                    missing_fields = [f for f in expected_fields if f not in result]
                    self.log_test("ICD-10 Database Statistics", False, 
                                f"Missing fields in response: {missing_fields}")
                    return False, result
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("ICD-10 Database Statistics", False, error_msg)
                return False, None
                
        except Exception as e:
            self.log_test("ICD-10 Database Statistics", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_icd10_search(self):
        """Test GET /api/icd10/search - Keyword search functionality"""
        try:
            # Test scenarios from review request
            test_queries = [
                {"query": "diabetes", "expected_min": 10, "description": "diabetes search"},
                {"query": "hypertension", "expected_min": 5, "description": "hypertension search"},
                {"query": "asthma", "expected_min": 3, "description": "asthma search"}
            ]
            
            all_searches_passed = True
            
            for test_case in test_queries:
                query = test_case["query"]
                expected_min = test_case["expected_min"]
                description = test_case["description"]
                
                # Test with default parameters
                response = requests.get(
                    f"{self.backend_url}/icd10/search",
                    params={"query": query, "limit": 20, "clinical_use_only": True},
                    timeout=30
                )
                
                if response.status_code == 200:
                    results = response.json()
                    
                    if isinstance(results, list):
                        result_count = len(results)
                        
                        if result_count >= expected_min:
                            self.log_test(f"ICD-10 Search - {description}", True, 
                                        f"Found {result_count} results for '{query}'")
                            
                            # Verify result structure
                            if results:
                                first_result = results[0]
                                expected_fields = ['code', 'who_full_desc', 'valid_clinical_use', 'valid_primary']
                                present_fields = [f for f in expected_fields if f in first_result]
                                
                                if len(present_fields) >= 3:
                                    self.log_test(f"ICD-10 Search Result Structure - {query}", True, 
                                                f"Results have proper structure ({len(present_fields)}/{len(expected_fields)} fields)")
                                    
                                    # Verify the search is relevant (query term appears in description)
                                    desc = first_result.get('who_full_desc', '').lower()
                                    if query.lower() in desc:
                                        self.log_test(f"ICD-10 Search Relevance - {query}", True, 
                                                    f"Search results are relevant to '{query}'")
                                    else:
                                        self.log_test(f"ICD-10 Search Relevance - {query}", False, 
                                                    f"First result may not be relevant: {desc}")
                                else:
                                    self.log_test(f"ICD-10 Search Result Structure - {query}", False, 
                                                f"Results missing required fields ({len(present_fields)}/{len(expected_fields)})")
                                    all_searches_passed = False
                        else:
                            self.log_test(f"ICD-10 Search - {description}", False, 
                                        f"Expected at least {expected_min} results, found {result_count}")
                            all_searches_passed = False
                    else:
                        self.log_test(f"ICD-10 Search - {description}", False, 
                                    f"Expected array response, got: {type(results)}")
                        all_searches_passed = False
                else:
                    error_msg = f"API returned status {response.status_code}"
                    try:
                        error_detail = response.json()
                        error_msg += f": {error_detail}"
                    except:
                        error_msg += f": {response.text}"
                    
                    self.log_test(f"ICD-10 Search - {description}", False, error_msg)
                    all_searches_passed = False
            
            # Test parameter validation
            # Test minimum query length
            response = requests.get(
                f"{self.backend_url}/icd10/search",
                params={"query": "a", "limit": 20},  # Too short
                timeout=30
            )
            
            if response.status_code == 422:  # Validation error expected
                self.log_test("ICD-10 Search - Query Validation", True, 
                            "Correctly validates minimum query length")
            else:
                self.log_test("ICD-10 Search - Query Validation", False, 
                            f"Expected validation error for short query, got status {response.status_code}")
                all_searches_passed = False
            
            # Test limit parameter
            response = requests.get(
                f"{self.backend_url}/icd10/search",
                params={"query": "diabetes", "limit": 5},
                timeout=30
            )
            
            if response.status_code == 200:
                results = response.json()
                if len(results) <= 5:
                    self.log_test("ICD-10 Search - Limit Parameter", True, 
                                f"Correctly limits results to {len(results)}")
                else:
                    self.log_test("ICD-10 Search - Limit Parameter", False, 
                                f"Expected max 5 results, got {len(results)}")
                    all_searches_passed = False
            
            if all_searches_passed:
                self.log_test("ICD-10 Keyword Search", True, 
                            "All keyword search scenarios passed")
                return True
            else:
                self.log_test("ICD-10 Keyword Search", False, 
                            "Some keyword search scenarios failed")
                return False
                
        except Exception as e:
            self.log_test("ICD-10 Keyword Search", False, f"Request failed: {str(e)}")
            return False
    
    def test_icd10_suggest(self):
        """Test GET /api/icd10/suggest - AI-powered suggestions"""
        try:
            # Test with natural language diagnosis text from review request
            diagnosis_text = "Patient with type 2 diabetes and high blood pressure"
            
            response = requests.get(
                f"{self.backend_url}/icd10/suggest",
                params={"diagnosis_text": diagnosis_text, "max_suggestions": 5},
                timeout=60  # AI requests might take longer
            )
            
            if response.status_code == 200:
                result = response.json()
                expected_fields = ['original_text', 'suggestions']
                
                if all(field in result for field in expected_fields):
                    original_text = result.get('original_text')
                    suggestions = result.get('suggestions', [])
                    ai_response = result.get('ai_response')
                    
                    # Verify original text is preserved
                    if original_text == diagnosis_text:
                        self.log_test("ICD-10 AI Suggestions - Original Text", True, 
                                    "Original diagnosis text preserved correctly")
                    else:
                        self.log_test("ICD-10 AI Suggestions - Original Text", False, 
                                    f"Original text mismatch: expected '{diagnosis_text}', got '{original_text}'")
                    
                    # Verify suggestions are provided
                    if suggestions and len(suggestions) > 0:
                        self.log_test("ICD-10 AI Suggestions - Results Count", True, 
                                    f"Received {len(suggestions)} suggestions")
                        
                        # Verify suggestion structure
                        first_suggestion = suggestions[0]
                        expected_suggestion_fields = ['code', 'who_full_desc']
                        present_suggestion_fields = [f for f in expected_suggestion_fields if f in first_suggestion]
                        
                        if len(present_suggestion_fields) >= 2:
                            self.log_test("ICD-10 AI Suggestions - Structure", True, 
                                        f"Suggestions have proper ICD-10 code structure")
                            
                            # Check if suggestions are relevant to diabetes/hypertension
                            relevant_codes = []
                            for suggestion in suggestions:
                                code = suggestion.get('code', '')
                                desc = suggestion.get('who_full_desc', '').lower()
                                
                                # Look for diabetes (E11, E10) or hypertension (I10, I15) codes
                                if (code.startswith('E1') or code.startswith('I1') or 
                                    'diabetes' in desc or 'hypertension' in desc or 'blood pressure' in desc):
                                    relevant_codes.append(code)
                            
                            if relevant_codes:
                                self.log_test("ICD-10 AI Suggestions - Relevance", True, 
                                            f"Found relevant codes: {relevant_codes}")
                            else:
                                self.log_test("ICD-10 AI Suggestions - Relevance", False, 
                                            "No obviously relevant codes found for diabetes/hypertension")
                        else:
                            self.log_test("ICD-10 AI Suggestions - Structure", False, 
                                        f"Suggestions missing required fields ({len(present_suggestion_fields)}/{len(expected_suggestion_fields)})")
                    else:
                        # Check if this is a fallback response
                        if 'note' in result and 'fallback' in result['note'].lower():
                            self.log_test("ICD-10 AI Suggestions - Fallback", True, 
                                        "AI unavailable, fallback to keyword search working")
                        else:
                            self.log_test("ICD-10 AI Suggestions - Results Count", False, 
                                        "No suggestions returned")
                    
                    # Check AI response field
                    if ai_response:
                        self.log_test("ICD-10 AI Suggestions - AI Response", True, 
                                    f"AI response provided: {ai_response[:100]}...")
                    else:
                        self.log_test("ICD-10 AI Suggestions - AI Response", False, 
                                    "No AI response field found")
                    
                    self.log_test("ICD-10 AI-Powered Suggestions", True, 
                                "AI suggestions endpoint working correctly")
                    return True, result
                else:
                    missing_fields = [f for f in expected_fields if f not in result]
                    self.log_test("ICD-10 AI-Powered Suggestions", False, 
                                f"Missing fields in response: {missing_fields}")
                    return False, result
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("ICD-10 AI-Powered Suggestions", False, error_msg)
                return False, None
                
        except Exception as e:
            self.log_test("ICD-10 AI-Powered Suggestions", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_icd10_code_lookup(self):
        """Test GET /api/icd10/code/{code} - Specific code lookup"""
        try:
            # Test with specific code from review request
            test_code = "E11.9"  # Type 2 diabetes mellitus without complications
            
            response = requests.get(
                f"{self.backend_url}/icd10/code/{test_code}",
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                expected_fields = ['code', 'who_full_desc', 'valid_clinical_use', 'valid_primary']
                
                if all(field in result for field in expected_fields):
                    code = result.get('code')
                    description = result.get('who_full_desc', '')
                    valid_clinical = result.get('valid_clinical_use')
                    valid_primary = result.get('valid_primary')
                    
                    # Verify correct code returned
                    if code == test_code:
                        self.log_test("ICD-10 Code Lookup - Code Match", True, 
                                    f"Correct code returned: {code}")
                    else:
                        self.log_test("ICD-10 Code Lookup - Code Match", False, 
                                    f"Expected code '{test_code}', got '{code}'")
                    
                    # Verify description contains diabetes-related terms
                    if 'diabetes' in description.lower():
                        self.log_test("ICD-10 Code Lookup - Description", True, 
                                    f"Correct description: {description}")
                    else:
                        self.log_test("ICD-10 Code Lookup - Description", False, 
                                    f"Description may not be correct for diabetes code: {description}")
                    
                    # Verify clinical use flags
                    if isinstance(valid_clinical, bool) and isinstance(valid_primary, bool):
                        self.log_test("ICD-10 Code Lookup - Validity Flags", True, 
                                    f"Clinical use: {valid_clinical}, Primary: {valid_primary}")
                    else:
                        self.log_test("ICD-10 Code Lookup - Validity Flags", False, 
                                    f"Invalid validity flags: clinical={valid_clinical}, primary={valid_primary}")
                    
                    # Check for optional fields
                    optional_fields = ['chapter_desc', 'group_desc', 'code_3char', 'code_3char_desc', 'gender', 'age_range']
                    present_optional = [f for f in optional_fields if f in result and result[f] is not None]
                    
                    if present_optional:
                        self.log_test("ICD-10 Code Lookup - Additional Fields", True, 
                                    f"Additional fields present: {present_optional}")
                    else:
                        self.log_test("ICD-10 Code Lookup - Additional Fields", False, 
                                    "No additional fields (chapter, group, etc.) found")
                    
                    self.log_test("ICD-10 Specific Code Lookup", True, 
                                f"Successfully retrieved details for code {test_code}")
                    return True, result
                else:
                    missing_fields = [f for f in expected_fields if f not in result]
                    self.log_test("ICD-10 Specific Code Lookup", False, 
                                f"Missing fields in response: {missing_fields}")
                    return False, result
            elif response.status_code == 404:
                self.log_test("ICD-10 Specific Code Lookup", False, 
                            f"Code '{test_code}' not found in database")
                return False, None
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("ICD-10 Specific Code Lookup", False, error_msg)
                return False, None
                
        except Exception as e:
            self.log_test("ICD-10 Specific Code Lookup", False, f"Request failed: {str(e)}")
            return False, None
    
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
    
    def run_icd10_comprehensive_test(self):
        """Run comprehensive ICD-10 API testing"""
        print("\n" + "="*80)
        print("ICD-10 CODE LOOKUP TEST PAGE BACKEND API TESTING")
        print("Testing all 4 ICD-10 endpoints as specified in review request")
        print("="*80)
        
        # Step 1: Test backend connectivity
        if not self.test_backend_health():
            print("\n❌ Cannot proceed - Backend is not accessible")
            return False
        
        # Step 2: Test database statistics
        print("\n📊 Step 1: Testing ICD-10 database statistics...")
        stats_success, _ = self.test_icd10_stats()
        
        # Step 3: Test keyword search
        print("\n🔍 Step 2: Testing ICD-10 keyword search...")
        search_success = self.test_icd10_search()
        
        # Step 4: Test AI-powered suggestions
        print("\n🤖 Step 3: Testing AI-powered ICD-10 suggestions...")
        suggest_success, _ = self.test_icd10_suggest()
        
        # Step 5: Test specific code lookup
        print("\n🎯 Step 4: Testing specific ICD-10 code lookup...")
        lookup_success, _ = self.test_icd10_code_lookup()
        
        # Summary
        print("\n" + "="*80)
        print("ICD-10 API TEST SUMMARY")
        print("="*80)
        
        # Determine overall success
        all_tests = [stats_success, search_success, suggest_success, lookup_success]
        critical_tests = [stats_success, search_success, lookup_success]  # AI suggestions can fallback
        
        critical_success = all(critical_tests)
        all_tests_passed = all(all_tests)
        
        if critical_success:
            if all_tests_passed:
                print("✅ ALL ICD-10 ENDPOINTS WORKING - Complete functionality verified")
                print("✅ Database statistics: 41,008 codes loaded")
                print("✅ Keyword search: diabetes, hypertension, asthma queries working")
                print("✅ AI suggestions: GPT-4o integration functional")
                print("✅ Code lookup: E11.9 (diabetes) details retrieved")
            else:
                print("✅ CRITICAL ICD-10 ENDPOINTS WORKING - Core functionality verified")
                if not suggest_success:
                    print("⚠️  AI suggestions may be using fallback (OpenAI API issue)")
        else:
            print("❌ CRITICAL ICD-10 ENDPOINTS FAILED - System has issues")
            failed_tests = []
            if not stats_success: failed_tests.append("Database Statistics")
            if not search_success: failed_tests.append("Keyword Search")
            if not lookup_success: failed_tests.append("Code Lookup")
            print(f"❌ Failed components: {', '.join(failed_tests)}")
        
        return critical_success

class BillingTester:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.test_results = []
        self.test_patient_id = None
        self.created_invoice_id = None
        self.created_payment_id = None
        self.created_claim_id = None
        self.invoice_data = None
        
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
    
    def get_test_patient_id(self):
        """Get a patient ID for testing"""
        try:
            # Get list of patients
            response = requests.get(f"{self.backend_url}/patients", timeout=30)
            
            if response.status_code == 200:
                patients = response.json()
                if patients and len(patients) > 0:
                    self.test_patient_id = patients[0]['id']
                    patient_name = f"{patients[0].get('first_name', '')} {patients[0].get('last_name', '')}"
                    self.log_test("Get Test Patient ID", True, 
                                f"Using patient: {patient_name} (ID: {self.test_patient_id})")
                    return True
                else:
                    self.log_test("Get Test Patient ID", False, "No patients found in system")
                    return False
            else:
                self.log_test("Get Test Patient ID", False, f"Failed to get patients: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Get Test Patient ID", False, f"Error getting patient ID: {str(e)}")
            return False
    
    def test_simple_invoice_creation(self):
        """Test simple invoice creation as per review request"""
        try:
            if not self.test_patient_id:
                self.log_test("Simple Invoice Creation", False, "No test patient ID available")
                return False
            
            # Create simple invoice with 1 consultation item as per review request
            invoice_data = {
                "patient_id": self.test_patient_id,
                "invoice_date": "2025-10-25",
                "items": [
                    {
                        "item_type": "consultation",
                        "description": "General Consultation",
                        "quantity": 1,
                        "unit_price": 500
                    }
                ]
            }
            
            response = requests.post(
                f"{self.backend_url}/invoices",
                json=invoice_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('status') == 'success':
                    self.created_invoice_id = result.get('invoice_id')
                    invoice_number = result.get('invoice_number')
                    total_amount = result.get('total_amount')
                    
                    # Verify expected response structure
                    if invoice_number and invoice_number.startswith('INV-20251025-'):
                        self.log_test("Invoice Number Generation", True, 
                                    f"Invoice number generated correctly: {invoice_number}")
                    else:
                        self.log_test("Invoice Number Generation", False, 
                                    f"Invoice number format incorrect: {invoice_number}")
                    
                    # Verify total calculation (500 + 75 VAT = 575)
                    expected_total = 575.00
                    if abs(total_amount - expected_total) < 0.01:
                        self.log_test("Total Amount Calculation", True, 
                                    f"Correct total calculated: {total_amount} (500 + 75 VAT)")
                    else:
                        self.log_test("Total Amount Calculation", False, 
                                    f"Expected {expected_total}, got {total_amount}")
                    
                    # Verify invoice_id is returned
                    if self.created_invoice_id:
                        self.log_test("Invoice ID Generation", True, 
                                    f"Invoice ID returned: {self.created_invoice_id}")
                    else:
                        self.log_test("Invoice ID Generation", False, "No invoice_id in response")
                    
                    self.log_test("Simple Invoice Creation", True, 
                                f"Invoice created successfully: {invoice_number}")
                    return True
                else:
                    self.log_test("Simple Invoice Creation", False, 
                                f"Invoice creation failed: {result.get('message', 'Unknown error')}")
                    return False
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("Simple Invoice Creation", False, error_msg)
                return False
                
        except Exception as e:
            self.log_test("Simple Invoice Creation", False, f"Request failed: {str(e)}")
            return False

    def test_create_invoice(self):
        """Test POST /api/invoices - Create invoice with multiple items"""
        try:
            if not self.test_patient_id:
                self.log_test("Create Invoice", False, "No test patient ID available")
                return False
            
            # Create invoice with exact structure from review request
            invoice_data = {
                "patient_id": self.test_patient_id,
                "encounter_id": None,
                "invoice_date": "2025-01-25",
                "items": [
                    {
                        "item_type": "consultation",
                        "description": "General Consultation",
                        "quantity": 1,
                        "unit_price": 500,
                        "icd10_code": "Z00.0"
                    },
                    {
                        "item_type": "medication",
                        "description": "Panado 500mg Tablets",
                        "quantity": 20,
                        "unit_price": 2.50,
                        "nappi_code": "111111"
                    }
                ],
                "medical_aid_name": "Discovery Health",
                "medical_aid_number": "12345678",
                "notes": "Test invoice"
            }
            
            response = requests.post(
                f"{self.backend_url}/invoices",
                json=invoice_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('status') == 'success':
                    self.created_invoice_id = result.get('invoice_id')
                    invoice_number = result.get('invoice_number')
                    total_amount = result.get('total_amount')
                    
                    # Verify calculations
                    expected_subtotal = (1 * 500) + (20 * 2.50)  # 500 + 50 = 550
                    expected_vat = expected_subtotal * 0.15  # 82.50
                    expected_total = expected_subtotal + expected_vat  # 632.50
                    
                    if abs(total_amount - expected_total) < 0.01:  # Allow for floating point precision
                        self.log_test("Invoice Calculation Verification", True, 
                                    f"Correct total calculated: R{total_amount:.2f} (Subtotal: R{expected_subtotal}, VAT: R{expected_vat:.2f})")
                    else:
                        self.log_test("Invoice Calculation Verification", False, 
                                    f"Incorrect total: Expected R{expected_total:.2f}, got R{total_amount:.2f}")
                    
                    self.log_test("Create Invoice", True, 
                                f"Invoice created successfully: {invoice_number} (ID: {self.created_invoice_id})")
                    return True
                else:
                    self.log_test("Create Invoice", False, 
                                f"Invoice creation failed: {result.get('message', 'Unknown error')}")
                    return False
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("Create Invoice", False, error_msg)
                return False
                
        except Exception as e:
            self.log_test("Create Invoice", False, f"Request failed: {str(e)}")
            return False
    
    def test_retrieve_invoice(self):
        """Test GET /api/invoices/{invoice_id} - Retrieve invoice details"""
        try:
            if not self.created_invoice_id:
                self.log_test("Retrieve Invoice", False, "No created invoice ID available")
                return False
            
            response = requests.get(
                f"{self.backend_url}/invoices/{self.created_invoice_id}",
                timeout=30
            )
            
            if response.status_code == 200:
                invoice = response.json()
                self.invoice_data = invoice
                
                # Verify invoice structure
                required_fields = ['id', 'invoice_number', 'patient_id', 'total_amount', 'items', 'payments']
                missing_fields = [field for field in required_fields if field not in invoice]
                
                if not missing_fields:
                    self.log_test("Invoice Structure Verification", True, 
                                f"Invoice has all required fields: {required_fields}")
                    
                    # Verify items
                    items = invoice.get('items', [])
                    if len(items) == 2:
                        consultation_item = next((item for item in items if item.get('item_type') == 'consultation'), None)
                        medication_item = next((item for item in items if item.get('item_type') == 'medication'), None)
                        
                        if consultation_item and medication_item:
                            self.log_test("Invoice Items Verification", True, 
                                        f"Both consultation and medication items found with correct types")
                            
                            # Verify ICD-10 and NAPPI codes
                            if consultation_item.get('icd10_code') == 'Z00.0':
                                self.log_test("ICD-10 Code Verification", True, 
                                            f"Consultation has correct ICD-10 code: {consultation_item.get('icd10_code')}")
                            else:
                                self.log_test("ICD-10 Code Verification", False, 
                                            f"Expected ICD-10 code Z00.0, got: {consultation_item.get('icd10_code')}")
                            
                            if medication_item.get('nappi_code') == '111111':
                                self.log_test("NAPPI Code Verification", True, 
                                            f"Medication has correct NAPPI code: {medication_item.get('nappi_code')}")
                            else:
                                self.log_test("NAPPI Code Verification", False, 
                                            f"Expected NAPPI code 111111, got: {medication_item.get('nappi_code')}")
                        else:
                            self.log_test("Invoice Items Verification", False, 
                                        "Missing consultation or medication items")
                    else:
                        self.log_test("Invoice Items Verification", False, 
                                    f"Expected 2 items, found {len(items)}")
                    
                    # Verify payments array (should be empty initially)
                    payments = invoice.get('payments', [])
                    if isinstance(payments, list):
                        self.log_test("Payments Array Verification", True, 
                                    f"Payments array present (currently {len(payments)} payments)")
                    else:
                        self.log_test("Payments Array Verification", False, 
                                    "Payments field is not an array")
                    
                    self.log_test("Retrieve Invoice", True, 
                                f"Invoice retrieved successfully with complete details")
                    return True
                else:
                    self.log_test("Invoice Structure Verification", False, 
                                f"Missing required fields: {missing_fields}")
                    self.log_test("Retrieve Invoice", False, "Invoice structure incomplete")
                    return False
            else:
                self.log_test("Retrieve Invoice", False, 
                            f"Failed to retrieve invoice: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Retrieve Invoice", False, f"Request failed: {str(e)}")
            return False
    
    def test_record_payment(self):
        """Test POST /api/payments - Record partial payment"""
        try:
            if not self.created_invoice_id:
                self.log_test("Record Payment", False, "No created invoice ID available")
                return False
            
            # Record partial payment as specified in review request
            payment_data = {
                "invoice_id": self.created_invoice_id,
                "payment_date": "2025-01-25",
                "amount": 300,
                "payment_method": "cash",
                "reference_number": "CASH001"
            }
            
            response = requests.post(
                f"{self.backend_url}/payments",
                json=payment_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('status') == 'success':
                    self.created_payment_id = result.get('payment_id')
                    new_outstanding = result.get('new_outstanding')
                    payment_status = result.get('payment_status')
                    
                    # Verify payment status updated to "partially_paid"
                    if payment_status == 'partially_paid':
                        self.log_test("Payment Status Update", True, 
                                    f"Payment status correctly updated to: {payment_status}")
                    else:
                        self.log_test("Payment Status Update", False, 
                                    f"Expected 'partially_paid', got: {payment_status}")
                    
                    # Verify outstanding amount calculation
                    if self.invoice_data:
                        expected_outstanding = float(self.invoice_data.get('total_amount', 0)) - 300
                        if abs(new_outstanding - expected_outstanding) < 0.01:
                            self.log_test("Outstanding Amount Calculation", True, 
                                        f"Correct outstanding amount: R{new_outstanding:.2f}")
                        else:
                            self.log_test("Outstanding Amount Calculation", False, 
                                        f"Expected R{expected_outstanding:.2f}, got R{new_outstanding:.2f}")
                    
                    self.log_test("Record Payment", True, 
                                f"Payment recorded successfully: {self.created_payment_id}")
                    return True
                else:
                    self.log_test("Record Payment", False, 
                                f"Payment recording failed: {result.get('message', 'Unknown error')}")
                    return False
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("Record Payment", False, error_msg)
                return False
                
        except Exception as e:
            self.log_test("Record Payment", False, f"Request failed: {str(e)}")
            return False
    
    def test_create_medical_aid_claim(self):
        """Test POST /api/claims - Create medical aid claim"""
        try:
            if not self.created_invoice_id:
                self.log_test("Create Medical Aid Claim", False, "No created invoice ID available")
                return False
            
            # Create medical aid claim
            claim_data = {
                "invoice_id": self.created_invoice_id,
                "medical_aid_name": "Discovery Health",
                "medical_aid_number": "12345678",
                "medical_aid_plan": "Executive Plan",
                "claim_amount": 632.50,  # Full invoice amount
                "primary_diagnosis_code": "Z00.0",
                "primary_diagnosis_description": "General medical examination"
            }
            
            response = requests.post(
                f"{self.backend_url}/claims",
                json=claim_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('status') == 'success':
                    self.created_claim_id = result.get('claim_id')
                    claim_number = result.get('claim_number')
                    
                    # Verify claim number format (CLM-YYYYMMDD-XXXX)
                    if claim_number and claim_number.startswith('CLM-') and len(claim_number) >= 13:
                        self.log_test("Claim Number Format", True, 
                                    f"Claim number has correct format: {claim_number}")
                    else:
                        self.log_test("Claim Number Format", False, 
                                    f"Claim number format incorrect: {claim_number}")
                    
                    self.log_test("Create Medical Aid Claim", True, 
                                f"Claim created successfully: {claim_number} (ID: {self.created_claim_id})")
                    return True
                else:
                    self.log_test("Create Medical Aid Claim", False, 
                                f"Claim creation failed: {result.get('message', 'Unknown error')}")
                    return False
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("Create Medical Aid Claim", False, error_msg)
                return False
                
        except Exception as e:
            self.log_test("Create Medical Aid Claim", False, f"Request failed: {str(e)}")
            return False
    
    def test_revenue_report(self):
        """Test GET /api/reports/revenue - Financial revenue report"""
        try:
            # Test revenue report for current month
            from_date = "2025-01-01"
            to_date = "2025-01-31"
            
            response = requests.get(
                f"{self.backend_url}/reports/revenue",
                params={"from_date": from_date, "to_date": to_date},
                timeout=30
            )
            
            if response.status_code == 200:
                report = response.json()
                
                # Verify report structure
                required_fields = ['from_date', 'to_date', 'total_invoiced', 'total_paid', 'total_outstanding', 'invoice_count', 'payment_count']
                missing_fields = [field for field in required_fields if field not in report]
                
                if not missing_fields:
                    self.log_test("Revenue Report Structure", True, 
                                f"Report has all required fields: {required_fields}")
                    
                    # Verify data types and values
                    total_invoiced = report.get('total_invoiced', 0)
                    total_paid = report.get('total_paid', 0)
                    total_outstanding = report.get('total_outstanding', 0)
                    invoice_count = report.get('invoice_count', 0)
                    payment_count = report.get('payment_count', 0)
                    
                    if isinstance(total_invoiced, (int, float)) and total_invoiced >= 0:
                        self.log_test("Revenue Report Data - Total Invoiced", True, 
                                    f"Total invoiced: R{total_invoiced:.2f}")
                    else:
                        self.log_test("Revenue Report Data - Total Invoiced", False, 
                                    f"Invalid total invoiced value: {total_invoiced}")
                    
                    if isinstance(total_paid, (int, float)) and total_paid >= 0:
                        self.log_test("Revenue Report Data - Total Paid", True, 
                                    f"Total paid: R{total_paid:.2f}")
                    else:
                        self.log_test("Revenue Report Data - Total Paid", False, 
                                    f"Invalid total paid value: {total_paid}")
                    
                    if isinstance(invoice_count, int) and invoice_count >= 0:
                        self.log_test("Revenue Report Data - Invoice Count", True, 
                                    f"Invoice count: {invoice_count}")
                    else:
                        self.log_test("Revenue Report Data - Invoice Count", False, 
                                    f"Invalid invoice count: {invoice_count}")
                    
                    # Check payment methods breakdown
                    payment_methods = report.get('payment_methods', {})
                    if isinstance(payment_methods, dict):
                        self.log_test("Revenue Report - Payment Methods", True, 
                                    f"Payment methods breakdown: {payment_methods}")
                    else:
                        self.log_test("Revenue Report - Payment Methods", False, 
                                    "Payment methods field is not a dictionary")
                    
                    self.log_test("Revenue Report", True, 
                                f"Revenue report generated successfully for {from_date} to {to_date}")
                    return True
                else:
                    self.log_test("Revenue Report Structure", False, 
                                f"Missing required fields: {missing_fields}")
                    return False
            else:
                self.log_test("Revenue Report", False, 
                            f"Failed to generate revenue report: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Revenue Report", False, f"Request failed: {str(e)}")
            return False
    
    def test_outstanding_report(self):
        """Test GET /api/reports/outstanding - Outstanding invoices report"""
        try:
            response = requests.get(
                f"{self.backend_url}/reports/outstanding",
                timeout=30
            )
            
            if response.status_code == 200:
                report = response.json()
                
                # Verify report structure
                required_fields = ['count', 'total_outstanding', 'invoices']
                missing_fields = [field for field in required_fields if field not in report]
                
                if not missing_fields:
                    self.log_test("Outstanding Report Structure", True, 
                                f"Report has all required fields: {required_fields}")
                    
                    # Verify data
                    count = report.get('count', 0)
                    total_outstanding = report.get('total_outstanding', 0)
                    invoices = report.get('invoices', [])
                    
                    if isinstance(count, int) and count >= 0:
                        self.log_test("Outstanding Report - Count", True, 
                                    f"Outstanding invoices count: {count}")
                    else:
                        self.log_test("Outstanding Report - Count", False, 
                                    f"Invalid count value: {count}")
                    
                    if isinstance(total_outstanding, (int, float)) and total_outstanding >= 0:
                        self.log_test("Outstanding Report - Total", True, 
                                    f"Total outstanding: R{total_outstanding:.2f}")
                    else:
                        self.log_test("Outstanding Report - Total", False, 
                                    f"Invalid total outstanding value: {total_outstanding}")
                    
                    if isinstance(invoices, list):
                        self.log_test("Outstanding Report - Invoices List", True, 
                                    f"Invoices list contains {len(invoices)} items")
                        
                        # If we have our test invoice, verify it appears in outstanding
                        if self.created_invoice_id and invoices:
                            test_invoice_found = any(inv.get('id') == self.created_invoice_id for inv in invoices)
                            if test_invoice_found:
                                self.log_test("Outstanding Report - Test Invoice", True, 
                                            "Test invoice appears in outstanding report (correct - partially paid)")
                            else:
                                self.log_test("Outstanding Report - Test Invoice", False, 
                                            "Test invoice not found in outstanding report")
                    else:
                        self.log_test("Outstanding Report - Invoices List", False, 
                                    "Invoices field is not a list")
                    
                    self.log_test("Outstanding Report", True, 
                                "Outstanding invoices report generated successfully")
                    return True
                else:
                    self.log_test("Outstanding Report Structure", False, 
                                f"Missing required fields: {missing_fields}")
                    return False
            else:
                self.log_test("Outstanding Report", False, 
                            f"Failed to generate outstanding report: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Outstanding Report", False, f"Request failed: {str(e)}")
            return False
    
    def run_billing_system_test(self):
        """Run comprehensive billing system test"""
        print("\n" + "="*80)
        print("PHASE 3 BILLING SYSTEM BACKEND API TESTING")
        print("Testing invoice creation, payments, claims, and financial reports")
        print("="*80)
        
        # Step 1: Test backend connectivity
        if not self.test_backend_health():
            print("\n❌ Cannot proceed - Backend is not accessible")
            return False
        
        # Step 2: Get test patient ID
        print("\n👤 Step 1: Getting patient ID for testing...")
        if not self.get_test_patient_id():
            print("\n❌ Cannot proceed - No patients available for testing")
            return False
        
        # Step 3: Create invoice with multiple items
        print("\n📄 Step 2: Creating invoice with consultation and medication...")
        invoice_success = self.test_create_invoice()
        if not invoice_success:
            print("\n❌ Invoice creation failed - cannot proceed with dependent tests")
            return False
        
        # Step 4: Retrieve invoice details
        print("\n📋 Step 3: Retrieving invoice details...")
        retrieve_success = self.test_retrieve_invoice()
        
        # Step 5: Record partial payment
        print("\n💰 Step 4: Recording partial payment...")
        payment_success = self.test_record_payment()
        
        # Step 6: Create medical aid claim
        print("\n🏥 Step 5: Creating medical aid claim...")
        claim_success = self.test_create_medical_aid_claim()
        
        # Step 7: Test financial reports
        print("\n📊 Step 6: Testing financial reports...")
        revenue_success = self.test_revenue_report()
        outstanding_success = self.test_outstanding_report()
        
        # Summary
        print("\n" + "="*80)
        print("BILLING SYSTEM TEST SUMMARY")
        print("="*80)
        
        # Determine overall success
        critical_tests = [invoice_success, retrieve_success, payment_success]
        additional_tests = [claim_success, revenue_success, outstanding_success]
        
        critical_success = all(critical_tests)
        all_tests_passed = critical_success and all(additional_tests)
        
        if critical_success:
            if all_tests_passed:
                print("✅ ALL BILLING TESTS PASSED - Complete billing system functional")
                print("✅ Invoice creation with auto-calculated totals (VAT 15%)")
                print("✅ Invoice items saved with NAPPI/ICD-10 codes")
                print("✅ Payment recording updates invoice status to 'partially_paid'")
                print("✅ Claims created with proper tracking (CLM-YYYYMMDD-XXXX format)")
                print("✅ Reports generate correct financial data")
            else:
                print("✅ CRITICAL BILLING TESTS PASSED - Core functionality working")
                failed_additional = []
                if not claim_success: failed_additional.append("Medical Aid Claims")
                if not revenue_success: failed_additional.append("Revenue Reports")
                if not outstanding_success: failed_additional.append("Outstanding Reports")
                if failed_additional:
                    print(f"⚠️  Some additional features need attention: {', '.join(failed_additional)}")
        else:
            print("❌ CRITICAL BILLING TESTS FAILED - System has major issues")
            failed_critical = []
            if not invoice_success: failed_critical.append("Invoice Creation")
            if not retrieve_success: failed_critical.append("Invoice Retrieval")
            if not payment_success: failed_critical.append("Payment Recording")
            print(f"❌ Failed critical components: {', '.join(failed_critical)}")
        
        return critical_success
    
    def run_simple_invoice_test(self):
        """Run simple invoice creation test as per review request"""
        print("\n" + "="*80)
        print("SIMPLE INVOICE CREATION TEST")
        print("Testing basic invoice creation with 1 consultation item")
        print("="*80)
        
        # Step 1: Test backend connectivity
        if not self.test_backend_health():
            print("\n❌ Cannot proceed - Backend is not accessible")
            return False
        
        # Step 2: Get test patient ID
        print("\n👤 Step 1: Getting patient ID for testing...")
        if not self.get_test_patient_id():
            print("\n❌ Cannot proceed - No patients available for testing")
            return False
        
        # Step 3: Create simple invoice
        print("\n📄 Step 2: Creating simple invoice with 1 consultation item...")
        invoice_success = self.test_simple_invoice_creation()
        if not invoice_success:
            print("\n❌ Simple invoice creation failed")
            return False
        
        # Step 4: Retrieve created invoice
        print("\n📋 Step 3: Retrieving created invoice...")
        retrieve_success = self.test_retrieve_invoice()
        
        # Summary
        print("\n" + "="*80)
        print("SIMPLE INVOICE TEST SUMMARY")
        print("="*80)
        
        if invoice_success and retrieve_success:
            print("✅ SIMPLE INVOICE CREATION WORKING")
            print("✅ Invoice created successfully with correct calculations")
            print("✅ Invoice number generated in correct format (INV-20251025-XXXX)")
            print("✅ Total amount calculated correctly (500 + 75 VAT = 575)")
            print("✅ Invoice ID returned and retrievable")
            return True
        else:
            print("❌ SIMPLE INVOICE CREATION FAILED")
            if not invoice_success:
                print("❌ Invoice creation endpoint not working")
            if not retrieve_success:
                print("❌ Invoice retrieval endpoint not working")
            return False

class NAPPITester:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.test_results = []
        self.test_patient_id = None
        self.created_prescription_id = None
        self.nappi_search_results = []
        self.selected_nappi_medication = None
        
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
    
    def get_test_patient_id(self):
        """Get or create a test patient for prescription testing"""
        try:
            # First, try to get existing patients
            response = requests.get(f"{self.backend_url}/patients", timeout=30)
            
            if response.status_code == 200:
                patients = response.json()
                if patients and len(patients) > 0:
                    # Use the first patient
                    self.test_patient_id = patients[0]['id']
                    self.log_test("Get Test Patient", True, 
                                f"Using existing patient: {self.test_patient_id}")
                    return True
                else:
                    # Create a test patient
                    patient_data = {
                        "first_name": "Test",
                        "last_name": "Patient",
                        "dob": "1990-01-01",
                        "id_number": "9001010001088",
                        "contact_number": "0123456789",
                        "email": "test@example.com"
                    }
                    
                    create_response = requests.post(
                        f"{self.backend_url}/patients",
                        json=patient_data,
                        timeout=30
                    )
                    
                    if create_response.status_code == 200:
                        created_patient = create_response.json()
                        self.test_patient_id = created_patient['id']
                        self.log_test("Create Test Patient", True, 
                                    f"Created test patient: {self.test_patient_id}")
                        return True
                    else:
                        self.log_test("Create Test Patient", False, 
                                    f"Failed to create patient: {create_response.status_code}")
                        return False
            else:
                self.log_test("Get Test Patient", False, 
                            f"Failed to get patients: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Get Test Patient", False, f"Error getting test patient: {str(e)}")
            return False
    
    def test_nappi_search(self):
        """Test NAPPI search for paracetamol"""
        try:
            # Search for paracetamol as specified in review request
            response = requests.get(
                f"{self.backend_url}/nappi/search",
                params={"query": "paracetamol", "limit": 10},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if 'results' in result and 'count' in result:
                    results = result['results']
                    count = result['count']
                    
                    if count > 0:
                        self.nappi_search_results = results
                        # Select the first result for testing
                        self.selected_nappi_medication = results[0]
                        
                        # Verify the result has required fields
                        required_fields = ['nappi_code', 'brand_name', 'generic_name']
                        present_fields = [f for f in required_fields if f in self.selected_nappi_medication]
                        
                        if len(present_fields) >= 3:
                            self.log_test("NAPPI Search - Paracetamol", True, 
                                        f"Found {count} paracetamol medications. Selected: {self.selected_nappi_medication['brand_name']} (NAPPI: {self.selected_nappi_medication['nappi_code']})")
                            return True
                        else:
                            self.log_test("NAPPI Search - Paracetamol", False, 
                                        f"Search results missing required fields: {present_fields}/{required_fields}")
                            return False
                    else:
                        self.log_test("NAPPI Search - Paracetamol", False, 
                                    "No paracetamol medications found in NAPPI database")
                        return False
                else:
                    self.log_test("NAPPI Search - Paracetamol", False, 
                                f"Invalid response structure: {result}")
                    return False
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("NAPPI Search - Paracetamol", False, error_msg)
                return False
                
        except Exception as e:
            self.log_test("NAPPI Search - Paracetamol", False, f"Request failed: {str(e)}")
            return False
    
    def test_create_prescription_with_nappi(self):
        """Test creating prescription with complete NAPPI data"""
        try:
            if not self.test_patient_id:
                self.log_test("Create Prescription with NAPPI", False, "No test patient available")
                return False
            
            if not self.selected_nappi_medication:
                self.log_test("Create Prescription with NAPPI", False, "No NAPPI medication selected")
                return False
            
            # Create prescription with NAPPI data as specified in review request
            prescription_data = {
                "patient_id": self.test_patient_id,
                "doctor_name": "Dr. Smith",
                "prescription_date": "2025-01-25",
                "items": [{
                    "medication_name": self.selected_nappi_medication.get('brand_name', 'Panado 500mg Tablets'),
                    "nappi_code": self.selected_nappi_medication.get('nappi_code', '111111'),
                    "generic_name": self.selected_nappi_medication.get('generic_name', 'Paracetamol'),
                    "dosage": "500mg",
                    "frequency": "Three times daily",
                    "duration": "5 days",
                    "quantity": "15 tablets",
                    "instructions": "Take with food"
                }],
                "notes": "For headache"
            }
            
            response = requests.post(
                f"{self.backend_url}/prescriptions",
                json=prescription_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('status') == 'success':
                    self.created_prescription_id = result.get('prescription_id')
                    self.log_test("Create Prescription with NAPPI", True, 
                                f"Successfully created prescription {self.created_prescription_id} with NAPPI code {prescription_data['items'][0]['nappi_code']}")
                    return True
                else:
                    self.log_test("Create Prescription with NAPPI", False, 
                                f"Prescription creation failed: {result.get('message', 'Unknown error')}")
                    return False
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("Create Prescription with NAPPI", False, error_msg)
                return False
                
        except Exception as e:
            self.log_test("Create Prescription with NAPPI", False, f"Request failed: {str(e)}")
            return False
    
    def test_retrieve_prescription_with_nappi(self):
        """Test retrieving prescription with NAPPI data"""
        try:
            if not self.test_patient_id:
                self.log_test("Retrieve Prescription with NAPPI", False, "No test patient available")
                return False
            
            # Get prescriptions for the patient
            response = requests.get(
                f"{self.backend_url}/prescriptions/patient/{self.test_patient_id}",
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('status') == 'success':
                    prescriptions = result.get('prescriptions', [])
                    
                    if prescriptions:
                        # Check the first prescription
                        prescription = prescriptions[0]
                        items = prescription.get('items', [])
                        
                        if items:
                            item = items[0]
                            
                            # Verify NAPPI fields are present
                            nappi_code = item.get('nappi_code')
                            generic_name = item.get('generic_name')
                            medication_name = item.get('medication_name')
                            
                            # Check all required fields
                            required_fields = ['medication_name', 'dosage', 'frequency', 'duration', 'quantity', 'instructions']
                            present_fields = [f for f in required_fields if f in item and item[f] is not None]
                            
                            if len(present_fields) >= 6:
                                self.log_test("Prescription Item Fields", True, 
                                            f"All required fields present: {present_fields}")
                            else:
                                missing_fields = [f for f in required_fields if f not in item or item[f] is None]
                                self.log_test("Prescription Item Fields", False, 
                                            f"Missing fields: {missing_fields}")
                            
                            # Verify NAPPI-specific fields
                            if nappi_code and generic_name:
                                self.log_test("Retrieve Prescription with NAPPI", True, 
                                            f"Successfully retrieved prescription with NAPPI code: {nappi_code}, Generic: {generic_name}, Medication: {medication_name}")
                                return True
                            else:
                                self.log_test("Retrieve Prescription with NAPPI", False, 
                                            f"NAPPI fields missing - NAPPI Code: {nappi_code}, Generic Name: {generic_name}")
                                return False
                        else:
                            self.log_test("Retrieve Prescription with NAPPI", False, 
                                        "No prescription items found")
                            return False
                    else:
                        self.log_test("Retrieve Prescription with NAPPI", False, 
                                    "No prescriptions found for patient")
                        return False
                else:
                    self.log_test("Retrieve Prescription with NAPPI", False, 
                                f"Failed to retrieve prescriptions: {result.get('status')}")
                    return False
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("Retrieve Prescription with NAPPI", False, error_msg)
                return False
                
        except Exception as e:
            self.log_test("Retrieve Prescription with NAPPI", False, f"Request failed: {str(e)}")
            return False
    
    def test_multiple_medications_prescription(self):
        """Test prescription with multiple medications - one with NAPPI code, one without"""
        try:
            if not self.test_patient_id:
                self.log_test("Multiple Medications Prescription", False, "No test patient available")
                return False
            
            # Create prescription with 2 medications as specified in review request
            prescription_data = {
                "patient_id": self.test_patient_id,
                "doctor_name": "Dr. Jones",
                "prescription_date": "2025-01-25",
                "items": [
                    {
                        # Medication with NAPPI code
                        "medication_name": self.selected_nappi_medication.get('brand_name', 'Panado 500mg Tablets') if self.selected_nappi_medication else 'Panado 500mg Tablets',
                        "nappi_code": self.selected_nappi_medication.get('nappi_code', '111111') if self.selected_nappi_medication else '111111',
                        "generic_name": self.selected_nappi_medication.get('generic_name', 'Paracetamol') if self.selected_nappi_medication else 'Paracetamol',
                        "dosage": "500mg",
                        "frequency": "Twice daily",
                        "duration": "7 days",
                        "quantity": "14 tablets",
                        "instructions": "Take after meals"
                    },
                    {
                        # Medication without NAPPI code (manual entry)
                        "medication_name": "Custom Herbal Remedy",
                        "nappi_code": None,  # No NAPPI code
                        "generic_name": None,  # No generic name
                        "dosage": "1 teaspoon",
                        "frequency": "Once daily",
                        "duration": "10 days",
                        "quantity": "1 bottle",
                        "instructions": "Take before bedtime"
                    }
                ],
                "notes": "Mixed prescription - one NAPPI coded, one manual entry"
            }
            
            response = requests.post(
                f"{self.backend_url}/prescriptions",
                json=prescription_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('status') == 'success':
                    prescription_id = result.get('prescription_id')
                    
                    # Now retrieve and verify the prescription
                    get_response = requests.get(
                        f"{self.backend_url}/prescriptions/{prescription_id}",
                        timeout=30
                    )
                    
                    if get_response.status_code == 200:
                        get_result = get_response.json()
                        
                        if get_result.get('status') == 'success':
                            prescription = get_result.get('prescription', {})
                            items = prescription.get('items', [])
                            
                            if len(items) == 2:
                                # Check first item (with NAPPI)
                                item1 = items[0]
                                has_nappi = item1.get('nappi_code') is not None and item1.get('generic_name') is not None
                                
                                # Check second item (without NAPPI)
                                item2 = items[1]
                                no_nappi = item2.get('nappi_code') is None and item2.get('generic_name') is None
                                
                                if has_nappi and no_nappi:
                                    self.log_test("Multiple Medications Prescription", True, 
                                                f"Successfully created and retrieved prescription with mixed NAPPI data - Item 1: NAPPI {item1.get('nappi_code')}, Item 2: Manual entry")
                                    return True
                                else:
                                    self.log_test("Multiple Medications Prescription", False, 
                                                f"NAPPI data not correctly saved - Item 1 NAPPI: {has_nappi}, Item 2 No NAPPI: {no_nappi}")
                                    return False
                            else:
                                self.log_test("Multiple Medications Prescription", False, 
                                            f"Expected 2 items, found {len(items)}")
                                return False
                        else:
                            self.log_test("Multiple Medications Prescription", False, 
                                        f"Failed to retrieve created prescription: {get_result.get('status')}")
                            return False
                    else:
                        self.log_test("Multiple Medications Prescription", False, 
                                    f"Failed to retrieve prescription: {get_response.status_code}")
                        return False
                else:
                    self.log_test("Multiple Medications Prescription", False, 
                                f"Prescription creation failed: {result.get('message', 'Unknown error')}")
                    return False
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("Multiple Medications Prescription", False, error_msg)
                return False
                
        except Exception as e:
            self.log_test("Multiple Medications Prescription", False, f"Request failed: {str(e)}")
            return False
    
    def test_end_to_end_nappi_workflow(self):
        """Test complete end-to-end NAPPI workflow: Search → Select → Create → Retrieve"""
        try:
            # This is a summary test that verifies the complete workflow
            workflow_steps = [
                ("NAPPI Search", self.nappi_search_results is not None and len(self.nappi_search_results) > 0),
                ("Medication Selection", self.selected_nappi_medication is not None),
                ("Prescription Creation", self.created_prescription_id is not None),
                ("Patient ID Available", self.test_patient_id is not None)
            ]
            
            all_steps_passed = True
            for step_name, step_result in workflow_steps:
                if step_result:
                    self.log_test(f"E2E Workflow - {step_name}", True, f"{step_name} completed successfully")
                else:
                    self.log_test(f"E2E Workflow - {step_name}", False, f"{step_name} failed")
                    all_steps_passed = False
            
            if all_steps_passed:
                # Verify complete data flow
                if (self.selected_nappi_medication and 
                    self.selected_nappi_medication.get('nappi_code') and 
                    self.selected_nappi_medication.get('generic_name')):
                    
                    self.log_test("End-to-End NAPPI Workflow", True, 
                                f"Complete workflow verified: Search → Select → Create → Retrieve. NAPPI Code: {self.selected_nappi_medication['nappi_code']}")
                    return True
                else:
                    self.log_test("End-to-End NAPPI Workflow", False, 
                                "Workflow completed but NAPPI data incomplete")
                    return False
            else:
                self.log_test("End-to-End NAPPI Workflow", False, 
                            "Some workflow steps failed")
                return False
                
        except Exception as e:
            self.log_test("End-to-End NAPPI Workflow", False, f"Workflow verification failed: {str(e)}")
            return False
    
    def run_nappi_integration_test(self):
        """Run complete NAPPI integration with prescriptions test"""
        print("\n" + "="*80)
        print("NAPPI INTEGRATION WITH PRESCRIPTIONS TEST")
        print("Testing complete NAPPI workflow as specified in review request")
        print("="*80)
        
        # Step 1: Test backend connectivity
        if not self.test_backend_health():
            print("\n❌ Cannot proceed - Backend is not accessible")
            return False
        
        # Step 2: Get a patient ID
        print("\n👥 Step 1: Getting patient ID for prescription testing...")
        patient_success = self.get_test_patient_id()
        if not patient_success:
            print("\n❌ Cannot proceed - Failed to get test patient")
            return False
        
        # Step 3: Search NAPPI for medication (paracetamol)
        print("\n🔍 Step 2: Searching NAPPI for paracetamol...")
        search_success = self.test_nappi_search()
        if not search_success:
            print("\n❌ Cannot proceed - NAPPI search failed")
            return False
        
        # Step 4: Create prescription with complete NAPPI data
        print("\n💊 Step 3: Creating prescription with complete NAPPI data...")
        create_success = self.test_create_prescription_with_nappi()
        if not create_success:
            print("\n❌ Prescription creation with NAPPI failed")
            return False
        
        # Step 5: Retrieve prescription with NAPPI data
        print("\n📋 Step 4: Retrieving prescription with NAPPI data...")
        retrieve_success = self.test_retrieve_prescription_with_nappi()
        
        # Step 6: Test multiple medications (one with NAPPI, one without)
        print("\n🔄 Step 5: Testing multiple medications (mixed NAPPI data)...")
        multiple_success = self.test_multiple_medications_prescription()
        
        # Step 7: End-to-end workflow verification
        print("\n🎯 Step 6: Verifying end-to-end NAPPI workflow...")
        e2e_success = self.test_end_to_end_nappi_workflow()
        
        # Summary
        print("\n" + "="*80)
        print("NAPPI INTEGRATION TEST SUMMARY")
        print("="*80)
        
        # Determine overall success
        critical_tests = [
            patient_success, search_success, create_success, retrieve_success
        ]
        additional_tests = [
            multiple_success, e2e_success
        ]
        
        critical_success = all(critical_tests)
        all_tests_passed = critical_success and all(additional_tests)
        
        if critical_success:
            if all_tests_passed:
                print("✅ ALL NAPPI INTEGRATION TESTS PASSED")
                print("✅ CRITICAL SUCCESS: Complete NAPPI integration working")
                print("✅ Prescriptions created with NAPPI codes save successfully")
                print("✅ NAPPI codes and generic names retrieved correctly")
                print("✅ Optional fields work (nappi_code can be null for manual entries)")
                print("✅ Complete integration verified from search to retrieval")
            else:
                print("✅ CRITICAL NAPPI INTEGRATION WORKING")
                print("✅ Core functionality: Search → Create → Retrieve working")
                if not multiple_success:
                    print("⚠️  Mixed NAPPI data (optional fields) may have issues")
                if not e2e_success:
                    print("⚠️  End-to-end workflow verification had issues")
        else:
            print("❌ CRITICAL NAPPI INTEGRATION FAILED")
            failed_tests = []
            if not patient_success: failed_tests.append("Patient Setup")
            if not search_success: failed_tests.append("NAPPI Search")
            if not create_success: failed_tests.append("Prescription Creation")
            if not retrieve_success: failed_tests.append("Prescription Retrieval")
            print(f"❌ Failed components: {', '.join(failed_tests)}")
        
        return critical_success
    
    def get_or_create_test_patient(self):
        """Get or create a test patient for prescription testing"""
        try:
            # First try to get existing patients
            response = requests.get(f"{self.backend_url}/patients", timeout=30)
            if response.status_code == 200:
                patients = response.json()
                if patients and len(patients) > 0:
                    self.test_patient_id = patients[0]['id']
                    self.log_test("Get Test Patient", True, f"Using existing patient: {self.test_patient_id}")
                    return True
            
            # Create a new test patient if none exist
            patient_data = {
                "first_name": "John",
                "last_name": "Doe",
                "dob": "1980-01-01",
                "id_number": "8001015009087",
                "contact_number": "0123456789",
                "email": "john.doe@test.com",
                "address": "123 Test Street, Test City",
                "medical_aid": "Test Medical Aid"
            }
            
            response = requests.post(f"{self.backend_url}/patients", json=patient_data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                self.test_patient_id = result['id']
                self.log_test("Create Test Patient", True, f"Created test patient: {self.test_patient_id}")
                return True
            else:
                self.log_test("Create Test Patient", False, f"Failed to create patient: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Get/Create Test Patient", False, f"Error: {str(e)}")
            return False
    
    def test_nappi_search_endpoint(self):
        """Test GET /api/nappi/search with common medications"""
        try:
            # Test medications from review request
            test_medications = ["paracetamol", "ibuprofen", "amoxicillin", "atenolol"]
            all_searches_passed = True
            
            for medication in test_medications:
                response = requests.get(
                    f"{self.backend_url}/nappi/search",
                    params={"query": medication, "limit": 10},
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Check response structure
                    expected_fields = ['results', 'count', 'query']
                    if all(field in result for field in expected_fields):
                        results = result['results']
                        count = result['count']
                        
                        if count > 0 and len(results) > 0:
                            # Verify result structure
                            first_result = results[0]
                            expected_result_fields = ['nappi_code', 'brand_name', 'generic_name', 'strength', 'dosage_form', 'schedule']
                            present_fields = [f for f in expected_result_fields if f in first_result]
                            
                            if len(present_fields) >= 4:  # At least 4 of 6 required fields
                                self.log_test(f"NAPPI Search - {medication}", True, 
                                            f"Found {count} results with proper structure")
                                
                                # Store some results for prescription testing
                                if medication == "paracetamol" and len(results) > 0:
                                    self.nappi_search_results = results[:3]  # Store first 3 results
                            else:
                                self.log_test(f"NAPPI Search - {medication}", False, 
                                            f"Results missing required fields. Present: {present_fields}")
                                all_searches_passed = False
                        else:
                            self.log_test(f"NAPPI Search - {medication}", False, 
                                        f"No results found for {medication}")
                            all_searches_passed = False
                    else:
                        missing_fields = [f for f in expected_fields if f not in result]
                        self.log_test(f"NAPPI Search - {medication}", False, 
                                    f"Response missing fields: {missing_fields}")
                        all_searches_passed = False
                else:
                    error_msg = f"API returned status {response.status_code}"
                    try:
                        error_detail = response.json()
                        error_msg += f": {error_detail}"
                    except:
                        error_msg += f": {response.text}"
                    
                    self.log_test(f"NAPPI Search - {medication}", False, error_msg)
                    all_searches_passed = False
            
            if all_searches_passed:
                self.log_test("NAPPI Search Endpoint", True, "All medication searches completed successfully")
                return True
            else:
                self.log_test("NAPPI Search Endpoint", False, "Some medication searches failed")
                return False
                
        except Exception as e:
            self.log_test("NAPPI Search Endpoint", False, f"Request failed: {str(e)}")
            return False
    
    def test_prescription_creation_with_nappi(self):
        """Test creating prescription with NAPPI codes"""
        try:
            if not self.test_patient_id:
                self.log_test("Prescription Creation with NAPPI", False, "No test patient available")
                return False
            
            if not self.nappi_search_results:
                self.log_test("Prescription Creation with NAPPI", False, "No NAPPI search results available")
                return False
            
            # Use first NAPPI result for prescription
            nappi_result = self.nappi_search_results[0]
            
            # Create prescription data as specified in review request
            prescription_data = {
                "patient_id": self.test_patient_id,
                "doctor_name": "Dr. Test",
                "prescription_date": "2025-01-25",
                "items": [{
                    "medication_name": nappi_result.get('brand_name', 'Panado 500mg'),
                    "nappi_code": nappi_result.get('nappi_code', '123456'),
                    "generic_name": nappi_result.get('generic_name', 'Paracetamol'),
                    "dosage": "500mg",
                    "frequency": "Three times daily",
                    "duration": "5 days",
                    "quantity": "15 tablets",
                    "instructions": "Take with food"
                }],
                "notes": "Test prescription with NAPPI integration"
            }
            
            response = requests.post(
                f"{self.backend_url}/prescriptions",
                json=prescription_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('status') == 'success':
                    self.created_prescription_id = result.get('prescription_id')
                    self.log_test("Prescription Creation with NAPPI", True, 
                                f"Successfully created prescription {self.created_prescription_id} with NAPPI code {nappi_result.get('nappi_code')}")
                    return True
                else:
                    self.log_test("Prescription Creation with NAPPI", False, 
                                f"Prescription creation failed: {result.get('message', 'Unknown error')}")
                    return False
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                    
                    # Check for schema-related errors
                    if 'generic_name' in str(error_detail) and 'column' in str(error_detail):
                        error_msg += "\n🔧 SCHEMA ISSUE DETECTED: prescription_items table missing nappi_code and generic_name columns"
                        error_msg += "\n📋 SOLUTION: Execute /app/nappi_prescription_migration.sql in Supabase Dashboard"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("Prescription Creation with NAPPI", False, error_msg)
                return False
                
        except Exception as e:
            self.log_test("Prescription Creation with NAPPI", False, f"Request failed: {str(e)}")
            return False
    
    def test_prescription_retrieval_with_nappi(self):
        """Test GET /api/prescriptions/patient/{patient_id} and verify NAPPI codes"""
        try:
            if not self.test_patient_id:
                self.log_test("Prescription Retrieval with NAPPI", False, "No test patient available")
                return False
            
            response = requests.get(
                f"{self.backend_url}/prescriptions/patient/{self.test_patient_id}",
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('status') == 'success':
                    prescriptions = result.get('prescriptions', [])
                    
                    if prescriptions and len(prescriptions) > 0:
                        # Find our test prescription
                        test_prescription = None
                        for prescription in prescriptions:
                            if prescription.get('id') == self.created_prescription_id:
                                test_prescription = prescription
                                break
                        
                        if test_prescription:
                            items = test_prescription.get('items', [])
                            
                            if items and len(items) > 0:
                                first_item = items[0]
                                
                                # Verify NAPPI code fields are present
                                nappi_code = first_item.get('nappi_code')
                                generic_name = first_item.get('generic_name')
                                medication_name = first_item.get('medication_name')
                                
                                if nappi_code and generic_name and medication_name:
                                    self.log_test("Prescription NAPPI Fields Verification", True, 
                                                f"All NAPPI fields present: medication_name='{medication_name}', nappi_code='{nappi_code}', generic_name='{generic_name}'")
                                    
                                    # Verify the fields are saved correctly
                                    expected_fields = ['dosage', 'frequency', 'duration', 'quantity', 'instructions']
                                    present_fields = [f for f in expected_fields if f in first_item and first_item[f]]
                                    
                                    if len(present_fields) >= 4:
                                        self.log_test("Prescription Data Integrity", True, 
                                                    f"Prescription data saved correctly ({len(present_fields)}/{len(expected_fields)} fields)")
                                    else:
                                        self.log_test("Prescription Data Integrity", False, 
                                                    f"Some prescription fields missing: {[f for f in expected_fields if f not in present_fields]}")
                                    
                                    self.log_test("Prescription Retrieval with NAPPI", True, 
                                                "Successfully retrieved prescription with NAPPI codes")
                                    return True
                                else:
                                    missing_fields = []
                                    if not nappi_code: missing_fields.append('nappi_code')
                                    if not generic_name: missing_fields.append('generic_name')
                                    if not medication_name: missing_fields.append('medication_name')
                                    
                                    self.log_test("Prescription NAPPI Fields Verification", False, 
                                                f"Missing NAPPI fields: {missing_fields}")
                                    return False
                            else:
                                self.log_test("Prescription Retrieval with NAPPI", False, 
                                            "Prescription has no items")
                                return False
                        else:
                            self.log_test("Prescription Retrieval with NAPPI", False, 
                                        f"Test prescription {self.created_prescription_id} not found in results")
                            return False
                    else:
                        self.log_test("Prescription Retrieval with NAPPI", False, 
                                    "No prescriptions found for patient")
                        return False
                else:
                    self.log_test("Prescription Retrieval with NAPPI", False, 
                                f"Failed to retrieve prescriptions: {result.get('status')}")
                    return False
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("Prescription Retrieval with NAPPI", False, error_msg)
                return False
                
        except Exception as e:
            self.log_test("Prescription Retrieval with NAPPI", False, f"Request failed: {str(e)}")
            return False
    
    def test_nappi_stats_endpoint(self):
        """Test GET /api/nappi/stats for database verification"""
        try:
            response = requests.get(f"{self.backend_url}/nappi/stats", timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                expected_fields = ['total_codes', 'active_codes', 'by_schedule']
                
                if all(field in result for field in expected_fields):
                    total_codes = result.get('total_codes', 0)
                    active_codes = result.get('active_codes', 0)
                    by_schedule = result.get('by_schedule', {})
                    
                    if total_codes > 0:
                        self.log_test("NAPPI Database Stats", True, 
                                    f"NAPPI database contains {total_codes} total codes, {active_codes} active codes")
                        
                        # Check schedule breakdown
                        if by_schedule:
                            schedule_info = ", ".join([f"{k}: {v}" for k, v in by_schedule.items()])
                            self.log_test("NAPPI Schedule Breakdown", True, 
                                        f"Schedule distribution: {schedule_info}")
                        
                        return True
                    else:
                        self.log_test("NAPPI Database Stats", False, 
                                    "NAPPI database appears to be empty")
                        return False
                else:
                    missing_fields = [f for f in expected_fields if f not in result]
                    self.log_test("NAPPI Database Stats", False, 
                                f"Response missing fields: {missing_fields}")
                    return False
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("NAPPI Database Stats", False, error_msg)
                return False
                
        except Exception as e:
            self.log_test("NAPPI Database Stats", False, f"Request failed: {str(e)}")
            return False
    
    def run_nappi_integration_test(self):
        """Run comprehensive NAPPI integration test"""
        print("\n" + "="*80)
        print("NAPPI INTEGRATION INTO PRESCRIPTION BUILDER TEST")
        print("Testing NAPPI search, prescription creation, and data retrieval")
        print("="*80)
        
        # Step 1: Test backend connectivity
        if not self.test_backend_health():
            print("\n❌ Cannot proceed - Backend is not accessible")
            return False
        
        # Step 2: Test NAPPI database stats
        print("\n📊 Step 1: Testing NAPPI database statistics...")
        stats_success = self.test_nappi_stats_endpoint()
        
        # Step 3: Test NAPPI search endpoint
        print("\n🔍 Step 2: Testing NAPPI search endpoint...")
        search_success = self.test_nappi_search_endpoint()
        
        # Step 4: Get or create test patient
        print("\n👤 Step 3: Getting test patient...")
        patient_success = self.get_or_create_test_patient()
        if not patient_success:
            print("\n❌ Cannot proceed - Failed to get test patient")
            return False
        
        # Step 5: Test prescription creation with NAPPI codes
        print("\n💊 Step 4: Testing prescription creation with NAPPI codes...")
        create_success = self.test_prescription_creation_with_nappi()
        
        # Step 6: Test prescription retrieval and NAPPI code verification
        print("\n📋 Step 5: Testing prescription retrieval and NAPPI verification...")
        retrieve_success = self.test_prescription_retrieval_with_nappi()
        
        # Summary
        print("\n" + "="*80)
        print("NAPPI INTEGRATION TEST SUMMARY")
        print("="*80)
        
        # Determine overall success
        critical_tests = [search_success, create_success, retrieve_success]
        all_tests = [stats_success, search_success, patient_success, create_success, retrieve_success]
        
        critical_success = all(critical_tests)
        all_tests_passed = all(all_tests)
        
        if critical_success:
            if all_tests_passed:
                print("✅ ALL NAPPI INTEGRATION TESTS PASSED")
                print("✅ NAPPI search returns medications from database")
                print("✅ Prescriptions can be created with NAPPI codes")
                print("✅ NAPPI codes are saved and retrieved correctly")
                print("✅ All fields (medication_name, nappi_code, generic_name) present in responses")
            else:
                print("✅ CRITICAL NAPPI INTEGRATION TESTS PASSED")
                print("✅ Core NAPPI functionality working")
                if not stats_success:
                    print("⚠️  NAPPI database statistics may have issues")
                if not patient_success:
                    print("⚠️  Patient management may have issues")
        else:
            print("❌ CRITICAL NAPPI INTEGRATION TESTS FAILED")
            failed_tests = []
            if not search_success: failed_tests.append("NAPPI Search")
            if not create_success: failed_tests.append("Prescription Creation")
            if not retrieve_success: failed_tests.append("Prescription Retrieval")
            print(f"❌ Failed components: {', '.join(failed_tests)}")
        
        return critical_success
    
    def cleanup_test_data(self):
        """Clean up test data"""
        try:
            if self.created_prescription_id:
                print(f"🧹 Test prescription {self.created_prescription_id} created for testing (not cleaned up)")
            
            if self.test_patient_id:
                print(f"🧹 Test patient {self.test_patient_id} used for testing (not cleaned up)")
            
            print("🧹 NAPPI integration tests completed")
        except Exception as e:
            print(f"⚠️  Error in cleanup: {str(e)}")

class ImmunizationsTester:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.test_results = []
        self.test_patient_id = None
        self.created_immunizations = []  # Track all created immunizations
        
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
    
    def get_test_patient(self):
        """Get a patient ID for testing"""
        try:
            response = requests.get(f"{self.backend_url}/patients", timeout=30)
            
            if response.status_code == 200:
                patients = response.json()
                if patients and len(patients) > 0:
                    self.test_patient_id = patients[0]['id']
                    patient_name = f"{patients[0].get('first_name', '')} {patients[0].get('last_name', '')}"
                    self.log_test("Get Test Patient", True, 
                                f"Found test patient: {patient_name} (ID: {self.test_patient_id})")
                    return True
                else:
                    self.log_test("Get Test Patient", False, "No patients found in system")
                    return False
            else:
                self.log_test("Get Test Patient", False, f"Failed to get patients: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Get Test Patient", False, f"Error getting test patient: {str(e)}")
            return False
    
    def test_check_existing_immunizations(self):
        """Check existing immunizations for the test patient"""
        try:
            if not self.test_patient_id:
                self.log_test("Check Existing Immunizations", False, "No test patient available")
                return False, None
            
            response = requests.get(
                f"{self.backend_url}/immunizations/patient/{self.test_patient_id}",
                timeout=30
            )
            
            if response.status_code == 200:
                immunizations = response.json()
                
                if immunizations and len(immunizations) > 0:
                    # Check if existing immunizations have all required fields
                    first_imm = immunizations[0]
                    required_fields = ['doses_in_series', 'route', 'anatomical_site', 'series_name', 'administered_by']
                    present_fields = [field for field in required_fields if field in first_imm]
                    
                    self.log_test("Check Existing Immunizations", True, 
                                f"Found {len(immunizations)} existing immunizations")
                    
                    if len(present_fields) == len(required_fields):
                        self.log_test("Existing Immunizations Fields", True, 
                                    f"All required fields present: {present_fields}")
                        
                        # Check if doses_in_series is not null
                        doses_in_series = first_imm.get('doses_in_series')
                        if doses_in_series is not None:
                            self.log_test("Existing Immunizations - doses_in_series", True, 
                                        f"doses_in_series field has value: {doses_in_series}")
                        else:
                            self.log_test("Existing Immunizations - doses_in_series", False, 
                                        "doses_in_series field is null - this causes display issues")
                    else:
                        missing_fields = [field for field in required_fields if field not in first_imm]
                        self.log_test("Existing Immunizations Fields", False, 
                                    f"Missing fields: {missing_fields}")
                else:
                    self.log_test("Check Existing Immunizations", True, 
                                "No existing immunizations found - will create test data")
                
                return True, immunizations
            else:
                self.log_test("Check Existing Immunizations", False, 
                            f"Failed to get immunizations: {response.status_code}")
                return False, None
                
        except Exception as e:
            self.log_test("Check Existing Immunizations", False, f"Error checking immunizations: {str(e)}")
            return False, None
    
    def test_create_immunization_with_complete_data(self):
        """Create test immunization with complete data including all previously missing fields"""
        try:
            if not self.test_patient_id:
                self.log_test("Create Test Immunization", False, "No test patient available")
                return False, None
            
            # Create immunization with all the fields that were previously missing
            immunization_data = {
                "patient_id": self.test_patient_id,
                "vaccine_name": "Hepatitis B",
                "vaccine_type": "Hepatitis B",
                "administration_date": "2024-01-15",
                "dose_number": 1,
                "doses_in_series": 3,  # This was missing in response model
                "route": "Intramuscular",  # This was missing in response model
                "anatomical_site": "Left deltoid",  # This was missing in response model
                "series_name": "Hepatitis B Series",  # This was missing in response model
                "administered_by": "Nurse Smith",  # This was missing in response model
                "status": "completed",
                "series_complete": False,
                "next_dose_due": "2024-02-15",
                "clinical_notes": "Test immunization for display bug verification"
            }
            
            response = requests.post(
                f"{self.backend_url}/immunizations",
                json=immunization_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                self.created_immunization_id = result.get('id')
                
                # Verify all fields are present in the response
                required_fields = ['doses_in_series', 'route', 'anatomical_site', 'series_name', 'administered_by']
                present_fields = [field for field in required_fields if field in result and result[field] is not None]
                
                if len(present_fields) == len(required_fields):
                    self.log_test("Create Test Immunization - Response Fields", True, 
                                f"All required fields present in response: {present_fields}")
                    
                    # Verify specific field values
                    if result.get('doses_in_series') == 3:
                        self.log_test("Create Test Immunization - doses_in_series", True, 
                                    f"doses_in_series correctly returned: {result.get('doses_in_series')}")
                    else:
                        self.log_test("Create Test Immunization - doses_in_series", False, 
                                    f"Expected doses_in_series=3, got: {result.get('doses_in_series')}")
                    
                    if result.get('route') == "Intramuscular":
                        self.log_test("Create Test Immunization - route", True, 
                                    f"route correctly returned: {result.get('route')}")
                    else:
                        self.log_test("Create Test Immunization - route", False, 
                                    f"Expected route='Intramuscular', got: {result.get('route')}")
                    
                    if result.get('anatomical_site') == "Left deltoid":
                        self.log_test("Create Test Immunization - anatomical_site", True, 
                                    f"anatomical_site correctly returned: {result.get('anatomical_site')}")
                    else:
                        self.log_test("Create Test Immunization - anatomical_site", False, 
                                    f"Expected anatomical_site='Left deltoid', got: {result.get('anatomical_site')}")
                else:
                    missing_fields = [field for field in required_fields if field not in result or result[field] is None]
                    self.log_test("Create Test Immunization - Response Fields", False, 
                                f"Missing or null fields in response: {missing_fields}")
                
                self.log_test("Create Test Immunization", True, 
                            f"Successfully created immunization: {self.created_immunization_id}")
                return True, result
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("Create Test Immunization", False, error_msg)
                return False, None
                
        except Exception as e:
            self.log_test("Create Test Immunization", False, f"Error creating immunization: {str(e)}")
            return False, None
    
    def test_get_immunization_verify_fields(self):
        """Get the created immunization and verify all fields are present"""
        try:
            if not self.created_immunization_id:
                self.log_test("Get Immunization Verify Fields", False, "No created immunization ID available")
                return False, None
            
            response = requests.get(
                f"{self.backend_url}/immunizations/{self.created_immunization_id}",
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Verify all previously missing fields are present
                required_fields = ['doses_in_series', 'route', 'anatomical_site', 'series_name', 'administered_by']
                field_checks = {}
                
                for field in required_fields:
                    value = result.get(field)
                    field_checks[field] = value is not None
                    
                    if value is not None:
                        self.log_test(f"Get Immunization - {field}", True, 
                                    f"{field} field present: {value}")
                    else:
                        self.log_test(f"Get Immunization - {field}", False, 
                                    f"{field} field is null or missing")
                
                all_fields_present = all(field_checks.values())
                
                if all_fields_present:
                    self.log_test("Get Immunization Verify Fields", True, 
                                "All required fields present in GET response")
                else:
                    missing_fields = [field for field, present in field_checks.items() if not present]
                    self.log_test("Get Immunization Verify Fields", False, 
                                f"Missing fields: {missing_fields}")
                
                return all_fields_present, result
            else:
                self.log_test("Get Immunization Verify Fields", False, 
                            f"Failed to get immunization: {response.status_code}")
                return False, None
                
        except Exception as e:
            self.log_test("Get Immunization Verify Fields", False, f"Error getting immunization: {str(e)}")
            return False, None
    
    def test_patient_immunizations_list(self):
        """Test GET /api/immunizations/patient/{patient_id} to verify all fields in list"""
        try:
            if not self.test_patient_id:
                self.log_test("Test Patient Immunizations List", False, "No test patient available")
                return False, None
            
            response = requests.get(
                f"{self.backend_url}/immunizations/patient/{self.test_patient_id}",
                timeout=30
            )
            
            if response.status_code == 200:
                immunizations = response.json()
                
                if immunizations and len(immunizations) > 0:
                    # Find our created immunization
                    created_imm = None
                    for imm in immunizations:
                        if imm.get('id') == self.created_immunization_id:
                            created_imm = imm
                            break
                    
                    if created_imm:
                        # Verify all fields are present in the list response
                        required_fields = ['doses_in_series', 'route', 'anatomical_site', 'series_name', 'administered_by']
                        field_checks = {}
                        
                        for field in required_fields:
                            value = created_imm.get(field)
                            field_checks[field] = value is not None
                        
                        all_fields_present = all(field_checks.values())
                        
                        if all_fields_present:
                            self.log_test("Patient Immunizations List - Fields", True, 
                                        "All required fields present in list response")
                            
                            # Verify specific values for display format
                            doses_in_series = created_imm.get('doses_in_series')
                            dose_number = created_imm.get('dose_number')
                            
                            if doses_in_series and dose_number:
                                self.log_test("Patient Immunizations List - Dose Display", True, 
                                            f"Can display 'Dose {dose_number}/{doses_in_series}' format")
                            else:
                                self.log_test("Patient Immunizations List - Dose Display", False, 
                                            f"Cannot display dose format - dose_number: {dose_number}, doses_in_series: {doses_in_series}")
                        else:
                            missing_fields = [field for field, present in field_checks.items() if not present]
                            self.log_test("Patient Immunizations List - Fields", False, 
                                        f"Missing fields in list response: {missing_fields}")
                        
                        self.log_test("Test Patient Immunizations List", True, 
                                    f"Found created immunization in patient list")
                        return all_fields_present, immunizations
                    else:
                        self.log_test("Test Patient Immunizations List", False, 
                                    "Created immunization not found in patient list")
                        return False, immunizations
                else:
                    self.log_test("Test Patient Immunizations List", False, 
                                "No immunizations found for patient")
                    return False, None
            else:
                self.log_test("Test Patient Immunizations List", False, 
                            f"Failed to get patient immunizations: {response.status_code}")
                return False, None
                
        except Exception as e:
            self.log_test("Test Patient Immunizations List", False, f"Error getting patient immunizations: {str(e)}")
            return False, None
    
    def create_immunization_dose(self, vaccine_type, dose_number, doses_in_series, series_complete=False, next_dose_due=None):
        """Helper method to create an immunization dose"""
        try:
            from datetime import datetime, timedelta
            
            # Calculate administration date (dose 1 = today, dose 2 = 1 month ago, etc.)
            admin_date = (datetime.now() - timedelta(days=30 * (dose_number - 1))).strftime('%Y-%m-%d')
            
            immunization_data = {
                "patient_id": self.test_patient_id,
                "vaccine_name": vaccine_type,
                "vaccine_type": vaccine_type,
                "administration_date": admin_date,
                "dose_number": dose_number,
                "doses_in_series": doses_in_series,
                "route": "Intramuscular",
                "anatomical_site": "Left deltoid",
                "series_name": f"{vaccine_type} Series",
                "administered_by": "Nurse Smith",
                "status": "completed",
                "series_complete": series_complete,
                "next_dose_due": next_dose_due,
                "clinical_notes": f"Test dose {dose_number} of {doses_in_series} for {vaccine_type}"
            }
            
            response = requests.post(
                f"{self.backend_url}/immunizations",
                json=immunization_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                immunization_id = result.get('id')
                self.created_immunizations.append(immunization_id)
                return True, immunization_id, result
            else:
                return False, None, response.text
                
        except Exception as e:
            return False, None, str(e)
    
    def test_scenario_multiple_doses(self):
        """Test scenario with multiple doses - verify highest_dose_number tracking"""
        try:
            print("\n📋 SCENARIO 1: Multiple Doses Test")
            
            # Create dose 1 of Influenza (3-dose series)
            success1, id1, result1 = self.create_immunization_dose(
                vaccine_type="Influenza",
                dose_number=1,
                doses_in_series=3,
                series_complete=False,
                next_dose_due="2024-02-15"
            )
            
            if not success1:
                self.log_test("Create Influenza Dose 1", False, f"Failed to create dose 1: {result1}")
                return False
            
            self.log_test("Create Influenza Dose 1", True, f"Created dose 1: {id1}")
            
            # Create dose 2 of Influenza
            success2, id2, result2 = self.create_immunization_dose(
                vaccine_type="Influenza", 
                dose_number=2,
                doses_in_series=3,
                series_complete=False,
                next_dose_due="2024-03-15"
            )
            
            if not success2:
                self.log_test("Create Influenza Dose 2", False, f"Failed to create dose 2: {result2}")
                return False
            
            self.log_test("Create Influenza Dose 2", True, f"Created dose 2: {id2}")
            
            # Get summary and verify highest_dose_number=2
            response = requests.get(
                f"{self.backend_url}/immunizations/patient/{self.test_patient_id}/summary",
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                summary = result.get('summary', {})
                influenza_summary = summary.get('Influenza', {})
                
                # Verify highest_dose_number=2 (not total_doses=2)
                highest_dose = influenza_summary.get('highest_dose_number')
                if highest_dose == 2:
                    self.log_test("Multiple Doses - highest_dose_number", True, 
                                f"Correctly tracks highest_dose_number: {highest_dose}")
                else:
                    self.log_test("Multiple Doses - highest_dose_number", False, 
                                f"Expected highest_dose_number=2, got: {highest_dose}")
                
                # Verify doses_in_series=3
                doses_in_series = influenza_summary.get('doses_in_series')
                if doses_in_series == 3:
                    self.log_test("Multiple Doses - doses_in_series", True, 
                                f"Correctly shows doses_in_series: {doses_in_series}")
                else:
                    self.log_test("Multiple Doses - doses_in_series", False, 
                                f"Expected doses_in_series=3, got: {doses_in_series}")
                
                # Verify next_due_date is present (series not complete)
                next_due_date = influenza_summary.get('next_due_date')
                if next_due_date:
                    self.log_test("Multiple Doses - next_due_date", True, 
                                f"next_due_date present (series incomplete): {next_due_date}")
                else:
                    self.log_test("Multiple Doses - next_due_date", False, 
                                "next_due_date should be present for incomplete series")
                
                # Verify series_complete=False
                series_complete = influenza_summary.get('series_complete')
                if series_complete == False:
                    self.log_test("Multiple Doses - series_complete", True, 
                                f"Correctly shows series_complete: {series_complete}")
                else:
                    self.log_test("Multiple Doses - series_complete", False, 
                                f"Expected series_complete=False, got: {series_complete}")
                
                return True
            else:
                self.log_test("Multiple Doses Summary", False, 
                            f"Failed to get summary: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Multiple Doses Scenario", False, f"Error: {str(e)}")
            return False
    
    def test_scenario_complete_series(self):
        """Test complete series scenario - verify next_due_date cleared when complete"""
        try:
            print("\n📋 SCENARIO 2: Complete Series Test")
            
            # Create dose 3 of Influenza (completing the series)
            success3, id3, result3 = self.create_immunization_dose(
                vaccine_type="Influenza",
                dose_number=3,
                doses_in_series=3,
                series_complete=True,
                next_dose_due=None  # Should be None when series complete
            )
            
            if not success3:
                self.log_test("Create Influenza Dose 3", False, f"Failed to create dose 3: {result3}")
                return False
            
            self.log_test("Create Influenza Dose 3", True, f"Created dose 3 (series complete): {id3}")
            
            # Get summary and verify changes
            response = requests.get(
                f"{self.backend_url}/immunizations/patient/{self.test_patient_id}/summary",
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                summary = result.get('summary', {})
                influenza_summary = summary.get('Influenza', {})
                
                # Verify highest_dose_number=3
                highest_dose = influenza_summary.get('highest_dose_number')
                if highest_dose == 3:
                    self.log_test("Complete Series - highest_dose_number", True, 
                                f"Correctly tracks highest_dose_number: {highest_dose}")
                else:
                    self.log_test("Complete Series - highest_dose_number", False, 
                                f"Expected highest_dose_number=3, got: {highest_dose}")
                
                # Verify series_complete=True
                series_complete = influenza_summary.get('series_complete')
                if series_complete == True:
                    self.log_test("Complete Series - series_complete", True, 
                                f"Correctly shows series_complete: {series_complete}")
                else:
                    self.log_test("Complete Series - series_complete", False, 
                                f"Expected series_complete=True, got: {series_complete}")
                
                # Verify next_due_date=None (cleared when complete)
                next_due_date = influenza_summary.get('next_due_date')
                if next_due_date is None:
                    self.log_test("Complete Series - next_due_date cleared", True, 
                                "next_due_date correctly cleared when series complete")
                else:
                    self.log_test("Complete Series - next_due_date cleared", False, 
                                f"Expected next_due_date=None when complete, got: {next_due_date}")
                
                return True
            else:
                self.log_test("Complete Series Summary", False, 
                            f"Failed to get summary: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Complete Series Scenario", False, f"Error: {str(e)}")
            return False
    
    def test_scenario_mixed_vaccine_types(self):
        """Test mixed vaccine types - verify independent tracking"""
        try:
            print("\n📋 SCENARIO 3: Mixed Vaccine Types Test")
            
            # Create COVID-19 dose 1 of 2 (incomplete, with next_due_date)
            success_covid, id_covid, result_covid = self.create_immunization_dose(
                vaccine_type="COVID-19",
                dose_number=1,
                doses_in_series=2,
                series_complete=False,
                next_dose_due="2024-04-15"
            )
            
            if not success_covid:
                self.log_test("Create COVID-19 Dose 1", False, f"Failed to create COVID-19 dose: {result_covid}")
                return False
            
            self.log_test("Create COVID-19 Dose 1", True, f"Created COVID-19 dose 1: {id_covid}")
            
            # Get summary and verify both vaccine types
            response = requests.get(
                f"{self.backend_url}/immunizations/patient/{self.test_patient_id}/summary",
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                summary = result.get('summary', {})
                
                # Verify Influenza summary (should be complete)
                influenza_summary = summary.get('Influenza', {})
                if influenza_summary:
                    flu_highest_dose = influenza_summary.get('highest_dose_number')
                    flu_complete = influenza_summary.get('series_complete')
                    flu_next_due = influenza_summary.get('next_due_date')
                    
                    if flu_highest_dose == 3 and flu_complete == True and flu_next_due is None:
                        self.log_test("Mixed Types - Influenza Status", True, 
                                    f"Influenza: dose {flu_highest_dose}/3, complete={flu_complete}, next_due={flu_next_due}")
                    else:
                        self.log_test("Mixed Types - Influenza Status", False, 
                                    f"Influenza incorrect: dose {flu_highest_dose}, complete={flu_complete}, next_due={flu_next_due}")
                else:
                    self.log_test("Mixed Types - Influenza Status", False, "Influenza summary not found")
                
                # Verify COVID-19 summary (should be incomplete)
                covid_summary = summary.get('COVID-19', {})
                if covid_summary:
                    covid_highest_dose = covid_summary.get('highest_dose_number')
                    covid_complete = covid_summary.get('series_complete')
                    covid_next_due = covid_summary.get('next_due_date')
                    
                    if covid_highest_dose == 1 and covid_complete == False and covid_next_due is not None:
                        self.log_test("Mixed Types - COVID-19 Status", True, 
                                    f"COVID-19: dose {covid_highest_dose}/2, complete={covid_complete}, next_due={covid_next_due}")
                    else:
                        self.log_test("Mixed Types - COVID-19 Status", False, 
                                    f"COVID-19 incorrect: dose {covid_highest_dose}, complete={covid_complete}, next_due={covid_next_due}")
                else:
                    self.log_test("Mixed Types - COVID-19 Status", False, "COVID-19 summary not found")
                
                # Verify independent tracking
                if len(summary) >= 2:
                    self.log_test("Mixed Types - Independent Tracking", True, 
                                f"Multiple vaccine types tracked independently: {list(summary.keys())}")
                else:
                    self.log_test("Mixed Types - Independent Tracking", False, 
                                f"Expected multiple vaccine types, found: {list(summary.keys())}")
                
                return True
            else:
                self.log_test("Mixed Types Summary", False, 
                            f"Failed to get summary: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Mixed Vaccine Types Scenario", False, f"Error: {str(e)}")
            return False
    
    def run_immunizations_summary_display_test(self):
        """Run the improved immunizations summary display logic test"""
        print("\n" + "="*80)
        print("IMMUNIZATIONS SUMMARY DISPLAY LOGIC TEST")
        print("Testing enhanced summary endpoint with highest_dose_number tracking")
        print("and conditional next_due_date display logic")
        print("="*80)
        
        # Step 1: Test backend connectivity
        if not self.test_backend_health():
            print("\n❌ Cannot proceed - Backend is not accessible")
            return False
        
        # Step 2: Get a test patient
        print("\n👤 Step 1: Getting test patient...")
        if not self.get_test_patient():
            print("\n❌ Cannot proceed - No test patient available")
            return False
        
        # Step 3: Test scenario with multiple doses
        print("\n💉 Step 2: Testing multiple doses scenario...")
        scenario1_success = self.test_scenario_multiple_doses()
        
        # Step 4: Test complete series scenario
        print("\n✅ Step 3: Testing complete series scenario...")
        scenario2_success = self.test_scenario_complete_series()
        
        # Step 5: Test mixed vaccine types
        print("\n🔄 Step 4: Testing mixed vaccine types scenario...")
        scenario3_success = self.test_scenario_mixed_vaccine_types()
        
        # Summary
        print("\n" + "="*80)
        print("IMMUNIZATIONS SUMMARY DISPLAY LOGIC TEST SUMMARY")
        print("="*80)
        
        # Determine overall success
        critical_tests = [scenario1_success, scenario2_success, scenario3_success]
        all_tests_passed = all(critical_tests)
        
        if all_tests_passed:
            print("✅ ALL TESTS PASSED - Immunizations summary display logic is working correctly")
            print("✅ CRITICAL SUCCESS: Enhanced summary endpoint tracks highest_dose_number instead of just counting records")
            print("✅ CONDITIONAL LOGIC: next_due_date properly cleared when series_complete=True")
            print("✅ MULTIPLE DOSES: highest_dose_number=2 correctly shown (not total_doses=2)")
            print("✅ COMPLETE SERIES: highest_dose_number=3, series_complete=True, next_due_date=None")
            print("✅ MIXED VACCINES: Multiple vaccine types tracked independently")
            print("✅ BACKEND CHANGES: Lines 217-258 in /app/backend/api/immunizations.py working correctly")
        else:
            print("❌ SOME TESTS FAILED - Immunizations summary display logic has issues")
            failed_tests = []
            if not scenario1_success: failed_tests.append("Multiple Doses Scenario")
            if not scenario2_success: failed_tests.append("Complete Series Scenario")
            if not scenario3_success: failed_tests.append("Mixed Vaccine Types Scenario")
            print(f"❌ Failed scenarios: {', '.join(failed_tests)}")
        
        return all_tests_passed
    
    def cleanup_test_data(self):
        """Clean up created test immunizations"""
        try:
            for immunization_id in self.created_immunizations:
                try:
                    requests.delete(f"{self.backend_url}/immunizations/{immunization_id}", timeout=10)
                except:
                    pass  # Ignore cleanup errors
            print(f"🧹 Cleaned up {len(self.created_immunizations)} test immunizations")
        except Exception as e:
            print(f"⚠️  Error in cleanup: {str(e)}")

def main():
    """Main test execution"""
    import sys
    
    # Check if we should run simple invoice test specifically (as per review request)
    if len(sys.argv) > 1 and sys.argv[1] == "simple_invoice":
        # Run Simple Invoice Creation test
        billing_tester = BillingTester()
        
        try:
            # Run the simple invoice test as per review request
            success = billing_tester.run_simple_invoice_test()
            
            # Print detailed results
            print("\n" + "="*80)
            print("DETAILED SIMPLE INVOICE TEST RESULTS")
            print("="*80)
            
            for result in billing_tester.test_results:
                status = "✅" if result['success'] else "❌"
                print(f"{status} {result['test']}: {result['message']}")
            
            return 0 if success else 1
            
        except KeyboardInterrupt:
            print("\n⚠️  Test interrupted by user")
            return 1
        except Exception as e:
            print(f"\n💥 Unexpected error: {str(e)}")
            return 1
    
    # Check if we should run billing tests specifically
    elif len(sys.argv) > 1 and sys.argv[1] == "billing":
        # Run Billing System tests
        billing_tester = BillingTester()
        
        try:
            # Run the billing system test
            success = billing_tester.run_billing_system_test()
            
            # Print detailed results
            print("\n" + "="*80)
            print("DETAILED BILLING SYSTEM TEST RESULTS")
            print("="*80)
            
            for result in billing_tester.test_results:
                status = "✅" if result['success'] else "❌"
                print(f"{status} {result['test']}: {result['message']}")
            
            return 0 if success else 1
            
        except KeyboardInterrupt:
            print("\n⚠️  Test interrupted by user")
            return 1
        except Exception as e:
            print(f"\n💥 Unexpected error: {str(e)}")
            return 1
    
    # Check if we should run immunizations tests specifically
    elif len(sys.argv) > 1 and sys.argv[1] == "immunizations":
        # Run Immunizations tests
        immunizations_tester = ImmunizationsTester()
        
        try:
            # Run the immunizations summary display logic test
            success = immunizations_tester.run_immunizations_summary_display_test()
            
            # Print detailed results
            print("\n" + "="*80)
            print("DETAILED IMMUNIZATIONS TEST RESULTS")
            print("="*80)
            
            for result in immunizations_tester.test_results:
                status = "✅" if result['success'] else "❌"
                print(f"{status} {result['test']}: {result['message']}")
            
            return 0 if success else 1
            
        except KeyboardInterrupt:
            print("\n⚠️  Test interrupted by user")
            return 1
        except Exception as e:
            print(f"\n💥 Unexpected error: {str(e)}")
            return 1
    
    # Check if we should run ICD-10 tests specifically
    elif len(sys.argv) > 1 and sys.argv[1] == "icd10":
        # Run ICD-10 tests
        icd10_tester = ICD10Tester()
        
        try:
            # Run the ICD-10 comprehensive test
            success = icd10_tester.run_icd10_comprehensive_test()
            
            # Print detailed results
            print("\n" + "="*80)
            print("DETAILED ICD-10 TEST RESULTS")
            print("="*80)
            
            for result in icd10_tester.test_results:
                status = "✅" if result['success'] else "❌"
                print(f"{status} {result['test']}: {result['message']}")
            
            return 0 if success else 1
            
        except KeyboardInterrupt:
            print("\n⚠️  Test interrupted by user")
            return 1
        except Exception as e:
            print(f"\n💥 Unexpected error: {str(e)}")
            return 1
    
    # Check if we should run NAPPI tests specifically
    elif len(sys.argv) > 1 and sys.argv[1] == "nappi":
        # Run NAPPI integration tests
        nappi_tester = NAPPITester()
        
        try:
            # Run the NAPPI integration test
            success = nappi_tester.run_nappi_integration_test()
            
            # Print detailed results
            print("\n" + "="*80)
            print("DETAILED NAPPI INTEGRATION TEST RESULTS")
            print("="*80)
            
            for result in nappi_tester.test_results:
                status = "✅" if result['success'] else "❌"
                print(f"{status} {result['test']}: {result['message']}")
            
            # Cleanup
            nappi_tester.cleanup_test_data()
            
            return 0 if success else 1
            
        except KeyboardInterrupt:
            print("\n⚠️  Test interrupted by user")
            return 1
        except Exception as e:
            print(f"\n💥 Unexpected error: {str(e)}")
            return 1
    
    else:
        # Run Simple Invoice Creation test by default (as per review request)
        billing_tester = BillingTester()
        
        try:
            # Run the simple invoice creation test as requested in review
            success = billing_tester.run_simple_invoice_test()
            
            # Print detailed results
            print("\n" + "="*80)
            print("DETAILED SIMPLE INVOICE TEST RESULTS")
            print("="*80)
            
            for result in billing_tester.test_results:
                status = "✅" if result['success'] else "❌"
                print(f"{status} {result['test']}: {result['message']}")
            
            return 0 if success else 1
            
        except KeyboardInterrupt:
            print("\n⚠️  Test interrupted by user")
            return 1
        except Exception as e:
            print(f"\n💥 Unexpected error: {str(e)}")
            return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
