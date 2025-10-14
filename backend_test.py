#!/usr/bin/env python3
"""
Backend API Testing for GP Validation Save Endpoint
Tests the complete GP validation workflow including save functionality
"""

import requests
import json
import uuid
from datetime import datetime, timezone
import os
from pymongo import MongoClient
import sys

# Configuration
BACKEND_URL = "https://surgiscan-gp.preview.emergentagent.com/api"
MONGO_URL = "mongodb://localhost:27017"
DATABASE_NAME = "surgiscan_documents"

class GPValidationTester:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.mongo_client = MongoClient(MONGO_URL)
        self.db = self.mongo_client[DATABASE_NAME]
        self.test_results = []
        
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
    
    def get_test_document_id(self):
        """Get a document ID for testing, or create a mock one if none exists"""
        try:
            # Try to find an existing document
            doc = self.db.gp_scanned_documents.find_one({})
            if doc:
                document_id = doc.get('document_id')
                self.log_test("Get Test Document", True, f"Found existing document: {document_id}")
                return document_id
            else:
                # Create a mock document for testing
                document_id = str(uuid.uuid4())
                mock_doc = {
                    "document_id": document_id,
                    "filename": "test_gp_record.pdf",
                    "patient_name": "John Smith",
                    "upload_date": datetime.now(timezone.utc).isoformat(),
                    "status": "processed",
                    "parsed_data": {
                        "demographics": {
                            "patient_name": "John Smith",
                            "age": 45,
                            "gender": "Male",
                            "date_of_birth": "1979-03-15",
                            "id_number": "7903155678901",
                            "contact_number": "0821234567",
                            "address": "123 Main Street, Cape Town"
                        },
                        "chronic_summary": {
                            "conditions": [
                                {"condition": "Hypertension", "diagnosed_date": "2020-01-15", "status": "Active"},
                                {"condition": "Type 2 Diabetes", "diagnosed_date": "2019-08-22", "status": "Active"}
                            ],
                            "medications": [
                                {"name": "Metformin", "dosage": "500mg", "frequency": "Twice daily", "start_date": "2019-08-22"},
                                {"name": "Lisinopril", "dosage": "10mg", "frequency": "Once daily", "start_date": "2020-01-15"}
                            ]
                        },
                        "vitals": [
                            {"date": "2024-01-15", "blood_pressure": "135/85", "heart_rate": 78, "weight": 85.5, "height": 175},
                            {"date": "2024-01-10", "blood_pressure": "140/90", "heart_rate": 82, "weight": 85.2, "height": 175}
                        ],
                        "clinical_notes": "Patient presents with well-controlled diabetes and hypertension. Continue current medication regimen. Blood pressure slightly elevated, monitor closely. Patient reports good adherence to medication. No new symptoms. Follow up in 3 months."
                    }
                }
                
                self.db.gp_scanned_documents.insert_one(mock_doc)
                self.log_test("Create Test Document", True, f"Created mock document: {document_id}")
                return document_id
                
        except Exception as e:
            self.log_test("Get Test Document", False, f"Error getting test document: {str(e)}")
            return None
    
    def test_gp_validation_save_endpoint(self, document_id):
        """Test the GP validation save endpoint"""
        try:
            # Prepare test data with modifications
            test_modifications = [
                {
                    "field_path": "demographics.patient_name",
                    "original_value": "John Smith",
                    "new_value": "John David Smith",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "modification_type": "edit"
                },
                {
                    "field_path": "demographics.contact_number",
                    "original_value": "0821234567",
                    "new_value": "0827654321",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "modification_type": "edit"
                },
                {
                    "field_path": "chronic_summary.medications",
                    "original_value": None,
                    "new_value": {"name": "Aspirin", "dosage": "75mg", "frequency": "Once daily", "start_date": "2024-01-15"},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "modification_type": "add"
                }
            ]
            
            # Updated parsed data with modifications applied
            validated_data = {
                "demographics": {
                    "patient_name": "John David Smith",  # Modified
                    "age": 45,
                    "gender": "Male",
                    "date_of_birth": "1979-03-15",
                    "id_number": "7903155678901",
                    "contact_number": "0827654321",  # Modified
                    "address": "123 Main Street, Cape Town"
                },
                "chronic_summary": {
                    "conditions": [
                        {"condition": "Hypertension", "diagnosed_date": "2020-01-15", "status": "Active"},
                        {"condition": "Type 2 Diabetes", "diagnosed_date": "2019-08-22", "status": "Active"}
                    ],
                    "medications": [
                        {"name": "Metformin", "dosage": "500mg", "frequency": "Twice daily", "start_date": "2019-08-22"},
                        {"name": "Lisinopril", "dosage": "10mg", "frequency": "Once daily", "start_date": "2020-01-15"},
                        {"name": "Aspirin", "dosage": "75mg", "frequency": "Once daily", "start_date": "2024-01-15"}  # Added
                    ]
                },
                "vitals": [
                    {"date": "2024-01-15", "blood_pressure": "135/85", "heart_rate": 78, "weight": 85.5, "height": 175},
                    {"date": "2024-01-10", "blood_pressure": "140/90", "heart_rate": 82, "weight": 85.2, "height": 175}
                ],
                "clinical_notes": "Patient presents with well-controlled diabetes and hypertension. Continue current medication regimen. Blood pressure slightly elevated, monitor closely. Patient reports good adherence to medication. No new symptoms. Added aspirin for cardiovascular protection. Follow up in 3 months."
            }
            
            # Prepare request payload
            payload = {
                "document_id": document_id,
                "parsed_data": validated_data,
                "modifications": test_modifications,
                "status": "approved",
                "notes": f"Validated at {datetime.now(timezone.utc).isoformat()}"
            }
            
            # Make API call
            response = requests.post(
                f"{self.backend_url}/gp/validation/save",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                expected_fields = ['status', 'message', 'document_id', 'modifications_count']
                
                if all(field in result for field in expected_fields):
                    if result['modifications_count'] == len(test_modifications):
                        self.log_test("GP Validation Save API", True, 
                                    f"Successfully saved validation with {result['modifications_count']} modifications")
                        return True, result
                    else:
                        self.log_test("GP Validation Save API", False, 
                                    f"Modification count mismatch: expected {len(test_modifications)}, got {result['modifications_count']}")
                        return False, result
                else:
                    missing_fields = [f for f in expected_fields if f not in result]
                    self.log_test("GP Validation Save API", False, 
                                f"Missing fields in response: {missing_fields}")
                    return False, result
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("GP Validation Save API", False, error_msg)
                return False, None
                
        except Exception as e:
            self.log_test("GP Validation Save API", False, f"Request failed: {str(e)}")
            return False, None
    
    def verify_validated_document_saved(self, document_id):
        """Verify that the validated document was saved to MongoDB"""
        try:
            # Check gp_validated_documents collection
            validated_doc = self.db.gp_validated_documents.find_one({"document_id": document_id})
            
            if validated_doc:
                required_fields = ['document_id', 'validated_data', 'modifications', 'status', 'validated_at']
                missing_fields = [f for f in required_fields if f not in validated_doc]
                
                if not missing_fields:
                    mod_count = len(validated_doc.get('modifications', []))
                    self.log_test("Validated Document Storage", True, 
                                f"Document saved with {mod_count} modifications")
                    return True
                else:
                    self.log_test("Validated Document Storage", False, 
                                f"Missing fields in saved document: {missing_fields}")
                    return False
            else:
                self.log_test("Validated Document Storage", False, 
                            "Validated document not found in gp_validated_documents collection")
                return False
                
        except Exception as e:
            self.log_test("Validated Document Storage", False, f"Error checking validated document: {str(e)}")
            return False
    
    def verify_original_document_updated(self, document_id):
        """Verify that the original document status was updated"""
        try:
            # Check original document in gp_scanned_documents
            original_doc = self.db.gp_scanned_documents.find_one({"document_id": document_id})
            
            if original_doc:
                status = original_doc.get('status')
                has_validated_at = 'validated_at' in original_doc
                
                if status == 'validated' and has_validated_at:
                    self.log_test("Original Document Update", True, 
                                "Original document status updated to 'validated'")
                    return True
                else:
                    self.log_test("Original Document Update", False, 
                                f"Document status: {status}, has validated_at: {has_validated_at}")
                    return False
            else:
                self.log_test("Original Document Update", False, 
                            "Original document not found")
                return False
                
        except Exception as e:
            self.log_test("Original Document Update", False, f"Error checking original document: {str(e)}")
            return False
    
    def verify_audit_event_logged(self, document_id):
        """Verify that an audit event was logged"""
        try:
            # Check audit_events collection in the main database
            main_db = self.mongo_client['surgiscan_db']  # Main database name from backend/.env
            
            # Look for recent audit event for this document
            recent_time = datetime.now(timezone.utc).replace(minute=datetime.now(timezone.utc).minute - 5)
            audit_event = main_db.audit_events.find_one({
                "event_type": "gp_document_validated",
                "document_id": document_id,
                "timestamp": {"$gte": recent_time.isoformat()}
            })
            
            if audit_event:
                self.log_test("Audit Event Logging", True, 
                            f"Audit event logged with type: {audit_event['event_type']}")
                return True
            else:
                self.log_test("Audit Event Logging", False, 
                            "No audit event found for document validation")
                return False
                
        except Exception as e:
            self.log_test("Audit Event Logging", False, f"Error checking audit events: {str(e)}")
            return False
    
    def run_complete_validation_workflow_test(self):
        """Run the complete GP validation workflow test"""
        print("\n" + "="*60)
        print("GP VALIDATION SAVE ENDPOINT - COMPLETE WORKFLOW TEST")
        print("="*60)
        
        # Step 1: Test backend connectivity
        if not self.test_backend_health():
            print("\n❌ Cannot proceed - Backend is not accessible")
            return False
        
        # Step 2: Test MongoDB connectivity
        mongo_ok, doc_count = self.test_mongodb_connection()
        if not mongo_ok:
            print("\n❌ Cannot proceed - MongoDB is not accessible")
            return False
        
        # Step 3: Get or create test document
        document_id = self.get_test_document_id()
        if not document_id:
            print("\n❌ Cannot proceed - No test document available")
            return False
        
        print(f"\n🔍 Testing with document ID: {document_id}")
        
        # Step 4: Test the validation save endpoint
        save_success, save_result = self.test_gp_validation_save_endpoint(document_id)
        if not save_success:
            print("\n❌ Validation save endpoint failed")
            return False
        
        # Step 5: Verify data persistence
        print("\n📊 Verifying data persistence...")
        
        validated_saved = self.verify_validated_document_saved(document_id)
        original_updated = self.verify_original_document_updated(document_id)
        audit_logged = self.verify_audit_event_logged(document_id)
        
        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        all_tests_passed = all([
            save_success,
            validated_saved,
            original_updated,
            audit_logged
        ])
        
        if all_tests_passed:
            print("✅ ALL TESTS PASSED - GP Validation workflow is working correctly")
        else:
            print("❌ SOME TESTS FAILED - Issues found in GP Validation workflow")
        
        return all_tests_passed
    
    def cleanup_test_data(self, document_id):
        """Clean up test data (optional)"""
        try:
            # Remove test documents if they were created for testing
            if document_id:
                self.db.gp_scanned_documents.delete_one({"document_id": document_id})
                self.db.gp_validated_documents.delete_one({"document_id": document_id})
                print(f"🧹 Cleaned up test data for document: {document_id}")
        except Exception as e:
            print(f"⚠️  Error cleaning up test data: {str(e)}")
    
    def close_connections(self):
        """Close database connections"""
        try:
            self.mongo_client.close()
        except:
            pass

def main():
    """Main test execution"""
    tester = GPValidationTester()
    
    try:
        # Run the complete workflow test
        success = tester.run_complete_validation_workflow_test()
        
        # Print detailed results
        print("\n" + "="*60)
        print("DETAILED TEST RESULTS")
        print("="*60)
        
        for result in tester.test_results:
            status = "✅" if result['success'] else "❌"
            print(f"{status} {result['test']}: {result['message']}")
        
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