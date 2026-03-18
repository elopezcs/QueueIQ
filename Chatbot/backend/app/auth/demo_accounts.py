DEMO_USERS = [
    {
        "patient_id": "demo-patient-alice",
        "full_name": "Alice Johnson",
        "email": "alice.patient@queueiq.local",
        "role": "patient",
        "clinic_id": None,
        "is_admin": False,
        "otp_code": "111111",
    },
    {
        "patient_id": "demo-patient-bob",
        "full_name": "Bob Smith",
        "email": "bob.patient@queueiq.local",
        "role": "patient",
        "clinic_id": None,
        "is_admin": False,
        "otp_code": "222222",
    },
    {
        "patient_id": "demo-staff-carol",
        "full_name": "Carol Staff",
        "email": "carol.staff@queueiq.local",
        "role": "staff",
        "clinic_id": "Downtown-Clinic",
        "is_admin": False,
        "otp_code": "333333",
    },
    {
        "patient_id": "demo-staff-ethan",
        "full_name": "Ethan Staff",
        "email": "ethan.staff@queueiq.local",
        "role": "staff",
        "clinic_id": "Westside-Clinic",
        "is_admin": False,
        "otp_code": "444444",
    },
    {
        "patient_id": "demo-manager-dana",
        "full_name": "Dana Manager",
        "email": "manager@queueiq.local",
        "role": "manager",
        "clinic_id": None,
        "is_admin": True,
        "otp_code": "999999",
    },
]


DEMO_USER_BY_EMAIL = {user["email"]: user for user in DEMO_USERS}
