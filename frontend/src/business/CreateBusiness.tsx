import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useBusiness } from "../context/BusinessContext";
import { ApiError } from "../services/apiClient";
import { createBusiness } from "../services/businesses";

export default function CreateBusiness() {
  const navigate = useNavigate();
  const { refresh, setActiveBusiness } = useBusiness();
  const [name, setName] = useState("");
  const [currency, setCurrency] = useState("IDR");
  const [timezone, setTimezone] = useState("Asia/Jakarta");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const business = await createBusiness({ name, currency, timezone });
      await refresh();
      setActiveBusiness(business);
      navigate("/overview");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-lg">
        <h2 className="text-center text-2xl font-bold text-blue-950">
          Create Your Business
        </h2>
        <p className="mt-2 text-center text-sm text-slate-600">
          Set up your business to get started
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label
              htmlFor="name"
              className="block text-sm font-medium text-slate-700"
            >
              Business Name
            </label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={150}
              className="mt-1 w-full rounded-lg border border-slate-300 px-4 py-2 text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="My Gyros Shop"
            />
          </div>

          <div>
            <label
              htmlFor="currency"
              className="block text-sm font-medium text-slate-700"
            >
              Currency
            </label>
            <input
              id="currency"
              type="text"
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              required
              minLength={3}
              maxLength={3}
              className="mt-1 w-full rounded-lg border border-slate-300 px-4 py-2 text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label
              htmlFor="timezone"
              className="block text-sm font-medium text-slate-700"
            >
              Timezone
            </label>
            <input
              id="timezone"
              type="text"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              required
              maxLength={64}
              className="mt-1 w-full rounded-lg border border-slate-300 px-4 py-2 text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-blue-950 px-4 py-2 font-semibold text-white hover:bg-blue-900 disabled:opacity-60"
          >
            {submitting ? "Creating…" : "Create Business"}
          </button>
        </form>
      </div>
    </div>
  );
}
