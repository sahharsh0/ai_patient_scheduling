'use client';

import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';

export default function Header() {
  const { user, isLoading: authLoading, logout } = useAuth();

  if (authLoading) {
    return (
      <header className="bg-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <Link href="/" className="flex items-center">
                <h1 className="text-xl font-semibold">SmartCare AI</h1>
              </Link>
            </div>
          </div>
        </div>
      </header>
    );
  }

  if (!user) {
    return (
      <header className="bg-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <Link href="/" className="flex items-center">
                <h1 className="text-xl font-semibold">SmartCare AI</h1>
              </Link>
            </div>
            <div className="hidden md:flex md:items-center md:space-x-4">
              <Link href="/login" className="text-gray-600 hover:text-gray-900">
                Login
              </Link>
              <Link href="/register" className="text-indigo-600 hover:text-indigo-900 font-medium">
                Register
              </Link>
            </div>
          </div>
        </div>
      </header>
    );
  }

  return (
    <header className="bg-white shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex">
            <Link href="/" className="flex items-center">
              <h1 className="text-xl font-semibold">SmartCare AI</h1>
            </Link>
          </div>
          <div className="hidden md:flex md:items-center md:space-x-4">
            <Link href={`/${user.role}`} className="text-gray-600 hover:text-gray-900">
              Dashboard
            </Link>
            {user.role === 'patient' && (
              <Link href="/ai-book" className="text-indigo-600 hover:text-indigo-900 font-medium">
                Book Appointment (AI)
              </Link>
            )}
            {user.role === 'doctor' && (
              <Link href="/doctor/schedule" className="text-indigo-600 hover:text-indigo-900 font-medium">
                Manage Schedule
              </Link>
            )}
          </div>
          <div className="md:flex md:items-center md:space-x-4">
            <div className="flex items-center text-sm text-gray-600">
              {user.name} ({user.role})
            </div>
            <button
              onClick={logout}
              className="flex items-center text-sm text-gray-600 hover:text-gray-900"
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}