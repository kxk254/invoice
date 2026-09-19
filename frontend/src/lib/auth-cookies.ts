// Shared between session.ts (Server Actions/Components) and proxy.ts (edge
// middleware, which can't import session.ts's "next/headers" usage) so the
// two never drift apart.
//
// The access-token cookie's maxAge must stay strictly below Django's
// SIMPLE_JWT ACCESS_TOKEN_LIFETIME (core/settings.py, currently 30 minutes).
// If it matched exactly, network latency between minting the JWT and
// setting the cookie means the cookie could outlive the token by a hair,
// and proxy.ts only refreshes when the cookie is *absent* - it never
// inspects an expired-but-still-present one. Any request landing in that
// gap sends a dead token, and apiGet's caller sees an unhandled 401 instead
// of being redirected to /login. A 5-minute margin guarantees the cookie
// always disappears first, so that existing "absent -> refresh" path always
// fires in time.
export const ACCESS_TOKEN_MAX_AGE = 60 * 25;
// The refresh-token cookie deliberately has no maxAge (session cookie), so
// closing the browser forces a fresh login.
