import { useEffect, useState } from "react";
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/24/solid";

export type ToastType = "success" | "error";

interface ToastProps {
  message: string;
  type: ToastType;
  isOpen: boolean;
  onClose: () => void;
  duration?: number;
}

export default function Toast({
  message,
  type,
  isOpen,
  onClose,
  duration = 2000,
}: ToastProps) {
  const [render, setRender] = useState(isOpen);

  if (isOpen && !render) {
    setRender(true);
  }

  useEffect(() => {
    if (!isOpen) return;

    const timer = setTimeout(() => {
      onClose();
    }, duration);

    return () => clearTimeout(timer);
  }, [isOpen, onClose, duration]);

  useEffect(() => {
    if (isOpen) return;

    const timer = setTimeout(() => setRender(false), 200);
    return () => clearTimeout(timer);
  }, [isOpen]);

  if (!render) return null;

  return (
    <div className="pointer-events-none fixed right-0 top-0 z-50 p-4">
      <div
        className={`pointer-events-auto flex w-80 max-w-full items-center gap-3 rounded-xl border p-4 shadow-lg transition-all duration-200 ${
          isOpen ? "translate-x-0 opacity-100" : "translate-x-full opacity-0"
        } ${
          type === "success"
            ? "border-emerald-200 bg-emerald-50"
            : "border-rose-200 bg-rose-50"
        }`}
        role="alert"
      >
        {type === "success" ? (
          <CheckCircleIcon className="h-6 w-6 shrink-0 text-emerald-600" />
        ) : (
          <ExclamationCircleIcon className="h-6 w-6 shrink-0 text-rose-600" />
        )}
        <div className="min-w-0 flex-1">
          <p
            className={`font-semibold ${
              type === "success" ? "text-emerald-900" : "text-rose-900"
            }`}
          >
            {type === "success" ? "Success" : "Error"}
          </p>
          <p
            className={`text-sm ${
              type === "success" ? "text-emerald-700" : "text-rose-700"
            }`}
          >
            {message}
          </p>
        </div>
      </div>
    </div>
  );
}
