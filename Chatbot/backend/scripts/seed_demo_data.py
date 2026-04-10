import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parents[1]
repo_root = backend_root.parents[1]

for path in (repo_root, backend_root):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from app.storage.db import get_conn, init_db
from app.storage.repo import seed_demo_data


def _count_demo_appointments() -> int:
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM appointments
            WHERE patient_id LIKE ?
            """,
        ('demo-%',),
        ).fetchone()
        return int(row['total']) if row else 0
    finally:
        conn.close()


def _count_demo_users() -> int:
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM patients
            WHERE patient_id LIKE ?
            """,
        ('demo-%',),
        ).fetchone()
        return int(row['total']) if row else 0
    finally:
        conn.close()


def _confirm_continue(existing_demo_users: int) -> bool:
    if existing_demo_users <= 0:
        return True

    print(
        f"Warning: {existing_demo_users} demo users already exist. "
        "This seed is add-only and will skip duplicates."
    )
    answer = input("Continue and add only missing demo rows? (yes/no): ").strip().lower()
    return answer in {'yes', 'y'}


def main() -> None:
    init_db()

    existing_demo_users = _count_demo_users()
    if not _confirm_continue(existing_demo_users):
        print('Seeding cancelled by user.')
        return

    summary = seed_demo_data()
    demo_users = _count_demo_users()
    demo_appointments = _count_demo_appointments()
    print(
        'Seed complete. '
        f"inserted_users={summary.get('inserted_users', 0)} "
        f"skipped_duplicates={summary.get('skipped_duplicates', 0)} "
        f"patient_rows_seeded={summary.get('patient_rows_seeded', 0)} "
        f"demo_users={demo_users} demo_appointments={demo_appointments}"
    )


if __name__ == '__main__':
    main()

