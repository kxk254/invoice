import LoginForm from "./LoginForm";

export default function LoginPage() {
  return (
    <div className="flex flex-1 items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="mb-6 text-xl font-semibold text-slate-900">Sign in</h1>
        <LoginForm />
      </div>
    </div>
  );
}
