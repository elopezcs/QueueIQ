import React from "react";

export default function ClinicSelector({ clinics, clinicId, setClinicId, disabled }) {
  return (
    <div className="field">
      <label>Select a Clinic</label>
      <select
        value={clinicId}
        disabled={disabled}
        onChange={(e) => setClinicId(e.target.value)}
      >
        {clinics.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name} ({c.address_or_city})
          </option>
        ))}
      </select>
      <div className="kpiDescription" style={{ textAlign: 'left', marginTop: '8px', marginBottom: '16px' }}>
        Please select the clinic you plan to visit, then click "Start intake" to begin your pre-arrival assessment.
      </div>
    </div>
  );
}
