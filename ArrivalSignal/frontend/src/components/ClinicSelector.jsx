import React from "react";

export default function ClinicSelector({ clinics, clinicId, setClinicId, disabled }) {
  return (
    <div className="field">
      <label>Clinic</label>
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
    </div>
  );
}
