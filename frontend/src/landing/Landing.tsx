import { Link } from "react-router-dom";

export default function Landing() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-blue-950 to-blue-800 px-6 text-center">
      <h1 className="text-4xl font-extrabold text-white md:text-6xl">
        GyrosProject
      </h1>
      <p className="mt-4 max-w-md text-lg text-blue-100">
        landing page website
      </p>
      <Link
        to="/login"
        className="mt-8 rounded-xl bg-white px-8 py-3 font-semibold text-blue-950 shadow-lg hover:bg-blue-50"
      >
        Get Started
      </Link>
    </div>
  );
}
