import LoginForm from "./LoginForm";

export default function LoginPage() {
  return (
    <div className="flex flex-1 items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm card p-8">
        <div className="mb-6 flex items-center gap-2.5">
          <svg width="32" height="32" viewBox="0 0 32 32" className="shrink-0 rounded-lg" aria-hidden="true">
            <defs>
              <linearGradient id="login-logo-grad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#0f766e" />
                <stop offset="100%" stopColor="#14b8a6" />
              </linearGradient>
            </defs>
            <rect width="32" height="32" rx="8" fill="url(#login-logo-grad)" />
            <path
              d="M9.5 6.5 L16 15 M22.5 6.5 L16 15 M16 15 L16 26 M9.5 17 L22.5 17 M9.5 22 L22.5 22"
              fill="none"
              stroke="#ffffff"
              strokeWidth={3.2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <h1 className="text-xl font-semibold text-slate-900">Sign in</h1>
        </div>
        <LoginForm />
      </div>
    </div>
  );
}
