'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import Header from '@/components/Header';

export default function Home() {
  const { user, isLoading: authLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (authLoading) return;
    if (user) {
      // Redirect to the appropriate dashboard based on role
      router.push(`/${user.role}`);
    }
  }, [authLoading, user, router]);

  if (authLoading || user) {
    // While the session is still being restored from localStorage, or once
    // we know the user is logged in and about to be redirected, avoid
    // flashing the logged-out landing page.
    return (
      <>
        <Header />
        <main className="min-h-screen bg-gray-50 py-12">
          <p className="text-center py-12">Loading...</p>
        </main>
      </>
    );
  }

  return (
    <>
      <Header />
      <main className="min-h-screen bg-gray-50 py-12">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-white rounded-lg shadow-md p-8">
            <h1 className="mb-6 text-2xl font-bold text-center">Welcome to SmartCare AI</h1>
            <p className="mb-6 text-center text-gray-600">
              An AI-powered patient appointment scheduler.
            </p>
            <div className="space-y-4">
              <a
                href="/login"
                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-3 px-4 rounded-md text-center"
              >
                Login
              </a>
              <a
                href="/register"
                className="w-full bg-white border border-indigo-600 hover:bg-indigo-50 text-indigo-600 font-medium py-3 px-4 rounded-md text-center"
              >
                Register as a Patient
              </a>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}