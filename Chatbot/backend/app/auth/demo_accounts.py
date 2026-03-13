DEMO_USERS = [
    {
        "patient_id": "demo-patient-alice",
        "full_name": "Alice Johnson",
        "email": "alice.patient@queueiq.local",
        "is_admin": False,
        "otp_code": "111111",
    },
    {
        "patient_id": "demo-patient-bob",
        "full_name": "Bob Smith",
        "email": "bob.patient@queueiq.local",
        "is_admin": False,
        "otp_code": "222222",
    },
    {
        "patient_id": "demo-patient-carol",
        "full_name": "Carol Davis",
        "email": "carol.patient@queueiq.local",
        "is_admin": False,
        "otp_code": "333333",
    },
    {
        "patient_id": "demo-admin-dana",
        "full_name": "Dana Admin",
        "email": "admin@queueiq.local",
        "is_admin": True,
        "otp_code": "999999",
    },
]


DEMO_USER_BY_EMAIL = {user["email"]: user for user in DEMO_USERS}
