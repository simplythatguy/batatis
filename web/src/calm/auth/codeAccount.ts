/** Accounts made by signing in with an access code have a made-up address that is never shown. */
export const hasRealEmail = (user: { email: string }) => !user.email.endsWith("@code.batatis.invalid");
