'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import Header from '@/components/Header';

export default function BookingPage() {
  const { user, token, isLoading: authLoading } = useAuth();
  const router = useRouter();

  const [doctors, setDoctors] = useState<any[]>([]);
  const [selectedDoctorId, setSelectedDoctorId] = useState<number | null>(null);
  const [doctorsLoading, setDoctorsLoading] = useState(true);
  const [doctorsError, setDoctorsError] = useState<string | null>(null);


  const [selectedDate, setSelectedDate] = useState<string>(''); // YYYY-MM-DD
  const [minDate, setMinDate] = useState<string>(''); // Today's date
  const [maxDate, setMaxDate] = useState<string>(''); // One month from today

  type AvailableSlot = {
    time: string;
    start_datetime: string;
    end_datetime: string;
    duration_minutes: number;
  };
  const [timeSlots, setTimeSlots] = useState<AvailableSlot[]>([]);
  const [selectedSlot, setSelectedSlot] = useState<AvailableSlot | null>(null);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [slotsError, setSlotsError] = useState<string | null>(null);

  // Step 4: Booking status
  const [bookingLoading, setBookingLoading] = useState(false);
  const [bookingError, setBookingError] = useState<string | null>(null);
  const [bookingSuccess, setBookingSuccess] = useState(false);


  useEffect(() => {
    if (authLoading) return;
    if (!user || user.role !== 'patient') {
      router.push('/');
    }
  }, [authLoading, user, router]);

  useEffect(() => {
    const fetchDoctors = async () => {
      setDoctorsLoading(true);
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/doctors`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (!response.ok) {
          throw new Error('Failed to fetch doctors');
        }

        const data = await response.json();
        setDoctors(data);
      } catch (err: any) {
        setDoctorsError(err.message || 'An unexpected error occurred');
      } finally {
        setDoctorsLoading(false);
      }
    };

    fetchDoctors();
  }, [user, token]);

  useEffect(() => {
    const today = new Date();
    const oneMonthLater = new Date();
    oneMonthLater.setMonth(oneMonthLater.getMonth() + 1);

    setMinDate(today.toISOString().split('T')[0]);
    setMaxDate(oneMonthLater.toISOString().split('T')[0]);

    setSelectedDate(today.toISOString().split('T')[0]);
  }, []);

  useEffect(() => {
    if (!selectedDoctorId || !selectedDate) {
      setTimeSlots([]);
      return;
    }

    const fetchTimeSlots = async () => {
      setSlotsLoading(true);
      setSlotsError(null);
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/doctor-availability-slots?doctor_id=${selectedDoctorId}&date=${selectedDate}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (!response.ok) {
          throw new Error('Failed to fetch time slots');
        }

        const data: AvailableSlot[] = await response.json();
        setTimeSlots(data);
      } catch (err: any) {
        setSlotsError(err.message || 'An unexpected error occurred');
      } finally {
        setSlotsLoading(false);
      }
    };

    fetchTimeSlots();
  }, [selectedDoctorId, selectedDate, user, token]);

  const handleBook = async () => {
    if (!selectedDoctorId || !selectedDate || !selectedSlot) {
      setBookingError('Please select a doctor, date, and time slot.');
      return;
    }


    const startDatetimeIso = selectedSlot.start_datetime;
    const endDatetimeIso = selectedSlot.end_datetime;

    setBookingLoading(true);
    setBookingError(null);
    setBookingSuccess(false);

    try {
      // First, get the selected doctor's specialization_id
      const selectedDoctor = doctors.find((d: any) => d.id === selectedDoctorId);
      if (!selectedDoctor) {
        throw new Error('Selected doctor not found');
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/appointments`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            doctor_id: selectedDoctorId,
            specialization_id: selectedDoctor.specialization_id,
            start_datetime: startDatetimeIso,
            end_datetime: endDatetimeIso,
            appointment_type: 'consultation',
            booking_source: 'normal',
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to book appointment');
      }

      setBookingSuccess(true);
      // Reset the form after a short delay
      setTimeout(() => {
        router.push('/patient');
      }, 1500);
    } catch (err: any) {
      setBookingError(err.message || 'An unexpected error occurred');
    } finally {
      setBookingLoading(false);
    }
  };

  if (authLoading) {
    return (
      <>
        <Header />
        <main className="min-h-screen bg-gray-50 py-12">
          <p className="text-center py-12">Loading...</p>
        </main>
      </>
    );
  }

  if (!user || user.role !== 'patient') {
    return null;
  }

  if (doctorsLoading) {
    return (
      <>
        <Header />
        <main className="min-h-screen bg-gray-50 py-12">
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
          </div>
        </main>
      </>
    );
  }

  if (doctorsError) {
    return (
      <>
        <Header />
        <main className="min-h-screen bg-gray-50 py-12">
          <div className="max-w-xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="bg-white rounded-lg shadow-md p-8">
              <h1 className="mb-4 text-2xl font-bold">Error</h1>
              <p className="text-red-600">{doctorsError}</p>
              <a href="/" className="mt-4 inline-block text-indigo-600 hover:text-indigo-900">
                Go back to home
              </a>
            </div>
          </div>
        </main>
      </>
    );
  }

  return (
    <>
      <Header />
      <main className="min-h-screen bg-gray-50 py-12">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-white rounded-lg shadow-md p-6">
            <h1 className="mb-4 text-2xl font-bold">Book an Appointment</h1>

            {/* Step 1: Select Doctor */}
            <div className="mb-6">
              <h2 className="text-xl font-semibold mb-2">Step 1: Select a Doctor</h2>
              <select
                value={selectedDoctorId || ''}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
                  setSelectedDoctorId(e.target.value ? Number(e.target.value) : null);
                  setSelectedSlot(null); // Reset time slot when doctor changes
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
                disabled={doctorsLoading}
              >
                <option value="">Select a doctor</option>
                {doctors.map((doctor: any) => (
                  <option key={doctor.id} value={doctor.id}>
                    Dr. {doctor.name} - {doctor.specialization?.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Step 2: Select Date */}
            <div className="mb-6">
              <h2 className="text-xl font-semibold mb-2">Step 2: Select a Date</h2>
              <input
                type="date"
                value={selectedDate}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                  setSelectedDate(e.target.value);
                  setSelectedSlot(null); // Reset time slot when date changes
                }}
                min={minDate}
                max={maxDate}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* Step 3: Select Time Slot */}
            <div className="mb-6">
              <h2 className="text-xl font-semibold mb-2">Step 3: Select a Time Slot</h2>
              {slotsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
                </div>
              ) : slotsError ? (
                <p className="text-red-600">{slotsError}</p>
              ) : timeSlots.length === 0 ? (
                <p className="text-gray-500">
                  No available time slots for the selected doctor on this date.
                  Please try another date.
                </p>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {timeSlots.map((slot: AvailableSlot) => (
                    <button
                      key={slot.start_datetime}
                      onClick={() => setSelectedSlot(slot)}
                      className={`w-full px-3 py-2 border border-gray-300 rounded-md ${
                        selectedSlot?.start_datetime === slot.start_datetime
                          ? 'bg-indigo-600 text-white'
                          : 'hover:bg-gray-50'
                      }`}
                    >
                      {slot.time}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Step 4: Confirm and Book */}
            <div className="mb-6">
              <h2 className="text-xl font-semibold mb-2">Step 4: Confirm and Book</h2>
              {selectedDoctorId && selectedDate && selectedSlot ? (
                <div className="bg-gray-50 p-4 rounded-md">
                  <p className="mb-2">
                    <strong>Doctor:</strong>
                    {doctors.find((d: any) => d.id === selectedDoctorId)?.name ||
                      'Unknown'}
                  </p>
                  <p className="mb-2">
                    <strong>Date:</strong> {new Date(selectedDate).toLocaleDateString()}
                  </p>
                  <p className="mb-2">
                    <strong>Time:</strong> {selectedSlot.time}
                  </p>
                  <p className="mb-2">
                    <strong>Duration:</strong> {selectedSlot.duration_minutes} minutes
                  </p>
                </div>
              ) : (
                <p className="text-gray-500">
                  Please complete the previous steps to see the booking summary.
                </p>
              )}
            </div>

            {/* Booking status */}
            {bookingLoading ? (
              <div className="flex items-center justify-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
              </div>
            ) : bookingError ? (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-600 rounded-md">
                {bookingError}
              </div>
            ) : bookingSuccess ? (
              <div className="mb-4 p-3 bg-green-50 border border-green-200 text-green-600 rounded-md">
                <p className="font-medium">Appointment booked successfully!</p>
                <p className="mt-2">
                  You will be redirected to your dashboard shortly.
                </p>
              </div>
            ) : null}

            {/* Book Button */}
            <div className="mt-6">
              <button
                onClick={handleBook}
                disabled={bookingLoading || !selectedDoctorId || !selectedDate || !selectedSlot}
                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-3 px-4 rounded-md disabled:opacity-50"
              >
                {bookingLoading ? 'Booking...' : 'Book Appointment'}
              </button>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}