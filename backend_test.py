#!/usr/bin/env python3
"""
Backend API Testing for AI Scribe Endpoints
Tests the AI Scribe audio transcription and SOAP note generation endpoints
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

# Configuration
BACKEND_URL = "https://healthcare-ehr.preview.emergentagent.com/api"
MONGO_URL = "mongodb://localhost:27017"
DATABASE_NAME = "surgiscan_documents"

class AIScribeTester:
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
    
    def create_test_audio_file(self):
        """Create a test audio file for transcription testing"""
        try:
            # Create a simple WAV file with a sine wave (simulating speech)
            sample_rate = 16000  # 16kHz sample rate
            duration = 3  # 3 seconds
            frequency = 440  # A4 note frequency
            
            # Generate sine wave data
            samples = []
            for i in range(int(sample_rate * duration)):
                # Create a simple sine wave that varies in frequency (simulating speech patterns)
                t = i / sample_rate
                # Mix multiple frequencies to simulate speech-like audio
                sample = (
                    0.3 * math.sin(2 * math.pi * frequency * t) +
                    0.2 * math.sin(2 * math.pi * (frequency * 1.5) * t) +
                    0.1 * math.sin(2 * math.pi * (frequency * 0.7) * t)
                )
                # Convert to 16-bit integer
                sample_int = int(sample * 32767)
                samples.append(sample_int)
            
            # Create WAV file in memory
            audio_buffer = io.BytesIO()
            
            with wave.open(audio_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                
                # Write samples
                for sample in samples:
                    wav_file.writeframes(struct.pack('<h', sample))
            
            audio_buffer.seek(0)
            audio_data = audio_buffer.getvalue()
            
            self.log_test("Create Test Audio", True, f"Created {len(audio_data)} byte WAV file")
            return audio_data, "test_consultation.wav"
            
        except Exception as e:
            self.log_test("Create Test Audio", False, f"Error creating test audio: {str(e)}")
            return None, None
    
    def test_ai_scribe_transcribe_endpoint(self):
        """Test the AI Scribe audio transcription endpoint"""
        try:
            # Create test audio file
            audio_data, filename = self.create_test_audio_file()
            if not audio_data:
                return False, None
            
            # Prepare multipart form data
            files = {
                'file': (filename, audio_data, 'audio/wav')
            }
            
            # Make API call
            response = requests.post(
                f"{self.backend_url}/ai-scribe/transcribe",
                files=files,
                timeout=60  # Longer timeout for transcription
            )
            
            if response.status_code == 200:
                result = response.json()
                expected_fields = ['status', 'transcription']
                
                if all(field in result for field in expected_fields):
                    if result['status'] == 'success' and result['transcription']:
                        transcription_length = len(result['transcription'])
                        self.log_test("AI Scribe Transcription API", True, 
                                    f"Successfully transcribed audio ({transcription_length} characters)")
                        return True, result
                    else:
                        self.log_test("AI Scribe Transcription API", False, 
                                    f"Invalid response: status={result.get('status')}, transcription_empty={not result.get('transcription')}")
                        return False, result
                else:
                    missing_fields = [f for f in expected_fields if f not in result]
                    self.log_test("AI Scribe Transcription API", False, 
                                f"Missing fields in response: {missing_fields}")
                    return False, result
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("AI Scribe Transcription API", False, error_msg)
                return False, None
                
        except Exception as e:
            self.log_test("AI Scribe Transcription API", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_ai_scribe_soap_generation_endpoint(self, transcription_text):
        """Test the AI Scribe SOAP note generation endpoint"""
        try:
            # Prepare test data
            test_patient_context = {
                "name": "Sarah Johnson",
                "age": 42,
                "chronic_conditions": ["Hypertension", "Type 2 Diabetes"]
            }
            
            payload = {
                "transcription": transcription_text,
                "patient_context": test_patient_context
            }
            
            # Make API call
            response = requests.post(
                f"{self.backend_url}/ai-scribe/generate-soap",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=60  # Longer timeout for LLM generation
            )
            
            if response.status_code == 200:
                result = response.json()
                expected_fields = ['status', 'soap_notes']
                
                if all(field in result for field in expected_fields):
                    if result['status'] == 'success' and result['soap_notes']:
                        soap_length = len(result['soap_notes'])
                        # Check if SOAP notes contain expected sections
                        soap_text = result['soap_notes'].upper()
                        has_subjective = 'SUBJECTIVE' in soap_text or 'S:' in soap_text
                        has_objective = 'OBJECTIVE' in soap_text or 'O:' in soap_text
                        has_assessment = 'ASSESSMENT' in soap_text or 'A:' in soap_text
                        has_plan = 'PLAN' in soap_text or 'P:' in soap_text
                        
                        soap_sections = sum([has_subjective, has_objective, has_assessment, has_plan])
                        
                        if soap_sections >= 3:  # At least 3 out of 4 SOAP sections
                            self.log_test("AI Scribe SOAP Generation API", True, 
                                        f"Successfully generated SOAP notes ({soap_length} characters, {soap_sections}/4 sections)")
                            return True, result
                        else:
                            self.log_test("AI Scribe SOAP Generation API", False, 
                                        f"SOAP notes missing sections (only {soap_sections}/4 found)")
                            return False, result
                    else:
                        self.log_test("AI Scribe SOAP Generation API", False, 
                                    f"Invalid response: status={result.get('status')}, soap_notes_empty={not result.get('soap_notes')}")
                        return False, result
                else:
                    missing_fields = [f for f in expected_fields if f not in result]
                    self.log_test("AI Scribe SOAP Generation API", False, 
                                f"Missing fields in response: {missing_fields}")
                    return False, result
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("AI Scribe SOAP Generation API", False, error_msg)
                return False, None
                
        except Exception as e:
            self.log_test("AI Scribe SOAP Generation API", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_ai_scribe_error_handling(self):
        """Test AI Scribe endpoints error handling"""
        try:
            # Test 1: Transcribe endpoint with invalid file
            invalid_files = {
                'file': ('test.txt', b'This is not an audio file', 'text/plain')
            }
            
            response = requests.post(
                f"{self.backend_url}/ai-scribe/transcribe",
                files=invalid_files,
                timeout=30
            )
            
            transcribe_error_handled = response.status_code in [400, 422, 500]
            
            # Test 2: SOAP generation with empty transcription
            empty_payload = {
                "transcription": "",
                "patient_context": {}
            }
            
            response = requests.post(
                f"{self.backend_url}/ai-scribe/generate-soap",
                json=empty_payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            soap_error_handled = response.status_code in [400, 422, 500]
            
            if transcribe_error_handled and soap_error_handled:
                self.log_test("AI Scribe Error Handling", True, 
                            "Both endpoints properly handle invalid inputs")
                return True
            else:
                self.log_test("AI Scribe Error Handling", False, 
                            f"Error handling issues: transcribe={transcribe_error_handled}, soap={soap_error_handled}")
                return False
                
        except Exception as e:
            self.log_test("AI Scribe Error Handling", False, f"Error testing error handling: {str(e)}")
            return False
    
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