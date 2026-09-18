import LoginForm from "./LoginForm";

export default function LoginPage() {
  return (
    <div className="flex flex-1 items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm card p-8">
        <div className="mb-6 flex items-center gap-2.5">
          <svg width="32" height="32" viewBox="0 0 32 32" className="shrink-0 rounded-lg" aria-hidden="true">
            <defs>
              <linearGradient id="login-logo-grad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#4f46e5" />
                <stop offset="100%" stopColor="#7c3aed" />
              </linearGradient>
            </defs>
            <rect width="32" height="32" rx="8" fill="url(#login-logo-grad)" />
            <path
              d="M10.5 7.5 L16 15 M21.5 7.5 L16 15 M16 15 L16 25 M11 18.5 L21 18.5 M11 21.5 L21 21.5"
              fill="none"
              stroke="#ffffff"
              strokeWidth={2.8}
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
