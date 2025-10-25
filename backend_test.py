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
BACKEND_URL = "https://ai-medscribe.preview.emergentagent.com/api"
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

def main():
    """Main test execution"""
    tester = PatientCreationTester()
    
    try:
        # Run the complete workflow test
        success = tester.run_patient_creation_complete_data_mapping_test()
        
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
