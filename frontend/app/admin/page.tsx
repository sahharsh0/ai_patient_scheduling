'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import Header from '@/components/Header';

interface AdminStats {
  total_patients: number;
  total_doctors: number;
  total_appointments: number;
  scheduled_appointments: number;
  completed_appointments: number;
  cancelled_appointments: number;
  no_show_appointments: number;
  ai_booked_appointments: number;
}

export default function AdminDashboard() {
  const { user, token, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [appointments, setAppointments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;

    if (!user || user.role !== 'admin') {
      router.push('/');
      return;
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const authHeaders = { Authorization: `Bearer ${token}` };

    const fetchData = async () => {
      setLoading(true);
      try {
        const [statsRes, appointmentsRes] = await Promise.all([
          fetch(`${apiUrl}/api/admin/stats`, { headers: authHeaders }),
          fetch(`${apiUrl}/api/appointments`, { headers: authHeaders }),
        ]);

        if (!statsRes.ok || !appointmentsRes.ok) {
          throw new Error('Failed to load admin dashboard data');
        }

        setStats(await statsRes.json());
        setAppointments(await appointmentsRes.json());
      } catch (err: any) {
        setError(err.message || 'An unexpected error occurred');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
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

  if (user && user.role !== 'admin') {
    router.push('/');
    return null;
  }

  const statCards = stats
    ? [
        { label: 'Total Patients', value: stats.total_patients },
        { label: 'Total Doctors', value: stats.total_doctors },
        { label: 'Total Appointments', value: stats.total_appointments },
        { label: 'Scheduled', value: stats.scheduled_appointments },
        { label: 'Completed', value: stats.completed_appointments },
        { label: 'Cancelled', value: stats.cancelled_appointments },
        { label: 'No-Shows', value: stats.no_show_appointments },
        { label: 'AI-Booked', value: stats.ai_booked_appointments },
      ]
    : [];

  return (
    <>
      <Header />
      <main className="min-h-screen bg-gray-50 py-12">
        {user && user.role === 'admin' ? (
          <>
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="flex justify-between items-center mb-6">
                <h1 className="text-2xl font-bold">Admin Dashboard</h1>
              </div>

              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-600 rounded-md">
                  {error}
                </div>
              )}

              {loading ? (
                <p className="text-center py-8">Loading dashboard...</p>
              ) : (
                <>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
                    {statCards.map((card) => (
                      <div key={card.label} className="bg-white rounded-lg shadow-md p-4 text-center">
                        <div className="text-2xl font-bold text-indigo-600">{card.value}</div>
                        <div className="text-sm text-gray-500 mt-1">{card.label}</div>
                      </div>
                    ))}
                  </div>

                  {appointments.length === 0 ? (
                    <p className="text-center py-8 text-gray-500">No appointments in the system.</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="min-w-full bg-white border border-gray-200">
                        <thead>
                          <tr className="bg-gray-50">
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Patient</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Doctor</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Start Time</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200">
                          {appointments.map((appt: any) => (
                            <tr key={appt.id} className="hover:bg-gray-50">
                              <td className="px-4 py-3 text-sm text-gray-900">{appt.id}</td>
                              <td className="px-4 py-3 text-sm text-gray-700">{appt.patient_name || 'Unknown'}</td>
                              <td className="px-4 py-3 text-sm text-gray-700">{appt.doctor_name || 'Unknown'}</td>
                              <td className="px-4 py-3 text-sm text-gray-700">
                                {new Date(appt.start_datetime).toLocaleString()}
                              </td>
                              <td className="px-4 py-3 text-sm">
                                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                  appt.status === 'scheduled'
                                    ? 'bg-green-100 text-green-800'
                                    : appt.status === 'cancelled'
                                    ? 'bg-red-100 text-red-800'
                                    : 'bg-gray-100 text-gray-800'
                                }`}>
                                  {appt.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
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
