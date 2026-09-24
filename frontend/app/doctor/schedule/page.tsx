'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import Header from '@/components/Header';

const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

interface Availability {
  id: number;
  day_of_week: number;
  start_time: string;
  end_time: string;
  slot_duration: number;
}

interface Leave {
  id: number;
  start_datetime: string;
  end_datetime: string;
  reason: string | null;
}

export default function DoctorSchedulePage() {
  const { user, token, isLoading: authLoading } = useAuth();
  const router = useRouter();

  const [doctorId, setDoctorId] = useState<number | null>(null);
  const [availability, setAvailability] = useState<Availability[]>([]);
  const [leaves, setLeaves] = useState<Leave[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newDay, setNewDay] = useState(0);
  const [newStart, setNewStart] = useState('09:00');
  const [newEnd, setNewEnd] = useState('17:00');
  const [newSlotDuration, setNewSlotDuration] = useState(30);

  const [leaveStart, setLeaveStart] = useState('');
  const [leaveEnd, setLeaveEnd] = useState('');
  const [leaveReason, setLeaveReason] = useState('');
  const [leaveConflictWarning, setLeaveConflictWarning] = useState<string | null>(null);

  const authHeaders = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };

  useEffect(() => {
    if (authLoading) return;
    if (!user || user.role !== 'doctor') {
      router.push('/');
      return;
    }

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const meRes = await fetch(`${apiUrl}/api/doctors/me`, { headers: authHeaders });
        if (!meRes.ok) throw new Error('Failed to load your doctor profile');
        const me = await meRes.json();
        setDoctorId(me.id);

        const [availRes, leaveRes] = await Promise.all([
          fetch(`${apiUrl}/api/doctor-availability/${me.id}`, { headers: authHeaders }),
          fetch(`${apiUrl}/api/doctor-leave/${me.id}`, { headers: authHeaders }),
        ]);
        if (!availRes.ok || !leaveRes.ok) throw new Error('Failed to load your schedule');
        setAvailability(await availRes.json());
        setLeaves(await leaveRes.json());
      } catch (err: any) {
        setError(err.message || 'An unexpected error occurred');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [authLoading, user, token, router]);

  const refreshAvailability = async () => {
    if (!doctorId) return;
    const res = await fetch(`${apiUrl}/api/doctor-availability/${doctorId}`, { headers: authHeaders });
    if (res.ok) setAvailability(await res.json());
  };

  const refreshLeaves = async () => {
    if (!doctorId) return;
    const res = await fetch(`${apiUrl}/api/doctor-leave/${doctorId}`, { headers: authHeaders });
    if (res.ok) setLeaves(await res.json());
  };

  const handleAddAvailability = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const res = await fetch(`${apiUrl}/api/doctor-availability`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({
          day_of_week: newDay,
          start_time: `${newStart}:00`,
          end_time: `${newEnd}:00`,
          slot_duration: newSlotDuration,
        }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to add availability');
      }
      await refreshAvailability();
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred');
    }
  };

  const handleRemoveAvailability = async (id: number) => {
    setError(null);
    try {
      const res = await fetch(`${apiUrl}/api/doctor-availability/${id}`, {
        method: 'DELETE',
        headers: authHeaders,
      });
      if (!res.ok && res.status !== 204) throw new Error('Failed to remove availability');
      setAvailability((prev: any) => prev.filter((a: any) => a.id !== id));
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred');
    }
  };

  const handleAddLeave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!leaveStart || !leaveEnd) {
      setError('Please fill in both leave start and end.');
      return;
    }
    try {
      const res = await fetch(`${apiUrl}/api/doctor-leave`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({
          start_datetime: new Date(leaveStart).toISOString(),
          end_datetime: new Date(leaveEnd).toISOString(),
          reason: leaveReason || null,
        }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to add leave period');
      }
      const created = await res.json();
      setLeaveStart('');
      setLeaveEnd('');
      setLeaveReason('');
      await refreshLeaves();
      if (created.conflicting_appointment_ids && created.conflicting_appointment_ids.length > 0) {
        setLeaveConflictWarning(
          `Heads up: ${created.conflicting_appointment_ids.length} already-scheduled appointment(s) fall inside this leave period. You'll need to reschedule or cancel them separately.`
        );
      } else {
        setLeaveConflictWarning(null);
      }
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred');
    }
  };

  const handleRemoveLeave = async (id: number) => {
    setError(null);
    try {
      const res = await fetch(`${apiUrl}/api/doctor-leave/${id}`, {
        method: 'DELETE',
        headers: authHeaders,
      });
      if (!res.ok && res.status !== 204) throw new Error('Failed to remove leave period');
      setLeaves((prev: any) => prev.filter((l: any) => l.id !== id));
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred');
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

  if (!user || user.role !== 'doctor') {
    return null;
  }

  return (
    <>
      <Header />
      <main className="min-h-screen bg-gray-50 py-12">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h1 className="text-2xl font-bold mb-6">Manage Your Schedule</h1>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-600 rounded-md">{error}</div>
          )}

          {loading ? (
            <p className="text-center py-8">Loading your schedule...</p>
          ) : (
            <>
              {/* Weekly availability */}
              <section className="bg-white rounded-lg shadow-md p-6 mb-8">
                <h2 className="text-xl font-semibold mb-4">Weekly Availability</h2>

                {availability.length === 0 ? (
                  <p className="text-gray-500 mb-4">No availability windows set yet.</p>
                ) : (
                  <ul className="mb-6 divide-y divide-gray-200">
                    {availability.map((a: any) => (
                      <li key={a.id} className="py-3 flex justify-between items-center">
                        <span>
                          <strong>{DAY_NAMES[a.day_of_week]}</strong>: {a.start_time.slice(0, 5)}–{a.end_time.slice(0, 5)}{' '}
                          <span className="text-gray-500 text-sm">({a.slot_duration} min slots)</span>
                        </span>
                        <button
                          onClick={() => handleRemoveAvailability(a.id)}
                          className="text-red-600 hover:text-red-800 text-sm font-medium"
                        >
                          Remove
                        </button>
                      </li>
                    ))}
                  </ul>
                )}

                <form onSubmit={handleAddAvailability} className="grid grid-cols-2 sm:grid-cols-5 gap-3 items-end">
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">Day</label>
                    <select
                      value={newDay}
                      onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setNewDay(Number(e.target.value))}
                      className="w-full px-2 py-2 border border-gray-300 rounded-md"
                    >
                      {DAY_NAMES.map((d, i) => (
                        <option key={d} value={i}>{d}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">Start</label>
                    <input
                      type="time"
                      value={newStart}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewStart(e.target.value)}
                      className="w-full px-2 py-2 border border-gray-300 rounded-md"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">End</label>
                    <input
                      type="time"
                      value={newEnd}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewEnd(e.target.value)}
                      className="w-full px-2 py-2 border border-gray-300 rounded-md"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">Slot (min)</label>
                    <input
                      type="number"
                      min={5}
                      max={120}
                      value={newSlotDuration}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewSlotDuration(Number(e.target.value))}
                      className="w-full px-2 py-2 border border-gray-300 rounded-md"
                    />
                  </div>
                  <button
                    type="submit"
                    className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-4 rounded-md"
                  >
                    Add
                  </button>
                </form>
              </section>

              {/* Leave periods */}
              <section className="bg-white rounded-lg shadow-md p-6">
                <h2 className="text-xl font-semibold mb-4">Leave Periods</h2>

                {leaveConflictWarning && (
                  <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 text-yellow-800 rounded-md text-sm">
                    {leaveConflictWarning}
                  </div>
                )}

                {leaves.length === 0 ? (
                  <p className="text-gray-500 mb-4">No upcoming leave scheduled.</p>
                ) : (
                  <ul className="mb-6 divide-y divide-gray-200">
                    {leaves.map((l: any) => (
                      <li key={l.id} className="py-3 flex justify-between items-center">
                        <span>
                          {new Date(l.start_datetime).toLocaleString()} – {new Date(l.end_datetime).toLocaleString()}
                          {l.reason && <span className="text-gray-500 text-sm"> ({l.reason})</span>}
                        </span>
                        <button
                          onClick={() => handleRemoveLeave(l.id)}
                          className="text-red-600 hover:text-red-800 text-sm font-medium"
                        >
                          Remove
                        </button>
                      </li>
                    ))}
                  </ul>
                )}

                <form onSubmit={handleAddLeave} className="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end">
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">From</label>
                    <input
                      type="datetime-local"
                      value={leaveStart}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setLeaveStart(e.target.value)}
                      className="w-full px-2 py-2 border border-gray-300 rounded-md"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">To</label>
                    <input
                      type="datetime-local"
                      value={leaveEnd}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setLeaveEnd(e.target.value)}
                      className="w-full px-2 py-2 border border-gray-300 rounded-md"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">Reason (optional)</label>
                    <input
                      type="text"
                      value={leaveReason}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setLeaveReason(e.target.value)}
                      className="w-full px-2 py-2 border border-gray-300 rounded-md"
                    />
                  </div>
                  <button
                    type="submit"
                    className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-4 rounded-md"
                  >
                    Add Leave
                  </button>
                </form>
              </section>
            </>
          )}
        </div>
      </main>
    </>
  );
}
