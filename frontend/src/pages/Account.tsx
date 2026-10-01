import { useMutation, useQuery } from "@tanstack/react-query";
import { CalendarDays, Files, KeyRound, LogOut, MonitorSmartphone, Palette, Save, Trash2, TriangleAlert, UserRound } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { UserAvatar } from "../components/Avatar";
import { ConfirmDialog } from "../components/Dialog";
import { FormField, IconInput, PasswordInput } from "../components/forms";
import { ThemeSwitcher } from "../components/ThemeSwitcher";
import { useToast } from "../components/Toaster";
import { Alert, Button, Card, PageHeader, inputClass } from "../components/ui";
import { api, isRemembered } from "../lib/api";
import { useAuth, useUser } from "../lib/auth";
import { cx, formatDate, plural } from "../lib/format";
import { EASE } from "../lib/motion";

function ProfileHero() {
  const user = useUser();
  const meetings = useQuery({ queryKey: ["meetings"], queryFn: api.meetings });
  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: EASE }}
      className="relative overflow-hidden rounded-2xl border border-line bg-card shadow-card"
    >
      <div className="relative h-24 overflow-hidden bg-deep-gradient">
        <motion.div
          aria-hidden
          className="absolute -top-16 left-1/4 size-56 rounded-full bg-fuchsia-400/40 blur-3xl"
          animate={{ x: [0, 60, 0] }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
        />
        <div
          aria-hidden
          className="absolute inset-0 opacity-20"
          style={{ backgroundImage: "radial-gradient(rgb(255 255 255 / 0.6) 1px, transparent 1px)", backgroundSize: "18px 18px" }}
        />
      </div>
      <div className="flex flex-wrap items-end gap-x-5 gap-y-3 px-6 pb-6">
        <motion.div
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 260, damping: 18, delay: 0.1 }}
          className="relative z-10 -mt-10"
        >
          <UserAvatar user={user} size="lg" className="shadow-lift ring-4" />
        </motion.div>
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-xl font-semibold tracking-tight">{user.name}</h2>
          <p className="truncate text-sm text-subtle">{user.email}</p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-medium text-subtle">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-sunken px-3 py-1.5">
            <CalendarDays className="size-3.5" /> Joined {formatDate(user.created_at)}
          </span>
          {meetings.data && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-3 py-1.5 text-brand">
              <Files className="size-3.5" /> {plural(meetings.data.length, "meeting")}
            </span>
          )}
        </div>
      </div>
    </motion.section>
  );
}

function ProfileCard() {
  const user = useUser();
  const { setUser } = useAuth();
  const toast = useToast();
  const [name, setName] = useState(user.name);
  const save = useMutation({
    mutationFn: () => api.updateProfile(name),
    onSuccess: (updated) => {
      setUser(updated);
      setName(updated.name);
      toast("success", "Profile saved");
    },
  });
  const changed = name.trim() !== user.name && name.trim().length > 0;
  return (
    <Card title="Profile" description="How you appear in the app." icon={UserRound}>
      <form
        className="space-y-4"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          if (changed) save.mutate();
        }}
      >
        <FormField label="Name" htmlFor="account-name">
          <IconInput id="account-name" icon={UserRound} autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
        </FormField>
        <FormField label="Email" htmlFor="account-email" hint="You sign in with this address.">
          <input id="account-email" className={cx(inputClass, "h-11 cursor-not-allowed bg-sunken")} value={user.email} readOnly />
        </FormField>
        {save.isError && <Alert tone="error">{save.error.message}</Alert>}
        <div className="flex justify-end">
          <Button type="submit" variant="primary" icon={Save} loading={save.isPending} disabled={!changed}>
            Save changes
          </Button>
        </div>
      </form>
    </Card>
  );
}

function PasswordCard() {
  const user = useUser();
  const { replaceSession } = useAuth();
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const change = useMutation({
    mutationFn: () => api.changePassword(current, next),
    onSuccess: (session) => {
      replaceSession(session);
      setCurrent("");
      setNext("");
      setConfirm("");
      toast("success", "Password updated", "Any other devices were signed out.");
    },
  });
  const mismatch = confirm.length > 0 && confirm !== next;
  return (
    <Card title="Password" description="Changing it signs you out on every other device." icon={KeyRound}>
      <form
        className="space-y-4"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          change.mutate();
        }}
      >
        {/* Lets password managers attach the new password to the right account */}
        <input type="email" autoComplete="username" value={user.email} readOnly hidden />
        <FormField label="Current password" htmlFor="account-current">
          <PasswordInput id="account-current" autoComplete="current-password" value={current} onChange={setCurrent} />
        </FormField>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="New password" htmlFor="account-new">
            <PasswordInput id="account-new" autoComplete="new-password" showStrength value={next} onChange={setNext} />
          </FormField>
          <FormField label="Confirm new password" htmlFor="account-confirm" hint={mismatch ? <span className="text-bad">The passwords don't match.</span> : undefined}>
            <PasswordInput id="account-confirm" autoComplete="new-password" value={confirm} onChange={setConfirm}
              className={cx(mismatch && "border-bad focus:border-bad focus:ring-bad/15")} />
          </FormField>
        </div>
        {change.isError && <Alert tone="error">{change.error.message}</Alert>}
        <div className="flex justify-end">
          <Button type="submit" variant="primary" icon={KeyRound} loading={change.isPending} disabled={!current || next.length < 8 || next !== confirm}>
            Update password
          </Button>
        </div>
      </form>
    </Card>
  );
}

function SessionsCard() {
  const { replaceSession, signOut } = useAuth();
  const toast = useToast();
  const others = useMutation({
    mutationFn: api.signOutOthers,
    onSuccess: (session) => {
      replaceSession(session);
      toast("success", "Signed out everywhere else", "This device stays signed in.");
    },
  });
  return (
    <Card title="Sessions" description="Where you're signed in." icon={MonitorSmartphone}>
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-sunken/50 p-3.5">
        <span className="relative flex size-2.5">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-good opacity-50" />
          <span className="relative inline-flex size-2.5 rounded-full bg-good" />
        </span>
        <div className="min-w-0 flex-1 text-sm">
          <div className="font-medium">This device</div>
          <div className="text-xs text-subtle">{isRemembered() ? "Kept signed in for 30 days" : "Signed out when you close the browser"}</div>
        </div>
        <Button size="sm" variant="ghost" icon={LogOut} onClick={signOut}>
          Sign out
        </Button>
      </div>
      {others.isError && <Alert tone="error" className="mt-3">{others.error.message}</Alert>}
      <Button className="mt-4" icon={MonitorSmartphone} loading={others.isPending} onClick={() => others.mutate()}>
        Sign out of all other devices
      </Button>
    </Card>
  );
}

function DangerZone() {
  const { signOut } = useAuth();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const remove = useMutation({
    mutationFn: () => api.deleteAccount(password),
    onSuccess: (result) => {
      setOpen(false);
      signOut();
      toast("info", "Account deleted", `Your account and ${plural(result.meetings_deleted, "meeting")} were permanently deleted.`);
    },
  });
  const close = () => {
    setOpen(false);
    setPassword("");
    remove.reset();
  };
  return (
    <section className="rounded-2xl border border-bad/30 bg-bad-soft/40 p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-bad-soft text-bad">
            <TriangleAlert className="size-[18px]" />
          </span>
          <div>
            <h2 className="text-[15px] font-semibold tracking-tight">Delete account</h2>
            <p className="mt-0.5 text-sm text-subtle">Permanently deletes your account and every meeting in it. This can't be undone.</p>
          </div>
        </div>
        <Button variant="danger" icon={Trash2} onClick={() => setOpen(true)}>
          Delete account
        </Button>
      </div>
      <ConfirmDialog
        open={open}
        title="Delete your account?"
        confirmLabel="Delete forever"
        loading={remove.isPending}
        confirmDisabled={!password}
        onConfirm={() => remove.mutate()}
        onCancel={close}
      >
        <p>Your account, meetings, minutes and transcripts will be permanently deleted. Enter your password to confirm.</p>
        <div className="mt-4 text-ink">
          <PasswordInput aria-label="Your password" autoComplete="current-password" placeholder="Your password" value={password} onChange={setPassword} />
        </div>
        {remove.isError && <Alert tone="error" className="mt-3">{remove.error.message}</Alert>}
      </ConfirmDialog>
    </section>
  );
}

export function Account() {
  return (
    <div>
      <PageHeader eyebrow="Settings" title="Your account" description="Manage your profile, password, sessions and how the app looks." />
      <div className="space-y-5">
        <ProfileHero />
        <div className="grid gap-5 lg:grid-cols-2">
          <ProfileCard />
          <div className="space-y-5">
            <Card title="Appearance" description="Light, dark, or follow your device." icon={Palette}>
              <ThemeSwitcher labels />
            </Card>
            <SessionsCard />
          </div>
        </div>
        <PasswordCard />
        <DangerZone />
      </div>
    </div>
  );
}
