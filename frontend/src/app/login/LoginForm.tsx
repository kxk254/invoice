"use client";

import { useActionState } from "react";
import Spinner from "@/components/Spinner";
import { login } from "./actions";

export default function LoginForm() {
  const [state, formAction, pending] = useActionState(login, undefined);

  return (
    <form action={formAction} className="flex flex-col gap-4">
      <div>
        <label htmlFor="username" className="block text-sm font-medium text-slate-700">
          Username
        </label>
        <input
          id="username"
          name="username"
          autoComplete="username"
          required
          className="field-input w-full py-2"
        />
      </div>
      <div>
        <label htmlFor="password" className="block text-sm font-medium text-slate-700">
          Password
        </label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          className="field-input w-full py-2"
        />
      </div>
      {state?.error && <p className="text-sm text-red-600">{state.error}</p>}
      <button type="submit" disabled={pending} className="btn-primary w-full py-2">
        {pending && <Spinner />}
        {pending ? "Signing in..." : "Sign in"}
      </button>
    </form>
  );
}
