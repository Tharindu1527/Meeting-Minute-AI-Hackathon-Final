import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, AtSign, KeyRound, LockKeyhole, MailCheck, ShieldCheck, Ticket, UserRound, type LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router";
import { AuthShell } from "../components/AuthShell";
import { Checkbox, FormField, IconInput, PasswordInput } from "../components/forms";
import { useToast } from "../components/Toaster";
import { Alert, Button, Spinner, buttonClass } from "../components/ui";
import { api } from "../lib/api";
import { firstName, useAuth } from "../lib/auth";
import { celebrate } from "../lib/confetti";
import { cx } from "../lib/format";
import type { AppStatus, Session } from "../lib/types";

/** Where to go after signing in: the page the user originally asked for, or the dashboard */
function useReturnTo() {
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  return from && !from.startsWith("/login") ? from : "/meetings";
}

function Heading({ icon: Icon, title, children }: { icon?: LucideIcon; title: string; children?: ReactNode }) {
  return (
    <div className="mb-8">
      {Icon && (
        <motion.div
          initial={{ scale: 0.5, rotate: -15, opacity: 0 }}
          animate={{ scale: 1, rotate: 0, opacity: 1 }}
          transition={{ type: "spring", stiffness: 280, damping: 18, delay: 0.05 }}
          className="mb-5 flex size-12 items-center justify-center rounded-2xl bg-brand-gradient text-white shadow-glow dark:text-brand-ink"
        >
          <Icon className="size-[22px]" />
        </motion.div>
      )}
      <h1 className="text-[28px] leading-tight font-semibold tracking-tight">{title}</h1>
      {children && <p className="mt-2 text-[15px] text-subtle">{children}</p>}
    </div>
  );
}

function SubmitButton({ loading, disabled, children }: { loading: boolean; disabled?: boolean; children: ReactNode }) {
  return (
    <Button type="submit" variant="primary" size="lg" className="group w-full" loading={loading} disabled={disabled}>
      {children}
      {!loading && <ArrowRight className="size-4 transition-transform duration-200 group-hover:translate-x-1" />}
    </Button>
  );
}

/** A form that shakes when the request fails */
function ShakeForm({ failed, onSubmit, children }: { failed: boolean; onSubmit: () => void; children: ReactNode }) {
  return (
    <motion.form
      noValidate
      animate={failed ? { x: [0, -9, 9, -6, 6, -2, 0] } : { x: 0 }}
      transition={{ duration: 0.45 }}
      className="space-y-5"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      {children}
    </motion.form>
  );
}

function FooterLink({ children }: { children: ReactNode }) {
  return <p className="mt-8 text-center text-sm text-subtle">{children}</p>;
}

const linkClass = "font-semibold text-brand underline-offset-4 transition hover:underline";

function Login({ status }: { status: AppStatus }) {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const returnTo = useReturnTo();
  const toast = useToast();
  const [email, setEmail] = useState((location.state as { email?: string } | null)?.email ?? "");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);

  const login = useMutation({
    mutationFn: () => api.login({ email, password, remember }),
    onSuccess: (session: Session) => {
      signIn(session, remember);
      toast("success", `Welcome back, ${firstName(session.user)}!`);
      navigate(returnTo, { replace: true });
    },
  });

  return (
    <>
      <Heading title="Welcome back">Sign in to pick up where you left off.</Heading>
      <ShakeForm failed={login.isError} onSubmit={() => login.mutate()}>
        <FormField label="Email" htmlFor="login-email">
          <IconInput id="login-email" icon={AtSign} type="email" autoComplete="email" autoFocus placeholder="you@company.com"
            value={email} onChange={(e) => setEmail(e.target.value)} />
        </FormField>
        <FormField
          label="Password"
          htmlFor="login-password"
          action={
            status.auth.password_reset && (
              <Link to="/forgot-password" state={{ email }} className="text-xs font-medium text-brand underline-offset-4 hover:underline">
                Forgot password?
              </Link>
            )
          }
        >
          <PasswordInput id="login-password" autoComplete="current-password" value={password} onChange={setPassword} />
        </FormField>
        <Checkbox checked={remember} onChange={setRemember}>
          Keep me signed in for 30 days
        </Checkbox>
        {login.isError && <Alert tone="error">{login.error.message}</Alert>}
        <SubmitButton loading={login.isPending} disabled={!email.trim() || !password}>
          Sign in
        </SubmitButton>
      </ShakeForm>
      {status.auth.signup_open ? (
        <FooterLink>
          New to Meeting Minutes AI?{" "}
          <Link to="/register" className={linkClass}>
            Create an account
          </Link>
        </FooterLink>
      ) : (
        <FooterLink>Need an account? Ask the app's owner to create one for you.</FooterLink>
      )}
    </>
  );
}

function Register({ status }: { status: AppStatus }) {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [remember, setRemember] = useState(true);
  const needsCode = status.auth.invite_code_required;

  const register = useMutation({
    mutationFn: () => api.register({ name, email, password, invite_code: inviteCode, remember }),
    onSuccess: (session: Session) => {
      signIn(session, remember);
      celebrate();
      toast("success", `Welcome, ${firstName(session.user)}!`, "Your account is ready. Create your first meeting to get started.");
      navigate("/meetings", { replace: true });
    },
  });

  if (!status.auth.signup_open) {
    return (
      <>
        <Heading icon={LockKeyhole} title="Sign-up is closed">
          New accounts aren't being created right now. Ask the app's owner to set one up for you.
        </Heading>
        <Link to="/login" className={buttonClass("primary", "lg", "w-full")}>
          <ArrowLeft className="size-4" /> Back to sign in
        </Link>
      </>
    );
  }

  return (
    <>
      <Heading title="Create your account">Turn your next meeting into clear minutes in a few minutes.</Heading>
      <ShakeForm failed={register.isError} onSubmit={() => register.mutate()}>
        <FormField label="Your name" htmlFor="register-name">
          <IconInput id="register-name" icon={UserRound} autoComplete="name" autoFocus placeholder="Ana Silva"
            value={name} onChange={(e) => setName(e.target.value)} />
        </FormField>
        <FormField label="Work email" htmlFor="register-email">
          <IconInput id="register-email" icon={AtSign} type="email" autoComplete="email" placeholder="you@company.com"
            value={email} onChange={(e) => setEmail(e.target.value)} />
        </FormField>
        <FormField label="Password" htmlFor="register-password">
          <PasswordInput id="register-password" autoComplete="new-password" showStrength value={password} onChange={setPassword} />
        </FormField>
        {needsCode && (
          <FormField label="Invite code" htmlFor="register-code" hint="New accounts on this app need the invite code from its owner.">
            <IconInput id="register-code" icon={Ticket} autoComplete="off" spellCheck={false} placeholder="Enter your invite code"
              value={inviteCode} onChange={(e) => setInviteCode(e.target.value)} />
          </FormField>
        )}
        <Checkbox checked={remember} onChange={setRemember}>
          Keep me signed in for 30 days
        </Checkbox>
        {register.isError && <Alert tone="error">{register.error.message}</Alert>}
        <SubmitButton loading={register.isPending} disabled={!name.trim() || !email.trim() || password.length < 8 || (needsCode && !inviteCode.trim())}>
          Create account
        </SubmitButton>
        <p className="flex items-center justify-center gap-1.5 text-xs text-subtle">
          <ShieldCheck className="size-3.5 text-good" /> Your meetings stay private to your account.
        </p>
      </ShakeForm>
      <FooterLink>
        Already have an account?{" "}
        <Link to="/login" className={linkClass}>
          Sign in
        </Link>
      </FooterLink>
    </>
  );
}

function BackToSignIn({ email }: { email?: string }) {
  return (
    <FooterLink>
      <Link to="/login" state={{ email }} className="inline-flex items-center gap-1.5 font-semibold text-brand underline-offset-4 hover:underline">
        <ArrowLeft className="size-4" /> Back to sign in
      </Link>
    </FooterLink>
  );
}

function ForgotPassword({ status }: { status: AppStatus }) {
  const location = useLocation();
  const [email, setEmail] = useState((location.state as { email?: string } | null)?.email ?? "");
  const forgot = useMutation({ mutationFn: () => api.forgotPassword(email) });

  if (!status.auth.password_reset) {
    return (
      <>
        <Heading icon={KeyRound} title="Forgot your password?">
          Password reset by email isn't set up on this server. Ask the app's owner to help you get back in.
        </Heading>
        <BackToSignIn />
      </>
    );
  }

  if (forgot.isSuccess) {
    return (
      <>
        <Heading icon={MailCheck} title="Check your inbox">
          If <span className="font-semibold text-ink">{email.trim()}</span> has an account, a link to choose a new password is on its
          way. It works once and expires in an hour.
        </Heading>
        <Alert tone="info">Nothing after a few minutes? Check your spam folder, or try again.</Alert>
        <Button className="mt-5 w-full" size="lg" onClick={() => forgot.reset()}>
          Send another link
        </Button>
        <BackToSignIn email={email} />
      </>
    );
  }

  return (
    <>
      <Heading icon={KeyRound} title="Forgot your password?">
        Enter your account's email and we'll send you a link to choose a new one.
      </Heading>
      <ShakeForm failed={forgot.isError} onSubmit={() => forgot.mutate()}>
        <FormField label="Email" htmlFor="forgot-email">
          <IconInput id="forgot-email" icon={AtSign} type="email" autoComplete="email" autoFocus placeholder="you@company.com"
            value={email} onChange={(e) => setEmail(e.target.value)} />
        </FormField>
        {forgot.isError && <Alert tone="error">{forgot.error.message}</Alert>}
        <SubmitButton loading={forgot.isPending} disabled={!email.trim()}>
          Send reset link
        </SubmitButton>
      </ShakeForm>
      <BackToSignIn email={email} />
    </>
  );
}

function ResetPassword() {
  const location = useLocation();
  const navigate = useNavigate();
  const { signIn } = useAuth();
  const toast = useToast();
  // The token is in the URL fragment (#token=...), which browsers never send to servers or put in Referer headers
  const token = new URLSearchParams(location.hash.slice(1)).get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const check = useQuery({ queryKey: ["reset-token", token], queryFn: () => api.checkResetToken(token), enabled: Boolean(token), retry: false });
  const reset = useMutation({
    mutationFn: () => api.resetPassword(token, password),
    onSuccess: (session) => {
      signIn(session, true);
      toast("success", "Password updated", "You're signed in. Any other devices were signed out.");
      navigate("/meetings", { replace: true });
    },
  });

  if (token && check.isPending) {
    return (
      <div className="flex justify-center py-10">
        <Spinner label="Checking your reset link…" />
      </div>
    );
  }
  if (!token || !check.data) {
    return (
      <>
        <Heading icon={KeyRound} title="This link has expired">
          {check.error?.message ?? "This reset link is incomplete."} Reset links work once and expire after an hour.
        </Heading>
        <Link to="/forgot-password" className={buttonClass("primary", "lg", "w-full")}>
          Request a new link
        </Link>
        <BackToSignIn />
      </>
    );
  }

  const mismatch = confirm.length > 0 && confirm !== password;
  return (
    <>
      <Heading icon={LockKeyhole} title="Choose a new password">
        For <span className="font-semibold text-ink">{check.data.email}</span>. You'll be signed in straight away.
      </Heading>
      <ShakeForm failed={reset.isError} onSubmit={() => reset.mutate()}>
        <FormField label="New password" htmlFor="reset-password">
          <PasswordInput id="reset-password" autoComplete="new-password" autoFocus showStrength value={password} onChange={setPassword} />
        </FormField>
        <FormField label="Confirm new password" htmlFor="reset-confirm" hint={mismatch ? <span className="text-bad">The passwords don't match.</span> : undefined}>
          <PasswordInput id="reset-confirm" autoComplete="new-password" value={confirm} onChange={setConfirm}
            className={cx(mismatch && "border-bad focus:border-bad focus:ring-bad/15")} />
        </FormField>
        {reset.isError && <Alert tone="error">{reset.error.message}</Alert>}
        <SubmitButton loading={reset.isPending} disabled={password.length < 8 || confirm !== password}>
          Update password
        </SubmitButton>
      </ShakeForm>
      <BackToSignIn email={check.data.email} />
    </>
  );
}

/** Everything a signed-out visitor can see */
export function AuthRoutes({ status }: { status: AppStatus }) {
  const location = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [location.pathname]);
  return (
    <AuthShell screenKey={location.pathname}>
      <Routes location={location}>
        <Route path="/login" element={<Login status={status} />} />
        <Route path="/register" element={<Register status={status} />} />
        <Route path="/forgot-password" element={<ForgotPassword status={status} />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="*" element={<Navigate to="/login" replace state={{ from: location.pathname + location.search }} />} />
      </Routes>
    </AuthShell>
  );
}
