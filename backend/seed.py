"""
Seed the database with realistic synthetic data for local development.

Usage:
    python seed.py            # seed (skips if data already exists)
    python seed.py --reset    # wipe all rows first, then reseed

Creates:
    - 8 specializations
    - 20 doctors, all with realistic Indian names (each with a user account + weekly availability)
    - 50 patients, all with realistic Indian names (each with a user account)
    - ~300 historical appointments (mix of completed / cancelled / no_show)
    - a handful of upcoming scheduled appointments
    - 3 demo accounts: admin@example.com / doctor@example.com / patient@example.com

All demo passwords are DEV-ONLY and must be changed before any production use.
"""
import datetime as dt
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from faker import Faker
from passlib.context import CryptContext
from sqlalchemy import text

from app.core.database import SessionLocal, engine
from app.models import (
    Appointment,
    Base,
    Doctor,
    DoctorAvailability,
    DoctorLeave,
    Notification,
    Patient,
    PredictionLog,
    Specialization,
    User,
    Waitlist,
)
from app.models.enums import (
    AppointmentStatus,
    AppointmentType,
    BookingSource,
    NotificationStatus,
    NotificationType,
    UserRole,
)

fake = Faker("en_IN")
Faker.seed(42)
random.seed(42)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SPECIALIZATIONS = [
    ("Cardiology", "Heart and cardiovascular system"),
    ("Dermatology", "Skin, hair, and nail conditions"),
    ("Orthopedics", "Bones, joints, and musculoskeletal system"),
    ("Neurology", "Brain and nervous system"),
    ("General Medicine", "General health and primary care"),
    ("ENT", "Ear, nose, and throat"),
    ("Pediatrics", "Child health"),
    ("Ophthalmology", "Eye care"),
]

# A curated list of realistic Indian doctor names, used instead of relying
# solely on Faker's en_IN name generator, so every doctor in the seed data is
# guaranteed to have an authentic, well-formed Indian name (first + surname,
# spanning several regions/communities) rather than a randomly-assembled one.
INDIAN_DOCTOR_NAMES = [
    "Ananya Sharma", "Rohan Verma", "Priya Nair", "Arjun Reddy", "Kavita Iyer",
    "Vikram Singh", "Meera Krishnan", "Aditya Rao", "Sanjana Gupta", "Karan Malhotra",
    "Divya Menon", "Rahul Kapoor", "Neha Joshi", "Siddharth Chatterjee", "Pooja Desai",
    "Arvind Pillai", "Ritu Agarwal", "Manoj Pillai", "Shreya Bhatt", "Amitabh Mukherjee",
    "Lakshmi Subramaniam", "Nikhil Choudhary", "Anjali Rathore", "Suresh Iyengar",
    "Deepika Bose", "Varun Khanna", "Swati Trivedi", "Gaurav Sethi", "Radhika Nambiar",
    "Vivek Bhatia",
]

# Realistic Indian patient names for the same reason as above.
INDIAN_PATIENT_NAMES = [
    "Aarav Shah", "Ishita Chawla", "Rajesh Kulkarni", "Sneha Pandey", "Aditi Chauhan",
    "Kabir Bhandari", "Tanvi Saxena", "Yash Thakur", "Nandini Ganguly", "Harsh Vora",
    "Simran Kaur", "Rohit Bajaj", "Alia Sheikh", "Devansh Mehta", "Pallavi Kulkarni",
    "Aman Tripathi", "Riya Ahluwalia", "Naveen Kumar", "Sakshi Dubey", "Kunal Oberoi",
    "Bhavna Rastogi", "Tarun Gill", "Ishaan Bhat", "Namrata Sinha", "Om Prakash Yadav",
    "Chetna Ramesh", "Abhishek Pawar", "Juhi Chandra", "Rakesh Bhosale", "Anushka Dutta",
    "Manish Solanki", "Preeti Bansal", "Vishal Chopra", "Kritika Mishra", "Saurabh Nanda",
    "Ayesha Qureshi", "Tejas Warrier", "Nisha Kohli", "Gopal Krishnan", "Vandana Rawat",
    "Pranav Acharya", "Sunidhi Sarin", "Mohit Khurana", "Rupali Deshpande", "Faisal Ansari",
    "Geetika Anand", "Rajat Suri", "Meenal Karnik", "Zubin Contractor", "Shalini Reddy",
]

DEV_PASSWORD = "DevPassword123!"  


def hash_pw(pw: str) -> str:
    return pwd_context.hash(pw)


def reset_schema():
    print("Dropping and recreating all tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed():
    db = SessionLocal()
    try:
        if db.query(User).count() > 0 and "--reset" not in sys.argv:
            print("Database already has data. Run with --reset to wipe and reseed.")
            return

        # --- Specializations ---
        specializations = []
        for name, desc in SPECIALIZATIONS:
            spec = Specialization(name=name, description=desc)
            db.add(spec)
            specializations.append(spec)
        db.flush()
        print(f"Created {len(specializations)} specializations")

        admin_user = User(name="Harsh", email="admin@example.com", password_hash=hash_pw(DEV_PASSWORD), role=UserRole.admin)
        db.add(admin_user)

        demo_doctor_user = User(
            name="Dr. Ananya Sharma", email="doctor@example.com", password_hash=hash_pw(DEV_PASSWORD), role=UserRole.doctor
        )
        db.add(demo_doctor_user)
        db.flush()
        demo_doctor = Doctor(
            user_id=demo_doctor_user.id,
            specialization_id=specializations[1].id,  # Dermatology
            experience_years=8,
            consultation_fee=60.00,
            bio="Experienced dermatologist focused on general and cosmetic dermatology.",
            rating=4.7,
        )
        db.add(demo_doctor)

        demo_patient_user = User(
            name="Nikhil Deshmukh", email="patient@example.com", password_hash=hash_pw(DEV_PASSWORD), role=UserRole.patient
        )
        db.add(demo_patient_user)
        db.flush()
        demo_patient = Patient(
            user_id=demo_patient_user.id,
            date_of_birth=dt.date(1992, 4, 12),
            phone=fake.phone_number()[:20],
            preferences={"preferred_time_of_day": "evening"},
        )
        db.add(demo_patient)
        db.flush()
        print("Created demo accounts: admin@example.com / doctor@example.com / patient@example.com")

        # --- 20 doctors total (including the demo one above = 19 more) ---
        doctors = [demo_doctor]
        remaining_doctor_names = [n for n in INDIAN_DOCTOR_NAMES if n != "Ananya Sharma"]
        random.shuffle(remaining_doctor_names)
        for i in range(19):
            full_name = remaining_doctor_names[i % len(remaining_doctor_names)]
            name = f"Dr. {full_name}"
            email = fake.unique.email()
            user = User(name=name, email=email, password_hash=hash_pw(DEV_PASSWORD), role=UserRole.doctor)
            db.add(user)
            db.flush()
            doctor = Doctor(
                user_id=user.id,
                specialization_id=random.choice(specializations).id,
                experience_years=random.randint(1, 30),
                consultation_fee=round(random.uniform(25, 150), 2),
                bio=fake.paragraph(nb_sentences=3),
                rating=round(random.uniform(3.5, 5.0), 2),
            )
            db.add(doctor)
            doctors.append(doctor)
        db.flush()
        print(f"Created {len(doctors)} doctors")

        # --- Weekly availability for every doctor: Mon-Fri, with variation ---
        for doctor in doctors:
            for day in range(0, 5):  # Mon-Fri
                if random.random() < 0.1:
                    continue  # some doctors don't work every weekday
                start_hour = random.choice([8, 9])
                end_hour = random.choice([16, 17, 18])
                db.add(
                    DoctorAvailability(
                        doctor_id=doctor.id,
                        day_of_week=day,
                        start_time=dt.time(start_hour, 0),
                        end_time=dt.time(end_hour, 0),
                        slot_duration=random.choice([20, 30]),
                    )
                )
            # Occasional Saturday morning clinic
            if random.random() < 0.3:
                db.add(
                    DoctorAvailability(
                        doctor_id=doctor.id, day_of_week=5, start_time=dt.time(9, 0), end_time=dt.time(13, 0), slot_duration=30
                    )
                )
        db.flush()
        print("Created doctor weekly availability")

        # --- A few upcoming leave periods ---
        for doctor in random.sample(doctors, 5):
            leave_start = dt.datetime.now() + dt.timedelta(days=random.randint(3, 20))
            db.add(
                DoctorLeave(
                    doctor_id=doctor.id,
                    start_datetime=leave_start,
                    end_datetime=leave_start + dt.timedelta(days=random.randint(1, 3)),
                    reason=random.choice(["Conference", "Personal leave", "Training"]),
                )
            )
        db.flush()
        print("Created doctor leave periods")

        # --- 50 patients total (including demo patient = 49 more) ---
        patients = [demo_patient]
        remaining_patient_names = [n for n in INDIAN_PATIENT_NAMES if n != "Nikhil Deshmukh"]
        random.shuffle(remaining_patient_names)
        for i in range(49):
            name = remaining_patient_names[i % len(remaining_patient_names)]
            email = fake.unique.email()
            user = User(name=name, email=email, password_hash=hash_pw(DEV_PASSWORD), role=UserRole.patient)
            db.add(user)
            db.flush()
            patient = Patient(
                user_id=user.id,
                date_of_birth=fake.date_of_birth(minimum_age=1, maximum_age=90),
                phone=fake.phone_number()[:20],
                preferences={"preferred_time_of_day": random.choice(["morning", "afternoon", "evening", None])},
            )
            db.add(patient)
            patients.append(patient)
        db.flush()
        print(f"Created {len(patients)} patients")

        # --- ~300 historical appointments over the past 120 days ---
        appt_types = list(AppointmentType)
        created = 0
        attempts = 0
        used_slots = set()  # (doctor_id, start_datetime) to avoid unique-constraint clashes
        while created < 300 and attempts < 3000:
            attempts += 1
            doctor = random.choice(doctors)
            patient = random.choice(patients)
            days_ago = random.randint(1, 120)
            appt_date = dt.datetime.now() - dt.timedelta(days=days_ago)
            hour = random.randint(8, 17)
            minute = random.choice([0, 15, 30, 45])
            start = appt_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            key = (doctor.id, start)
            if key in used_slots:
                continue
            used_slots.add(key)

            duration = random.choice([15, 20, 30, 45])
            end = start + dt.timedelta(minutes=duration)

            roll = random.random()
            if roll < 0.75:
                status = AppointmentStatus.completed
            elif roll < 0.85:
                status = AppointmentStatus.cancelled
            elif roll < 0.95:
                status = AppointmentStatus.no_show
            else:
                status = AppointmentStatus.rescheduled

            appt = Appointment(
                patient_id=patient.id,
                doctor_id=doctor.id,
                specialization_id=doctor.specialization_id,
                start_datetime=start,
                end_datetime=end,
                appointment_type=random.choice(appt_types),
                status=status,
                booking_source=random.choice([BookingSource.normal, BookingSource.ai]),
                # Real (ground-truth) duration — this is what the duration ML
                # model actually trains against, distinct from predicted_duration below.
                duration_minutes=duration,
                predicted_duration=duration + random.choice([-5, 0, 0, 5]),
                predicted_no_show_probability=round(random.uniform(0.02, 0.35), 2),
                predicted_waiting_time=random.randint(0, 25),
                recommendation_score=round(random.uniform(60, 99), 1) if random.random() < 0.5 else None,
            )
            db.add(appt)
            created += 1
        db.flush()
        print(f"Created {created} historical appointments")

        # --- A handful of upcoming scheduled appointments (so dashboards aren't empty) ---
        upcoming_created = 0
        attempts = 0
        while upcoming_created < 15 and attempts < 500:
            attempts += 1
            doctor = random.choice(doctors)
            patient = random.choice(patients)
            days_ahead = random.randint(1, 14)
            start = (dt.datetime.now() + dt.timedelta(days=days_ahead)).replace(
                hour=random.randint(9, 16), minute=random.choice([0, 30]), second=0, microsecond=0
            )
            key = (doctor.id, start)
            if key in used_slots:
                continue
            used_slots.add(key)
            duration = 30
            appt = Appointment(
                patient_id=patient.id,
                doctor_id=doctor.id,
                specialization_id=doctor.specialization_id,
                start_datetime=start,
                end_datetime=start + dt.timedelta(minutes=duration),
                appointment_type=AppointmentType.consultation,
                status=AppointmentStatus.scheduled,
                booking_source=BookingSource.ai,
                duration_minutes=duration,
                predicted_duration=duration,
                predicted_no_show_probability=round(random.uniform(0.05, 0.2), 2),
                predicted_waiting_time=random.randint(0, 15),
                recommendation_score=round(random.uniform(80, 98), 1),
            )
            db.add(appt)
            upcoming_created += 1
        db.flush()
        print(f"Created {upcoming_created} upcoming scheduled appointments")

        # One upcoming appointment tied to the demo patient + demo doctor, guaranteed.
        guaranteed_start = (dt.datetime.now() + dt.timedelta(days=3)).replace(hour=17, minute=30, second=0, microsecond=0)
        if (demo_doctor.id, guaranteed_start) not in used_slots:
            db.add(
                Appointment(
                    patient_id=demo_patient.id,
                    doctor_id=demo_doctor.id,
                    specialization_id=demo_doctor.specialization_id,
                    start_datetime=guaranteed_start,
                    end_datetime=guaranteed_start + dt.timedelta(minutes=30),
                    appointment_type=AppointmentType.consultation,
                    status=AppointmentStatus.scheduled,
                    booking_source=BookingSource.ai,
                    duration_minutes=30,
                    predicted_duration=30,
                    predicted_no_show_probability=0.08,
                    predicted_waiting_time=7,
                    recommendation_score=94.0,
                )
            )

        db.commit()
        print("\nSeed complete.")
        print("Demo logins (password for all: 'DevPassword123!' — DEV ONLY, change before production):")
        print("  admin@example.com")
        print("  doctor@example.com")
        print("  patient@example.com")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if "--reset" in sys.argv:
        reset_schema()
    seed()
