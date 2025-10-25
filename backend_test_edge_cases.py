#!/usr/bin/env python3
"""
Edge Cases and Error Scenario Testing for GP Validation Save Endpoint
"""

import requests
import json
import uuid
from datetime import datetime, timezone
import os
from pymongo import MongoClient

# Configuration
BACKEND_URL = "https://medical-records-10.preview.emergentagent.com/api"
MONGO_URL = "mongodb://localhost:27017"
DATABASE_NAME = "surgiscan_documents"

class GPValidationEdgeCaseTester:
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
    
    def test_invalid_document_id(self):
        """Test with non-existent document ID"""
        try:
            fake_document_id = str(uuid.uuid4())
            payload = {
                "document_id": fake_document_id,
                "parsed_data": {"demographics": {"patient_name": "Test"}},
                "modifications": [],
                "status": "approved",
                "notes": "Test validation"
            }
            
            response = requests.post(
                f"{self.backend_url}/gp/validation/save",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 404:
                self.log_test("Invalid Document ID", True, "Correctly returned 404 for non-existent document")
                return True
            else:
                self.log_test("Invalid Document ID", False, f"Expected 404, got {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Invalid Document ID", False, f"Request failed: {str(e)}")
            return False
    
    def test_missing_required_fields(self):
        """Test with missing required fields"""
        try:
            # Get a valid document ID
            doc = self.db.gp_scanned_documents.find_one({})
            if not doc:
                self.log_test("Missing Required Fields", False, "No test document available")
                return False
            
            document_id = doc.get('document_id')
            
            # Test missing document_id
            payload = {
                "parsed_data": {"demographics": {"patient_name": "Test"}},
                "modifications": [],
                "status": "approved"
            }
            
            response = requests.post(
                f"{self.backend_url}/gp/validation/save",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 422:  # Validation error
                self.log_test("Missing Required Fields", True, "Correctly rejected request with missing document_id")
                return True
            else:
                self.log_test("Missing Required Fields", False, f"Expected 422, got {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Missing Required Fields", False, f"Request failed: {str(e)}")
            return False
    
    def test_empty_modifications_array(self):
        """Test with empty modifications array (valid scenario)"""
        try:
            # Get a valid document ID
            doc = self.db.gp_scanned_documents.find_one({})
            if not doc:
                self.log_test("Empty Modifications Array", False, "No test document available")
                return False
            
            document_id = doc.get('document_id')
            
            payload = {
                "document_id": document_id,
                "parsed_data": {
                    "demographics": {"patient_name": "Test Patient"},
                    "chronic_summary": {},
                    "vitals": [],
                    "clinical_notes": "No changes made"
                },
                "modifications": [],  # Empty modifications
                "status": "approved",
                "notes": "No modifications needed"
            }
            
            response = requests.post(
                f"{self.backend_url}/gp/validation/save",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('modifications_count') == 0:
                    self.log_test("Empty Modifications Array", True, "Successfully handled empty modifications")
                    return True
                else:
                    self.log_test("Empty Modifications Array", False, f"Wrong modification count: {result.get('modifications_count')}")
                    return False
            else:
                self.log_test("Empty Modifications Array", False, f"Expected 200, got {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Empty Modifications Array", False, f"Request failed: {str(e)}")
            return False
    
    def test_large_modifications_array(self):
        """Test with large number of modifications"""
        try:
            # Get a valid document ID
            doc = self.db.gp_scanned_documents.find_one({})
            if not doc:
                self.log_test("Large Modifications Array", False, "No test document available")
                return False
            
            document_id = doc.get('document_id')
            
            # Create 50 modifications
            modifications = []
            for i in range(50):
                modifications.append({
                    "field_path": f"test_field_{i}",
                    "original_value": f"original_{i}",
                    "new_value": f"new_{i}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "modification_type": "edit"
                })
            
            payload = {
                "document_id": document_id,
                "parsed_data": {
                    "demographics": {"patient_name": "Test Patient"},
                    "chronic_summary": {},
                    "vitals": [],
                    "clinical_notes": "Many modifications made"
                },
                "modifications": modifications,
                "status": "approved",
                "notes": "Stress test with many modifications"
            }
            
            response = requests.post(
                f"{self.backend_url}/gp/validation/save",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('modifications_count') == 50:
                    self.log_test("Large Modifications Array", True, "Successfully handled 50 modifications")
                    return True
                else:
                    self.log_test("Large Modifications Array", False, f"Wrong modification count: {result.get('modifications_count')}")
                    return False
            else:
                self.log_test("Large Modifications Array", False, f"Expected 200, got {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Large Modifications Array", False, f"Request failed: {str(e)}")
            return False
    
    def test_invalid_json_payload(self):
        """Test with malformed JSON"""
        try:
            # Send malformed JSON
            response = requests.post(
                f"{self.backend_url}/gp/validation/save",
                data="invalid json {",  # Malformed JSON
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 422:  # Validation error
                self.log_test("Invalid JSON Payload", True, "Correctly rejected malformed JSON")
                return True
            else:
                self.log_test("Invalid JSON Payload", False, f"Expected 422, got {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Invalid JSON Payload", False, f"Request failed: {str(e)}")
            return False
    
    def test_different_status_values(self):
        """Test with different status values"""
        try:
            # Get a valid document ID
            doc = self.db.gp_scanned_documents.find_one({})
            if not doc:
                self.log_test("Different Status Values", False, "No test document available")
                return False
            
            document_id = doc.get('document_id')
            
            # Test with "rejected" status
            payload = {
                "document_id": document_id,
                "parsed_data": {
                    "demographics": {"patient_name": "Test Patient"},
                    "chronic_summary": {},
                    "vitals": [],
                    "clinical_notes": "Rejected validation"
                },
                "modifications": [],
                "status": "rejected",
                "notes": "Document rejected due to poor quality"
            }
            
            response = requests.post(
                f"{self.backend_url}/gp/validation/save",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                self.log_test("Different Status Values", True, "Successfully handled 'rejected' status")
                return True
            else:
                self.log_test("Different Status Values", False, f"Expected 200, got {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Different Status Values", False, f"Request failed: {str(e)}")
            return False
    
    def run_edge_case_tests(self):
        """Run all edge case tests"""
        print("\n" + "="*60)
        print("GP VALIDATION SAVE ENDPOINT - EDGE CASES & ERROR SCENARIOS")
        print("="*60)
        
        tests = [
            self.test_invalid_document_id,
            self.test_missing_required_fields,
            self.test_empty_modifications_array,
            self.test_large_modifications_array,
            self.test_invalid_json_payload,
            self.test_different_status_values
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test in tests:
            if test():
                passed_tests += 1
        
        print("\n" + "="*60)
        print("EDGE CASE TEST SUMMARY")
        print("="*60)
        print(f"Passed: {passed_tests}/{total_tests}")
        
        if passed_tests == total_tests:
            print("✅ ALL EDGE CASE TESTS PASSED")
        else:
            print("❌ SOME EDGE CASE TESTS FAILED")
        
        return passed_tests == total_tests
    
    def close_connections(self):
        """Close database connections"""
        try:
            self.mongo_client.close()
        except:
            pass

def main():
    """Main test execution"""
    tester = GPValidationEdgeCaseTester()
    
    try:
        success = tester.run_edge_case_tests()
        
        # Print detailed results
        print("\n" + "="*60)
        print("DETAILED EDGE CASE TEST RESULTS")
        print("="*60)
        
        for result in tester.test_results:
            status = "✅" if result['success'] else "❌"
            print(f"{status} {result['test']}: {result['message']}")
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"\n💥 Unexpected error: {str(e)}")
        return 1
    finally:
        tester.close_connections()

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)