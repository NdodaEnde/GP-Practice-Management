#!/usr/bin/env python3
"""
Backend API Testing for Queue Management System Phase 2
Tests the complete Queue Management System including:
- Patient check-in flow
- Queue display and stats
- Workstation dashboard integration
- Queue status updates
- Integration points with AI Scribe
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
BACKEND_URL = "https://aihealth-clinic.preview.emergentagent.com/api"
MONGO_URL = "mongodb://localhost:27017"
DATABASE_NAME = "surgiscan_documents"
MICROSERVICE_URL = "http://localhost:5001"

class QueueManagementTester:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.mongo_client = MongoClient(MONGO_URL)
        self.db = self.mongo_client["surgiscan_db"]  # Use the main database
        self.test_results = []
        self.test_patient_id = None
        self.test_patient_id_2 = None
        self.test_queue_id = None
        self.test_queue_id_2 = None
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
            
            # Check if queue_entries collection exists
            collections = self.db.list_collection_names()
            has_queue_collection = 'queue_entries' in collections
            
            if has_queue_collection:
                queue_count = self.db.queue_entries.count_documents({})
                self.log_test("MongoDB Connection", True, f"Connected. Found {queue_count} queue entries")
                return True, queue_count
            else:
                self.log_test("MongoDB Connection", True, "Connected but no queue_entries collection found")
                return True, 0
                
        except Exception as e:
            self.log_test("MongoDB Connection", False, f"MongoDB connection failed: {str(e)}")
            return False, 0
    
    def create_test_patients(self):
        """Create test patients for queue testing"""
        try:
            # Patient 1 - existing patient for check-in
            patient_data_1 = {
                "first_name": "Sarah",
                "last_name": "Johnson", 
                "dob": "1985-07-22",
                "id_number": "8507225555084",
                "contact_number": "+27123456789",
                "email": "sarah.johnson@example.com",
                "address": "456 Oak Street, Cape Town",
                "medical_aid": "Discovery Health"
            }
            
            response = requests.post(
                f"{self.backend_url}/patients",
                json=patient_data_1,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                self.test_patient_id = result['id']
                self.log_test("Create Test Patient 1", True, f"Created test patient 1: {self.test_patient_id}")
            else:
                self.log_test("Create Test Patient 1", False, f"Failed to create patient 1: {response.status_code}")
                return False
            
            # Patient 2 - for new patient registration + check-in
            patient_data_2 = {
                "first_name": "Michael",
                "last_name": "Brown", 
                "dob": "1978-11-15",
                "id_number": "7811155555085",
                "contact_number": "+27987654321",
                "email": "michael.brown@example.com",
                "address": "789 Pine Avenue, Johannesburg",
                "medical_aid": "Momentum Health"
            }
            
            response = requests.post(
                f"{self.backend_url}/patients",
                json=patient_data_2,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                self.test_patient_id_2 = result['id']
                self.log_test("Create Test Patient 2", True, f"Created test patient 2: {self.test_patient_id_2}")
                return True
            else:
                self.log_test("Create Test Patient 2", False, f"Failed to create patient 2: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Create Test Patients", False, f"Error creating test patients: {str(e)}")
            return False
    
    def test_queue_check_in_existing_patient(self):
        """Test Scenario 1: Check-in flow with existing patient"""
        try:
            if not self.test_patient_id:
                self.log_test("Queue Check-in (Existing)", False, "No test patient available")
                return False, None
            
            # Test check-in with chief complaint
            check_in_data = {
                "patient_id": self.test_patient_id,
                "reason_for_visit": "Routine annual physical examination",
                "priority": "normal"
            }
            
            response = requests.post(
                f"{self.backend_url}/queue/check-in",
                json=check_in_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                expected_fields = ['status', 'queue_id', 'queue_number', 'patient_name']
                
                if all(field in result for field in expected_fields):
                    if result['status'] == 'success':
                        self.test_queue_id = result['queue_id']
                        queue_number = result['queue_number']
                        patient_name = result['patient_name']
                        
                        self.log_test("Queue Check-in (Existing)", True, 
                                    f"Successfully checked in patient. Queue #{queue_number}, Name: {patient_name}")
                        
                        # Verify queue entry was created in MongoDB
                        queue_entry = self.db.queue_entries.find_one({'id': self.test_queue_id})
                        if queue_entry:
                            if queue_entry.get('reason_for_visit') == check_in_data['reason_for_visit']:
                                self.log_test("Queue Entry Verification", True, 
                                            "Queue entry created in MongoDB with correct chief complaint")
                            else:
                                self.log_test("Queue Entry Verification", False, 
                                            "Chief complaint not saved correctly in MongoDB")
                        else:
                            self.log_test("Queue Entry Verification", False, 
                                        "Queue entry not found in MongoDB")
                        
                        return True, result
                    else:
                        self.log_test("Queue Check-in (Existing)", False, 
                                    f"Check-in failed: {result.get('status')}")
                        return False, result
                else:
                    missing_fields = [f for f in expected_fields if f not in result]
                    self.log_test("Queue Check-in (Existing)", False, 
                                f"Missing fields in response: {missing_fields}")
                    return False, result
            else:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                self.log_test("Queue Check-in (Existing)", False, error_msg)
                return False, None
                
        except Exception as e:
            self.log_test("Queue Check-in (Existing)", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_queue_check_in_new_patient(self):
        """Test Scenario 2: New patient registration + check-in"""
        try:
            if not self.test_patient_id_2:
                self.log_test("Queue Check-in (New Patient)", False, "No second test patient available")
                return False, None
            
            # Test check-in with new patient
            check_in_data = {
                "patient_id": self.test_patient_id_2,
                "reason_for_visit": "Chest pain and shortness of breath",
                "priority": "urgent"
            }
            
            response = requests.post(
                f"{self.backend_url}/queue/check-in",
                json=check_in_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    self.test_queue_id_2 = result['queue_id']
                    self.log_test("Queue Check-in (New Patient)", True, 
                                f"Successfully checked in new patient. Queue #{result['queue_number']}")
                    return True, result
                else:
                    self.log_test("Queue Check-in (New Patient)", False, 
                                f"Check-in failed: {result.get('status')}")
                    return False, result
            else:
                self.log_test("Queue Check-in (New Patient)", False, 
                            f"API returned status {response.status_code}")
                return False, None
                
        except Exception as e:
            self.log_test("Queue Check-in (New Patient)", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_queue_current_display(self):
        """Test Scenario 2: Queue display functionality"""
        try:
            # Test getting current queue
            response = requests.get(
                f"{self.backend_url}/queue/current",
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                expected_fields = ['status', 'date', 'queue', 'count']
                
                if all(field in result for field in expected_fields):
                    if result['status'] == 'success':
                        queue_count = result['count']
                        queue_entries = result['queue']
                        
                        self.log_test("Queue Current Display", True, 
                                    f"Successfully retrieved current queue with {queue_count} entries")
                        
                        # Verify queue entries have proper structure
                        if queue_entries and len(queue_entries) > 0:
                            first_entry = queue_entries[0]
                            entry_fields = ['id', 'queue_number', 'patient_name', 'reason_for_visit', 'status']
                            present_fields = [f for f in entry_fields if f in first_entry]
                            
                            if len(present_fields) >= 4:
                                self.log_test("Queue Entry Structure", True, 
                                            f"Queue entries have proper structure ({len(present_fields)}/{len(entry_fields)} fields)")
                                
                                # Check if entries are sorted by queue_number
                                if len(queue_entries) > 1:
                                    sorted_correctly = all(
                                        queue_entries[i]['queue_number'] <= queue_entries[i+1]['queue_number']
                                        for i in range(len(queue_entries)-1)
                                    )
                                    if sorted_correctly:
                                        self.log_test("Queue Sorting", True, "Queue entries properly sorted by queue_number")
                                    else:
                                        self.log_test("Queue Sorting", False, "Queue entries not properly sorted")
                            else:
                                self.log_test("Queue Entry Structure", False, 
                                            f"Queue entries missing fields ({len(present_fields)}/{len(entry_fields)})")
                        
                        return True, result
                    else:
                        self.log_test("Queue Current Display", False, 
                                    f"Queue display failed: {result.get('status')}")
                        return False, result
                else:
                    missing_fields = [f for f in expected_fields if f not in result]
                    self.log_test("Queue Current Display", False, 
                                f"Missing fields in response: {missing_fields}")
                    return False, result
            else:
                self.log_test("Queue Current Display", False, 
                            f"API returned status {response.status_code}")
                return False, None
                
        except Exception as e:
            self.log_test("Queue Current Display", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_queue_stats(self):
        """Test Scenario 2: Queue statistics"""
        try:
            response = requests.get(
                f"{self.backend_url}/queue/stats",
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                expected_fields = ['status', 'date', 'stats']
                
                if all(field in result for field in expected_fields):
                    if result['status'] == 'success':
                        stats = result['stats']
                        stat_fields = ['total_checked_in', 'waiting', 'in_progress', 'completed']
                        
                        if all(field in stats for field in stat_fields):
                            waiting_count = stats['waiting']
                            in_progress_count = stats['in_progress']
                            completed_count = stats['completed']
                            
                            self.log_test("Queue Stats", True, 
                                        f"Stats: {waiting_count} waiting, {in_progress_count} in progress, {completed_count} completed")
                            return True, result
                        else:
                            missing_stat_fields = [f for f in stat_fields if f not in stats]
                            self.log_test("Queue Stats", False, 
                                        f"Missing stat fields: {missing_stat_fields}")
                            return False, result
                    else:
                        self.log_test("Queue Stats", False, 
                                    f"Stats request failed: {result.get('status')}")
                        return False, result
                else:
                    missing_fields = [f for f in expected_fields if f not in result]
                    self.log_test("Queue Stats", False, 
                                f"Missing fields in response: {missing_fields}")
                    return False, result
            else:
                self.log_test("Queue Stats", False, 
                            f"API returned status {response.status_code}")
                return False, None
                
        except Exception as e:
            self.log_test("Queue Stats", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_workstation_call_next(self):
        """Test Scenario 3: Workstation Dashboard - Call next patient"""
        try:
            if not self.test_queue_id:
                self.log_test("Workstation Call Next", False, "No test queue entry available")
                return False, None
            
            # Test calling next patient to consultation
            response = requests.post(
                f"{self.backend_url}/queue/{self.test_queue_id}/call-next",
                params={"station": "consultation"},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                expected_fields = ['status', 'message', 'queue_number', 'patient_name']
                
                if all(field in result for field in expected_fields):
                    if result['status'] == 'success':
                        self.log_test("Workstation Call Next", True, 
                                    f"Successfully called patient {result['patient_name']} to consultation")
                        
                        # Verify status change in MongoDB
                        queue_entry = self.db.queue_entries.find_one({'id': self.test_queue_id})
                        if queue_entry and queue_entry.get('status') == 'in_consultation':
                            self.log_test("Status Update Verification", True, 
                                        "Queue status correctly updated to 'in_consultation'")
                            
                            # Check if timestamp was recorded
                            if queue_entry.get('called_at'):
                                self.log_test("Timestamp Recording", True, 
                                            "Call timestamp properly recorded")
                            else:
                                self.log_test("Timestamp Recording", False, 
                                            "Call timestamp not recorded")
                        else:
                            self.log_test("Status Update Verification", False, 
                                        "Queue status not updated correctly in MongoDB")
                        
                        return True, result
                    else:
                        self.log_test("Workstation Call Next", False, 
                                    f"Call next failed: {result.get('status')}")
                        return False, result
                else:
                    missing_fields = [f for f in expected_fields if f not in result]
                    self.log_test("Workstation Call Next", False, 
                                f"Missing fields in response: {missing_fields}")
                    return False, result
            else:
                self.log_test("Workstation Call Next", False, 
                            f"API returned status {response.status_code}")
                return False, None
                
        except Exception as e:
            self.log_test("Workstation Call Next", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_patient_details_with_vitals(self):
        """Test Scenario 3: Patient details endpoint with vitals"""
        try:
            if not self.test_patient_id:
                self.log_test("Patient Details with Vitals", False, "No test patient available")
                return False, None
            
            # First create an encounter with vitals for the patient
            encounter_data = {
                "patient_id": self.test_patient_id,
                "chief_complaint": "Routine checkup",
                "vitals": {
                    "blood_pressure": "120/80",
                    "heart_rate": 72,
                    "temperature": 36.6,
                    "weight": 70.5,
                    "height": 175.0,
                    "oxygen_saturation": 98
                }
            }
            
            encounter_response = requests.post(
                f"{self.backend_url}/encounters",
                json=encounter_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if encounter_response.status_code == 200:
                encounter_result = encounter_response.json()
                self.test_encounter_id = encounter_result['id']
                
                # Now test getting patient details
                response = requests.get(
                    f"{self.backend_url}/patients/{self.test_patient_id}",
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    expected_fields = ['id', 'first_name', 'last_name', 'dob']
                    
                    if all(field in result for field in expected_fields):
                        self.log_test("Patient Details", True, 
                                    f"Successfully retrieved patient details for {result['first_name']} {result['last_name']}")
                        
                        # Note: The current implementation doesn't include latest_vitals in patient response
                        # This is a gap that should be noted
                        if 'latest_vitals' in result:
                            self.log_test("Latest Vitals Integration", True, 
                                        "Patient response includes latest vitals")
                        else:
                            self.log_test("Latest Vitals Integration", False, 
                                        "MISSING FEATURE: Patient response should include latest_vitals field")
                        
                        return True, result
                    else:
                        missing_fields = [f for f in expected_fields if f not in result]
                        self.log_test("Patient Details", False, 
                                    f"Missing fields in response: {missing_fields}")
                        return False, result
                else:
                    self.log_test("Patient Details", False, 
                                f"API returned status {response.status_code}")
                    return False, None
            else:
                self.log_test("Patient Details with Vitals", False, 
                            f"Failed to create encounter with vitals: {encounter_response.status_code}")
                return False, None
                
        except Exception as e:
            self.log_test("Patient Details with Vitals", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_queue_status_updates(self):
        """Test Scenario 4: Queue status updates"""
        try:
            if not self.test_queue_id:
                self.log_test("Queue Status Updates", False, "No test queue entry available")
                return False, None
            
            # Test updating status from in_consultation to completed
            update_data = {
                "status": "completed",
                "station": "consultation",
                "notes": "Consultation completed successfully"
            }
            
            response = requests.put(
                f"{self.backend_url}/queue/{self.test_queue_id}/update-status",
                json=update_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                expected_fields = ['status', 'message', 'queue_id']
                
                if all(field in result for field in expected_fields):
                    if result['status'] == 'success':
                        self.log_test("Queue Status Updates", True, 
                                    "Successfully updated queue status to completed")
                        
                        # Verify status change and timestamp in MongoDB
                        queue_entry = self.db.queue_entries.find_one({'id': self.test_queue_id})
                        if queue_entry:
                            if queue_entry.get('status') == 'completed':
                                self.log_test("Status Change Verification", True, 
                                            "Queue status correctly updated to 'completed'")
                                
                                # Check if completion timestamp was recorded
                                if queue_entry.get('completed_at'):
                                    self.log_test("Completion Timestamp", True, 
                                                "Completion timestamp properly recorded")
                                else:
                                    self.log_test("Completion Timestamp", False, 
                                                "Completion timestamp not recorded")
                                
                                # Check audit logging
                                audit_entry = self.db.audit_events.find_one({
                                    'event_type': 'queue_status_updated',
                                    'queue_id': self.test_queue_id
                                })
                                if audit_entry:
                                    self.log_test("Audit Logging", True, 
                                                "Status update properly logged in audit events")
                                else:
                                    self.log_test("Audit Logging", False, 
                                                "Status update not found in audit events")
                            else:
                                self.log_test("Status Change Verification", False, 
                                            f"Queue status not updated correctly: {queue_entry.get('status')}")
                        else:
                            self.log_test("Status Change Verification", False, 
                                        "Queue entry not found in MongoDB")
                        
                        return True, result
                    else:
                        self.log_test("Queue Status Updates", False, 
                                    f"Status update failed: {result.get('status')}")
                        return False, result
                else:
                    missing_fields = [f for f in expected_fields if f not in result]
                    self.log_test("Queue Status Updates", False, 
                                f"Missing fields in response: {missing_fields}")
                    return False, result
            else:
                self.log_test("Queue Status Updates", False, 
                            f"API returned status {response.status_code}")
                return False, None
                
        except Exception as e:
            self.log_test("Queue Status Updates", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_ai_scribe_integration_endpoints(self):
        """Test Scenario 5: Integration points - AI Scribe navigation endpoints"""
        try:
            if not self.test_patient_id:
                self.log_test("AI Scribe Integration", False, "No test patient available")
                return False, None
            
            # Test if patient endpoint exists (for EHR viewing)
            response = requests.get(
                f"{self.backend_url}/patients/{self.test_patient_id}",
                timeout=30
            )
            
            if response.status_code == 200:
                self.log_test("EHR Navigation Endpoint", True, 
                            "Patient endpoint accessible for EHR viewing")
            else:
                self.log_test("EHR Navigation Endpoint", False, 
                            f"Patient endpoint not accessible: {response.status_code}")
                return False, None
            
            # Check if AI Scribe endpoint exists (mentioned in review request)
            # Note: The review mentions /patients/{id}/ai-scribe but this doesn't exist in current backend
            ai_scribe_response = requests.get(
                f"{self.backend_url}/patients/{self.test_patient_id}/ai-scribe",
                timeout=30
            )
            
            if ai_scribe_response.status_code == 200:
                self.log_test("AI Scribe Navigation Endpoint", True, 
                            "AI Scribe navigation endpoint exists")
            else:
                self.log_test("AI Scribe Navigation Endpoint", False, 
                            f"MISSING FEATURE: /patients/{{id}}/ai-scribe endpoint not implemented (status: {ai_scribe_response.status_code})")
            
            # Test AI Scribe transcription endpoint
            transcribe_response = requests.get(
                f"{self.backend_url}/ai-scribe/transcribe",
                timeout=10
            )
            
            # We expect this to fail without a file, but endpoint should exist
            if transcribe_response.status_code in [400, 422]:  # Bad request or validation error
                self.log_test("AI Scribe Transcribe Endpoint", True, 
                            "AI Scribe transcription endpoint exists (validation error expected)")
            elif transcribe_response.status_code == 404:
                self.log_test("AI Scribe Transcribe Endpoint", False, 
                            "AI Scribe transcription endpoint not found")
            else:
                self.log_test("AI Scribe Transcribe Endpoint", True, 
                            f"AI Scribe transcription endpoint accessible (status: {transcribe_response.status_code})")
            
            return True, None
                
        except Exception as e:
            self.log_test("AI Scribe Integration", False, f"Request failed: {str(e)}")
            return False, None
    
    def test_consultation_call_next_endpoint(self):
        """Test the specific /api/queue/consultation/call-next endpoint mentioned in review"""
        try:
            # Test the specific endpoint mentioned in the review request
            response = requests.post(
                f"{self.backend_url}/queue/consultation/call-next",
                timeout=30
            )
            
            if response.status_code == 200:
                self.log_test("Consultation Call-Next Endpoint", True, 
                            "Consultation call-next endpoint exists and accessible")
                return True, response.json()
            elif response.status_code == 404:
                self.log_test("Consultation Call-Next Endpoint", False, 
                            "MISSING FEATURE: /api/queue/consultation/call-next endpoint not implemented")
                return False, None
            else:
                self.log_test("Consultation Call-Next Endpoint", False, 
                            f"Consultation call-next endpoint error: {response.status_code}")
                return False, None
                
        except Exception as e:
            self.log_test("Consultation Call-Next Endpoint", False, f"Request failed: {str(e)}")
            return False, None
    
    # Old GP document methods removed - replaced with queue management tests above
    
    # Additional old GP methods removed for queue management focus
    
    # Old GP test methods removed - focusing on queue management
    
    def run_complete_queue_management_test(self):
        """Run the complete Queue Management System Phase 2 test"""
        print("\n" + "="*80)
        print("QUEUE MANAGEMENT SYSTEM PHASE 2 - COMPLETE WORKFLOW TEST")
        print("="*80)
        
        # Step 1: Test backend connectivity
        if not self.test_backend_health():
            print("\n❌ Cannot proceed - Backend is not accessible")
            return False
        
        # Step 2: Test MongoDB connectivity
        mongo_ok, queue_count = self.test_mongodb_connection()
        if not mongo_ok:
            print("\n⚠️  MongoDB not accessible - Queue storage may not work")
        
        # Step 3: Create test patients
        print("\n👤 Creating test patients...")
        patients_created = self.create_test_patients()
        if not patients_created:
            print("\n❌ Cannot proceed - Failed to create test patients")
            return False
        
        # Step 4: Test Scenario 1 - Check-in Flow
        print("\n📝 Testing Scenario 1: Check-in Flow...")
        print("  Testing existing patient check-in...")
        checkin_existing_success, _ = self.test_queue_check_in_existing_patient()
        
        print("  Testing new patient check-in...")
        checkin_new_success, _ = self.test_queue_check_in_new_patient()
        
        # Step 5: Test Scenario 2 - Queue Display
        print("\n📊 Testing Scenario 2: Queue Display...")
        print("  Testing current queue display...")
        queue_display_success, _ = self.test_queue_current_display()
        
        print("  Testing queue statistics...")
        queue_stats_success, _ = self.test_queue_stats()
        
        # Step 6: Test Scenario 3 - Workstation Dashboard Integration
        print("\n🖥️  Testing Scenario 3: Workstation Dashboard Integration...")
        print("  Testing call next patient...")
        call_next_success, _ = self.test_workstation_call_next()
        
        print("  Testing patient details with vitals...")
        patient_details_success, _ = self.test_patient_details_with_vitals()
        
        # Step 7: Test Scenario 4 - Queue Status Updates
        print("\n🔄 Testing Scenario 4: Queue Status Updates...")
        status_update_success, _ = self.test_queue_status_updates()
        
        # Step 8: Test Scenario 5 - Integration Points
        print("\n🔗 Testing Scenario 5: Integration Points...")
        print("  Testing AI Scribe integration endpoints...")
        ai_scribe_integration_success, _ = self.test_ai_scribe_integration_endpoints()
        
        print("  Testing consultation call-next endpoint...")
        consultation_endpoint_success, _ = self.test_consultation_call_next_endpoint()
        
        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        # Determine overall success
        critical_tests = [
            checkin_existing_success, checkin_new_success,
            queue_display_success, queue_stats_success,
            call_next_success, status_update_success
        ]
        critical_success = all(critical_tests)
        
        secondary_tests = [
            patient_details_success, ai_scribe_integration_success, 
            consultation_endpoint_success
        ]
        all_tests_passed = critical_success and all(secondary_tests)
        
        if critical_success:
            if all_tests_passed:
                print("✅ ALL TESTS PASSED - Queue Management System Phase 2 is working correctly")
                print("✅ CRITICAL: All core queue management features are functional")
            else:
                print("✅ CRITICAL TESTS PASSED - Core queue management workflow is working")
                print("⚠️  Some integration features missing but core functionality works")
        else:
            print("❌ CRITICAL TESTS FAILED - Queue management system has issues")
            failed_tests = []
            if not checkin_existing_success: failed_tests.append("Existing Patient Check-in")
            if not checkin_new_success: failed_tests.append("New Patient Check-in")
            if not queue_display_success: failed_tests.append("Queue Display")
            if not queue_stats_success: failed_tests.append("Queue Statistics")
            if not call_next_success: failed_tests.append("Call Next Patient")
            if not status_update_success: failed_tests.append("Status Updates")
            print(f"❌ Failed components: {', '.join(failed_tests)}")
        
        return critical_success
    
    def cleanup_test_data(self):
        """Clean up test data"""
        try:
            # Clean up test patients if created
            if self.test_patient_id:
                print(f"🧹 Test patient 1 {self.test_patient_id} would be cleaned up in production")
            
            if self.test_patient_id_2:
                print(f"🧹 Test patient 2 {self.test_patient_id_2} would be cleaned up in production")
            
            # Clean up queue entries if created
            if self.test_queue_id:
                print(f"🧹 Test queue entry {self.test_queue_id} would be cleaned up in production")
            
            if self.test_queue_id_2:
                print(f"🧹 Test queue entry 2 {self.test_queue_id_2} would be cleaned up in production")
            
            print("🧹 Queue management tests completed")
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
    tester = QueueManagementTester()
    
    try:
        # Run the complete workflow test
        success = tester.run_complete_queue_management_test()
        
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
