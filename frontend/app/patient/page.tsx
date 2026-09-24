'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import Header from '@/components/Header';

export default function PatientDashboard() {
  const { user, token, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const [appointments, setAppointments] = useState<any[]>([]);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [waitlistEntries, setWaitlistEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Wait for AuthContext to finish checking localStorage before deciding
    // the user isn't logged in — otherwise a genuinely logged-in user gets
    // redirected away on every refresh (see AuthContext.tsx).
    if (authLoading) return;

    if (!user || user.role !== 'patient') {
      router.push('/');
      return;
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const authHeaders = { Authorization: `Bearer ${token}` };

    const fetchAll = async () => {
      setLoading(true);
      try {
        const [apptRes, notifRes, waitlistRes] = await Promise.all([
          fetch(`${apiUrl}/api/appointments/me`, { headers: authHeaders }),
          fetch(`${apiUrl}/api/notifications`, { headers: authHeaders }),
          fetch(`${apiUrl}/api/waitlist`, { headers: authHeaders }),
        ]);

        if (!apptRes.ok) {
          throw new Error('Failed to fetch appointments');
        }
        setAppointments(await apptRes.json());
        setNotifications(notifRes.ok ? await notifRes.json() : []);
        setWaitlistEntries(waitlistRes.ok ? await waitlistRes.json() : []);
      } catch (err: any) {
        setError(err.message || 'An unexpected error occurred');
      } finally {
        setLoading(false);
      }
    };

    fetchAll();
  }, [authLoading, user, token, router]);

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

  if (user && user.role !== 'patient') {
    router.push('/');
    return null;
  }

  return (
    <>
      <Header />
      <main className="min-h-screen bg-gray-50 py-12">
        {user && user.role === 'patient' ? (
          <>
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="flex justify-between items-center mb-6">
                <h1 className="text-2xl font-bold">Patient Dashboard</h1>
                <div className="flex space-x-3">
                  {/* AI Booking link */}
                  <a
                    href="/ai-book"
                    className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-4 rounded-md"
                  >
                    Book Appointment (AI)
                  </a>
                  {/* Normal booking link */}
                  <a
                    href="/book"
                    className="ml-3 bg-white hover:bg-indigo-50 text-indigo-600 font-medium py-2 px-4 rounded-md border border-indigo-600"
                  >
                    Book Appointment (Form)
                  </a>
                </div>
              </div>

              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-600 rounded-md">
                  {error}
                </div>
              )}

              {loading ? (
                <p className="text-center py-8">Loading appointments...</p>
              ) : appointments.length === 0 ? (
                <p className="text-center py-8 text-gray-500">
                  You have no upcoming appointments.{' '}
                  <a href="/ai-book" className="text-indigo-600 hover:text-indigo-900">
                    Book one now with AI
                  </a>
                </p>
              ) : (
                <div className="space-y-6">
                  {appointments.map((appt: any) => (
                    <div key={appt.id} className="bg-white rounded-lg shadow-md p-6">
                      <div className="flex justify-between items-start">
                        <div>
                          <h2 className="text-lg font-medium text-gray-900">
                            Appointment with {appt.doctor_name || 'Unknown'}
                          </h2>
                          <p className="mt-1 text-sm text-gray-500">
                            {new Date(appt.start_datetime).toLocaleString()}
                          </p>
                        </div>
                        <div className="text-sm space-x-2">
                          <span className={`px-2 py-1 rounded-full ${
                            appt.status === 'scheduled'
                              ? 'bg-green-100 text-green-800'
                              : appt.status === 'cancelled'
                              ? 'bg-red-100 text-red-800'
                              : 'bg-gray-100 text-gray-800'
                          }`}>
                            {appt.status}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Notifications */}
              {!loading && notifications.length > 0 && (
                <div className="mt-10">
                  <h2 className="text-xl font-bold mb-3">Notifications</h2>
                  <div className="bg-white rounded-lg shadow-md divide-y divide-gray-200">
                    {notifications.slice(0, 10).map((n: any) => (
                      <div key={n.id} className="p-4">
                        <p className="text-sm text-gray-900">{n.message}</p>
                        {n.sent_at && (
                          <p className="text-xs text-gray-400 mt-1">{new Date(n.sent_at).toLocaleString()}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Waitlist */}
              {!loading && waitlistEntries.length > 0 && (
                <div className="mt-10">
                  <h2 className="text-xl font-bold mb-3">Your Waitlist Requests</h2>
                  <div className="bg-white rounded-lg shadow-md divide-y divide-gray-200">
                    {waitlistEntries.map((w: any) => (
                      <div key={w.id} className="p-4 flex justify-between items-center">
                        <span className="text-sm text-gray-900">
                          Preferred date: {w.preferred_date}
                          {w.earliest_time && ` from ${w.earliest_time.slice(0, 5)}`}
                          {w.latest_time && ` to ${w.latest_time.slice(0, 5)}`}
                        </span>
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                          w.status === 'offered' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                        }`}>
                          {w.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </>
        ) : (
          <p className="text-center py-12">Loading...</p>
        )}
      </main>
    </>
  );
}