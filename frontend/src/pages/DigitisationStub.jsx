import React from 'react';
import { Construction } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

// Phase A placeholder for Type C sub-pages (Documents Pipeline, Validation
// Queue, Archive, Export Centre, Operational Insights). The real screens come
// from porting groundtruth-clean-gp's digitisation module in Phase B and
// restyling against the agreed Type C mockups.
const DigitisationStub = ({ title, description }) => (
  <div className="max-w-[1200px] mx-auto">
    <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 mb-2">{title}</h1>
    <p className="text-slate-600 mb-6">{description}</p>
    <Card className="border-slate-200">
      <CardContent className="p-12 text-center">
        <Construction className="w-12 h-12 mx-auto text-blue-900 mb-4" />
        <h2 className="text-xl font-bold text-slate-900 mb-2">Coming in Phase B</h2>
        <p className="text-slate-600 max-w-md mx-auto">
          This screen ports from groundtruth-clean-gp's digitisation pipeline
          and is restyled against the new Type C mockups.
        </p>
      </CardContent>
    </Card>
  </div>
);

export default DigitisationStub;
