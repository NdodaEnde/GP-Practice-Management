import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, UserPlus, User, Calendar, Phone, Mail, FileText, CheckCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { patientAPI } from '@/services/api';
import { useToast } from '@/hooks/use-toast';
import axios from 'axios';

const PatientRegistry = () => {
  const [patients, setPatients] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [checkInDialogOpen, setCheckInDialogOpen] = useState(false);
  const [newlyCreatedPatient, setNewlyCreatedPatient] = useState(null);
  const [isCheckingIn, setIsCheckingIn] = useState(false);
  const { toast } = useToast();

  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    dob: '',
    id_number: '',
    contact_number: '',
    email: '',
    address: '',
    medical_aid: ''
  });

  const [checkInData, setCheckInData] = useState({
    reason_for_visit: '',
    priority: 'normal'
  });

  useEffect(() => {
    loadPatients();
  }, []);

  const loadPatients = async (search = '') => {
    try {
      setLoading(true);
      const response = await patientAPI.list(search);
      setPatients(response.data);
    } catch (error) {
      console.error('Error loading patients:', error);
      toast({
        title: 'Error',
        description: 'Failed to load patients',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e) => {
    const value = e.target.value;
    setSearchTerm(value);
    loadPatients(value);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await patientAPI.create(formData);
      toast({
        title: 'Success',
        description: 'Patient registered successfully'
      });
      setDialogOpen(false);
      setFormData({
        first_name: '',
        last_name: '',
        dob: '',
        id_number: '',
        contact_number: '',
        email: '',
        address: '',
        medical_aid: ''
      });
      loadPatients();
    } catch (error) {
      console.error('Error creating patient:', error);
      toast({
        title: 'Error',
        description: 'Failed to register patient',
        variant: 'destructive'
      });
    }
  };

  const handleInputChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  return (
    <div className="space-y-6 animate-fade-in" data-testid="patient-registry-container">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold text-slate-800 mb-2">Patient Registry</h1>
          <p className="text-slate-600">Manage all patient records</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button 
              className="bg-gradient-to-r from-teal-500 to-cyan-600 hover:from-teal-600 hover:to-cyan-700 text-white shadow-md hover:shadow-lg transition-all duration-200"
              data-testid="register-new-patient-btn"
            >
              <UserPlus className="w-4 h-4 mr-2" />
              Register New Patient
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="text-2xl font-bold text-slate-800">Register New Patient</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="first_name">First Name *</Label>
                  <Input
                    id="first_name"
                    name="first_name"
                    value={formData.first_name}
                    onChange={handleInputChange}
                    required
                    data-testid="input-first-name"
                  />
                </div>
                <div>
                  <Label htmlFor="last_name">Last Name *</Label>
                  <Input
                    id="last_name"
                    name="last_name"
                    value={formData.last_name}
                    onChange={handleInputChange}
                    required
                    data-testid="input-last-name"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="dob">Date of Birth *</Label>
                  <Input
                    id="dob"
                    name="dob"
                    type="date"
                    value={formData.dob}
                    onChange={handleInputChange}
                    required
                    data-testid="input-dob"
                  />
                </div>
                <div>
                  <Label htmlFor="id_number">ID Number *</Label>
                  <Input
                    id="id_number"
                    name="id_number"
                    value={formData.id_number}
                    onChange={handleInputChange}
                    required
                    data-testid="input-id-number"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="contact_number">Contact Number</Label>
                  <Input
                    id="contact_number"
                    name="contact_number"
                    value={formData.contact_number}
                    onChange={handleInputChange}
                    data-testid="input-contact-number"
                  />
                </div>
                <div>
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    value={formData.email}
                    onChange={handleInputChange}
                    data-testid="input-email"
                  />
                </div>
              </div>
              <div>
                <Label htmlFor="address">Address</Label>
                <Input
                  id="address"
                  name="address"
                  value={formData.address}
                  onChange={handleInputChange}
                  data-testid="input-address"
                />
              </div>
              <div>
                <Label htmlFor="medical_aid">Medical Aid</Label>
                <Input
                  id="medical_aid"
                  name="medical_aid"
                  value={formData.medical_aid}
                  onChange={handleInputChange}
                  data-testid="input-medical-aid"
                />
              </div>
              <div className="flex justify-end gap-2 pt-4">
                <Button 
                  type="button" 
                  variant="outline" 
                  onClick={() => setDialogOpen(false)}
                  data-testid="cancel-btn"
                >
                  Cancel
                </Button>
                <Button 
                  type="submit"
                  className="bg-gradient-to-r from-teal-500 to-cyan-600 hover:from-teal-600 hover:to-cyan-700 text-white"
                  data-testid="submit-patient-btn"
                >
                  Register Patient
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Search */}
      <Card className="border-0 shadow-lg">
        <CardContent className="pt-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400 w-5 h-5" />
            <Input
              type="text"
              placeholder="Search by name, ID number..."
              value={searchTerm}
              onChange={handleSearch}
              className="pl-10 h-12 text-base"
              data-testid="search-patients-input"
            />
          </div>
        </CardContent>
      </Card>

      {/* Patient List */}
      <Card className="border-0 shadow-lg">
        <CardHeader>
          <CardTitle className="text-xl font-bold text-slate-800">
            Registered Patients ({patients.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="w-12 h-12 border-4 border-teal-500 border-t-transparent rounded-full animate-spin"></div>
            </div>
          ) : patients.length === 0 ? (
            <div className="text-center py-12">
              <User className="w-16 h-16 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-500 text-lg">No patients found</p>
              <p className="text-slate-400 text-sm">Register your first patient to get started</p>
            </div>
          ) : (
            <div className="space-y-3">
              {patients.map((patient) => (
                <div
                  key={patient.id}
                  className="p-5 bg-gradient-to-r from-slate-50 to-blue-50 rounded-lg hover:shadow-md transition-all duration-200 border border-slate-200"
                  data-testid={`patient-card-${patient.id}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4 flex-1">
                      <div className="w-14 h-14 rounded-full bg-gradient-to-br from-teal-400 to-cyan-500 flex items-center justify-center text-white font-bold text-xl shadow-md">
                        {patient.first_name[0]}{patient.last_name[0]}
                      </div>
                      <div className="flex-1">
                        <h3 className="text-lg font-semibold text-slate-800">
                          {patient.first_name} {patient.last_name}
                        </h3>
                        <div className="flex items-center gap-4 text-sm text-slate-600 mt-1">
                          <span className="flex items-center gap-1">
                            <User className="w-4 h-4" />
                            {patient.id_number}
                          </span>
                          <span className="flex items-center gap-1">
                            <Calendar className="w-4 h-4" />
                            {patient.dob}
                          </span>
                          {patient.contact_number && (
                            <span className="flex items-center gap-1">
                              <Phone className="w-4 h-4" />
                              {patient.contact_number}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {patient.medical_aid && (
                        <span className="inline-block px-3 py-1 bg-violet-100 text-violet-700 text-xs font-medium rounded-full">
                          {patient.medical_aid}
                        </span>
                      )}
                      <Link to={`/patients/${patient.id}`}>
                        <Button 
                          className="bg-gradient-to-r from-teal-500 to-cyan-600 hover:from-teal-600 hover:to-cyan-700 text-white shadow-md hover:shadow-lg transition-all duration-200"
                          data-testid={`view-ehr-btn-${patient.id}`}
                        >
                          <FileText className="w-4 h-4 mr-2" />
                          View EHR
                        </Button>
                      </Link>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default PatientRegistry;