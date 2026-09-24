'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import Header from '@/components/Header';

interface ParsedRequest {
  specialization_name: string | null;
  doctor_name: string | null;
  preferred_date: string | null;
  time_of_day: string | null;
  urgency: string | null;
  experience_preference: string | null;
  wait_preference: string | null;
  appointment_type: string | null;
}

interface RecommendedSlot {
  doctor_id: number;
  doctor_name: string;
  specialization_id: number;
  specialization_name: string;
  start_datetime: string;
  end_datetime: string;
  score: number;
  predicted_duration_minutes: number | null;
  predicted_no_show_probability: number | null;
  predicted_waiting_time_minutes: number | null;
  explanations: string[];
}

const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function AIBookingPage() {
  const { user, token, isLoading: authLoading } = useAuth();
  const router = useRouter();

  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [bookedSlot, setBookedSlot] = useState<RecommendedSlot | null>(null);

  const [parsedRequest, setParsedRequest] = useState<ParsedRequest | null>(null);
  const [candidates, setCandidates] = useState<RecommendedSlot[]>([]);
  const [selectedSlot, setSelectedSlot] = useState<RecommendedSlot | null>(null);
  const [waitlistOffer, setWaitlistOffer] = useState<{ specialization_id: number; preferred_date: string } | null>(null);
  const [waitlistJoined, setWaitlistJoined] = useState(false);

  useEffect(() => {
    if (authLoading) return;
    if (!user || user.role !== 'patient') {
      router.push('/');
      return;
    }
    setMessages([
      {
        role: 'assistant',
        content:
          "Hello! I'm your AI booking assistant. Tell me what you need in your own words — for example: " +
          '"I need a cardiologist tomorrow evening, someone experienced, and I don\'t want to wait too long."',
      },
    ]);
  }, [authLoading, user, router]);

  const authHeaders = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = input;
    setInput('');
    setLoading(true);
    setError(null);
    setCandidates([]);
    setSelectedSlot(null);
    setMessages((prev: any) => [...prev, { role: 'user', content: userMessage }]);

    try {
      // Stage 1: parse the natural-language request into human concepts
      // (never a database ID) — see backend app/ai/service.py.
      const parseResponse = await fetch(`${apiUrl}/api/ai/parse`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({ text: userMessage }),
      });

      if (!parseResponse.ok) {
        const errorData = await parseResponse.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to parse your request');
      }

      const parseResult: {
        status: string;
        data: ParsedRequest | null;
        clarification_question: string | null;
      } = await parseResponse.json();

      if (parseResult.status !== 'complete' || !parseResult.data) {
        setMessages((prev: any) => [
          ...prev,
          { role: 'assistant', content: parseResult.clarification_question || "Could you tell me a bit more?" },
        ]);
        return;
      }

      setParsedRequest(parseResult.data);

      // Stage 2: ground the parsed request against the real database and get
      // ranked, actually-available candidate slots — see
      // app/ai/grounding.py and app/services/recommendation_service.py.
      const recommendResponse = await fetch(`${apiUrl}/api/ai/recommend`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify(parseResult.data),
      });

      if (!recommendResponse.ok) {
        const errorData = await recommendResponse.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to find available appointments');
      }

      const recommendResult: {
        status: string;
        clarification_question: string | null;
        candidates: RecommendedSlot[];
        specialization_id?: number | null;
        preferred_date?: string | null;
      } = await recommendResponse.json();

      if (recommendResult.status === 'complete' && recommendResult.candidates.length > 0) {
        setCandidates(recommendResult.candidates);
        setSelectedSlot(recommendResult.candidates[0]);
        setWaitlistOffer(null);
        setMessages((prev: any) => [
          ...prev,
          {
            role: 'assistant',
            content: `I found ${recommendResult.candidates.length} option${recommendResult.candidates.length > 1 ? 's' : ''} for you below — take a look and pick one.`,
          },
        ]);
      } else {
        if (recommendResult.status === 'no_availability' && recommendResult.specialization_id && recommendResult.preferred_date) {
          setWaitlistOffer({
            specialization_id: recommendResult.specialization_id,
            preferred_date: recommendResult.preferred_date,
          });
        }
        setMessages((prev: any) => [
          ...prev,
          {
            role: 'assistant',
            content: recommendResult.clarification_question || "I couldn't find anything matching that — could you try a different date or specialty?",
          },
        ]);
      }
    } catch (err: any) {
      const msg = err.message || 'An unexpected error occurred';
      setError(msg);
      setMessages((prev: any) => [...prev, { role: 'assistant', content: `Sorry, I ran into a problem: ${msg}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleBookSelectedSlot = async () => {
    if (!selectedSlot) return;

    setLoading(true);
    setError(null);

    try {
      // Every field below came from the server's own candidate list above —
      // never typed by the LLM or invented on the client — and the normal
      // scheduling engine (doctor lock, availability, overlap checks) still
      // re-validates it at booking time. The AI never bypasses booking.
      const bookingResponse = await fetch(`${apiUrl}/api/appointments`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({
          doctor_id: selectedSlot.doctor_id,
          specialization_id: selectedSlot.specialization_id,
          start_datetime: selectedSlot.start_datetime,
          end_datetime: selectedSlot.end_datetime,
          appointment_type: parsedRequest?.appointment_type || 'consultation',
          booking_source: 'ai',
        }),
      });

      if (!bookingResponse.ok) {
        const errorData = await bookingResponse.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to book appointment');
      }

      setBookedSlot(selectedSlot);
      setSuccess(true);
      setMessages((prev: any) => [
        ...prev,
        {
          role: 'assistant',
          content: `Great! I've booked your appointment with Dr. ${selectedSlot.doctor_name} for ${new Date(selectedSlot.start_datetime).toLocaleString()}.`,
        },
      ]);
      setTimeout(() => {
        router.push('/patient');
      }, 2000);
    } catch (err: any) {
      const msg = err.message || 'An unexpected error occurred';
      setError(msg);
      setMessages((prev: any) => [...prev, { role: 'assistant', content: `Sorry, I ran into a problem: ${msg}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleJoinWaitlist = async () => {
    if (!waitlistOffer) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiUrl}/api/waitlist`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({
          specialization_id: waitlistOffer.specialization_id,
          preferred_date: waitlistOffer.preferred_date,
          priority: 0,
        }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to join the waitlist');
      }
      setWaitlistJoined(true);
      setWaitlistOffer(null);
      setMessages((prev: any) => [
        ...prev,
        { role: 'assistant', content: "You're on the waitlist — I'll notify you if a matching slot opens up." },
      ]);
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred');
    } finally {
      setLoading(false);
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

  if (success) {
    return (
      <>
        <Header />
        <main className="min-h-screen bg-gray-50 py-12">
          <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="bg-white rounded-lg shadow-md p-8 text-center">
              <h1 className="mb-6 text-2xl font-bold">Appointment Booked!</h1>
              <p className="mb-4">You will be redirected to your dashboard shortly.</p>
              {bookedSlot && (
                <div className="mt-6 p-4 bg-blue-50 rounded-md text-left">
                  <p className="mb-2"><strong>Doctor:</strong> {bookedSlot.doctor_name}</p>
                  <p className="mb-2"><strong>Time:</strong> {new Date(bookedSlot.start_datetime).toLocaleString()}</p>
                </div>
              )}
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
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-white rounded-lg shadow-md">
            <div className="p-6">
              <h1 className="mb-4 text-2xl font-bold">AI Appointment Booking</h1>
              <p className="mb-6 text-gray-600">
                Book an appointment using natural language. I'll understand your request and ask for any missing details.
              </p>

              <div className="mb-6 h-80 overflow-y-auto border rounded-md p-4 bg-gray-50">
                {messages.map((msg: any, index: number) => (
                  <div key={index} className={`mb-4 ${msg.role === 'user' ? 'ml-auto' : 'mr-auto'}`}>
                    <div className={`max-w-xs px-3 py-2 rounded-md ${
                      msg.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-gray-200 text-gray-900'
                    }`}>
                      {msg.content}
                    </div>
                  </div>
                ))}
              </div>

              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-600 rounded-md">{error}</div>
              )}

              {waitlistOffer && !waitlistJoined && (
                <div className="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded-md flex justify-between items-center">
                  <span className="text-sm text-yellow-800">No open slots right now — want me to add you to the waitlist?</span>
                  <button
                    onClick={handleJoinWaitlist}
                    disabled={loading}
                    className="ml-4 px-3 py-1.5 text-sm bg-yellow-600 hover:bg-yellow-700 text-white rounded-md disabled:opacity-50"
                  >
                    Join Waitlist
                  </button>
                </div>
              )}

              {candidates.length > 0 && (
                <div className="mb-6">
                  <h2 className="mb-4 text-xl font-bold">Recommended Appointments</h2>
                  <div className="space-y-4">
                    {candidates.map((slot: any, index: number) => (
                      <div
                        key={index}
                        onClick={() => setSelectedSlot(slot)}
                        className={`border rounded-lg p-4 cursor-pointer ${
                          selectedSlot === slot ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200'
                        }`}
                      >
                        <div className="flex justify-between items-start">
                          <div>
                            <h3 className="font-semibold text-gray-900">
                              {slot.doctor_name} — {slot.specialization_name}
                            </h3>
                            <p className="text-sm text-gray-500">
                              {new Date(slot.start_datetime).toLocaleString()} · Score: {slot.score.toFixed(2)}
                            </p>
                            {slot.explanations.length > 0 && (
                              <div className="mt-2 text-sm space-y-1">
                                {slot.explanations.map((exp: any, expIndex: number) => (
                                  <p key={expIndex} className="text-gray-600">• {exp}</p>
                                ))}
                              </div>
                            )}
                          </div>
                          <button
                            type="button"
                            className={`px-3 py-1.5 text-sm rounded-md ${
                              selectedSlot === slot ? 'bg-indigo-600 text-white' : 'bg-gray-200 text-gray-700'
                            }`}
                          >
                            {selectedSlot === slot ? 'Selected' : 'Select'}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                  {selectedSlot && (
                    <div className="mt-4">
                      <button
                        onClick={handleBookSelectedSlot}
                        disabled={loading}
                        className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-4 rounded-md disabled:opacity-50"
                      >
                        {loading ? 'Booking...' : 'Book Selected Slot'}
                      </button>
                    </div>
                  )}
                </div>
              )}

              <form onSubmit={handleSubmit} className="flex space-x-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setInput(e.target.value)}
                  placeholder="Type your request here..."
                  disabled={loading}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-gray-900 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"                />
                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-md disabled:opacity-50"
                >
                  {loading ? 'Sending...' : 'Send'}
                </button>
              </form>

              <div className="mt-6 text-sm text-gray-500">
                <p className="mb-2">Try asking:</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>"I need a cardiologist tomorrow evening, someone experienced"</li>
                  <li>"Book a follow-up with a dermatologist next week, I don't want to wait long"</li>
                  <li>"Can I get a check-up this Friday morning?"</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
        </main>
      </>
    );
}