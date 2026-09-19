"use client";

import { useActionState, type ReactNode } from "react";
import { bulkUpdateAccountItems } from "./actions";

// The rows inside stay server-rendered (passed as children); this only adds
// the client-side state needed to show why a save was refused.
export default function SaveForm({ children }: { children: ReactNode }) {
  const [state, action] = useActionState(bulkUpdateAccountItems, undefined);
  return (
    <form action={action}>
      {state?.error && (
        <p role="alert" className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          Not saved — nothing was changed. {state.error}
        </p>
      )}
      {children}
    </form>
  );
}
