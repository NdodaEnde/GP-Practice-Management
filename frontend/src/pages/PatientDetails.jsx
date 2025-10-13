import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, User, Calendar, Phone, Mail, MapPin, Heart, FileText, Plus } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { patientAPI, encounterAPI } from '@/services/api';
import { useToast } from '@/hooks/use-toast';

const PatientDetails = () => {
  const { patientId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [patient, setPatient] = useState(null);
  const [encounters, setEncounters] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPatientData();
  }, [patientId]);

  const loadPatientData = async () => {
    try {
      setLoading(true);
      const [patientRes, encountersRes] = await Promise.all([
        patientAPI.get(patientId),
        encounterAPI.listByPatient(patientId)
      ]);
      setPatient(patientRes.data);
      setEncounters(encountersRes.data);
    } catch (error) {
      console.error('Error loading patient:', error);
      toast({
        title: 'Error',
        description: 'Failed to load patient data',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="w-16 h-16 border-4 border-teal-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500 text-lg">Patient not found</p>
        <Link to="/patients">
          <Button className="mt-4">Back to Patients</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="patient-details-container">
      {/* Header */}
      <div>
        <Link to="/patients" className="inline-flex items-center text-teal-600 hover:text-teal-700 mb-4">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Patients
        </Link>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-20 h-20 rounded-full bg-gradient-to-br from-teal-400 to-cyan-500 flex items-center justify-center text-white font-bold text-3xl shadow-lg">
              {patient.first_name[0]}{patient.last_name[0]}
            </div>
            <div>
              <h1 className="text-4xl font-bold text-slate-800">
                {patient.first_name} {patient.last_name}
              </h1>
              <p className="text-slate-600">Patient ID: {patient.id_number}</p>
            </div>
          </div>
          <Link to={`/encounters/new/${patientId}`}>
            <Button 
              className="bg-gradient-to-r from-teal-500 to-cyan-600 hover:from-teal-600 hover:to-cyan-700 text-white shadow-md hover:shadow-lg transition-all duration-200"
              data-testid="new-encounter-btn"
            >
              <Plus className="w-4 h-4 mr-2" />
              New Encounter
            </Button>
          </Link>
        </div>
      </div>

      {/* Patient Information */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-0 shadow-lg">
          <CardHeader>
            <CardTitle className="text-xl font-bold text-slate-800 flex items-center gap-2">
              <User className="w-5 h-5" />
              Personal Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-start gap-3">
              <Calendar className="w-5 h-5 text-slate-400 mt-1" />
              <div>
                <p className="text-sm text-slate-500">Date of Birth</p>
                <p className="text-base font-semibold text-slate-800">{patient.dob}</p>
              </div>
            </div>
            {patient.contact_number && (
              <div className="flex items-start gap-3">
                <Phone className="w-5 h-5 text-slate-400 mt-1" />
                <div>
                  <p className="text-sm text-slate-500">Contact Number</p>
                  <p className="text-base font-semibold text-slate-800">{patient.contact_number}</p>
                </div>
              </div>
            )}
            {patient.email && (
              <div className="flex items-start gap-3">
                <Mail className="w-5 h-5 text-slate-400 mt-1" />
                <div>
                  <p className="text-sm text-slate-500">Email</p>
                  <p className="text-base font-semibold text-slate-800">{patient.email}</p>
                </div>
              </div>
            )}
            {patient.address && (
              <div className="flex items-start gap-3">
                <MapPin className="w-5 h-5 text-slate-400 mt-1" />
                <div>
                  <p className="text-sm text-slate-500">Address</p>
                  <p className="text-base font-semibold text-slate-800">{patient.address}</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border-0 shadow-lg">
          <CardHeader>
            <CardTitle className="text-xl font-bold text-slate-800 flex items-center gap-2">
              <Heart className="w-5 h-5" />
              Medical Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {patient.medical_aid ? (
              <div>
                <p className="text-sm text-slate-500">Medical Aid</p>
                <p className="text-base font-semibold text-slate-800">{patient.medical_aid}</p>
              </div>
            ) : (
              <p className="text-slate-400">No medical aid information</p>
            )}
            <div>
              <p className="text-sm text-slate-500">Total Encounters</p>
              <p className="text-2xl font-bold text-teal-600">{encounters.length}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Encounter History */}
      <Card className="border-0 shadow-lg">
        <CardHeader>
          <CardTitle className="text-xl font-bold text-slate-800 flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Encounter History
          </CardTitle>
        </CardHeader>
        <CardContent>
          {encounters.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="w-16 h-16 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-500 text-lg">No encounters yet</p>
              <Link to={`/encounters/new/${patientId}`}>
                <Button className="mt-4 bg-gradient-to-r from-teal-500 to-cyan-600 text-white">
                  Create First Encounter
                </Button>
              </Link>
            </div>
          ) : (
            <div className="space-y-3">
              {encounters.map((encounter) => (
                <div
                  key={encounter.id}
                  className="p-5 bg-gradient-to-r from-slate-50 to-blue-50 rounded-lg border border-slate-200 hover:shadow-md transition-all duration-200"
                  data-testid={`encounter-card-${encounter.id}`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-semibold text-slate-800">
                        {encounter.chief_complaint || 'General Consultation'}
                      </h3>
                      <p className="text-sm text-slate-600 mt-1">
                        {new Date(encounter.encounter_date).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </p>
                      {encounter.gp_notes && (
                        <p className="text-sm text-slate-600 mt-2 line-clamp-2">{encounter.gp_notes}</p>
                      )}
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <span className={`inline-block px-3 py-1 text-xs font-medium rounded-full ${
                        encounter.status === 'completed'
                          ? 'bg-emerald-100 text-emerald-700'
                          : 'bg-amber-100 text-amber-700'
                      }`}>
                        {encounter.status}
                      </span>
                      <Link to={`/validation/${encounter.id}`}>
                        <Button 
                          size="sm" 
                          variant="outline"
                          data-testid={`view-encounter-${encounter.id}`}
                        >
                          View Details
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

export default PatientDetails;