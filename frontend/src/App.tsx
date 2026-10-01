import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NotebookPen } from "lucide-react";
import { AnimatePresence, MotionConfig, motion } from "motion/react";
import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router";
import { CommandPaletteProvider } from "./components/CommandPalette";
import { Layout } from "./components/Layout";
import { Toaster } from "./components/Toaster";
import { ApiError } from "./lib/api";
import { AuthProvider, useAuth } from "./lib/auth";
import { ModelProvider, useStatus } from "./lib/hooks";
import { EASE } from "./lib/motion";
import { ThemeProvider } from "./lib/theme";
import type { AppStatus } from "./lib/types";
import { Account } from "./pages/Account";
import { ActionItems } from "./pages/ActionItems";
import { AuthRoutes } from "./pages/Auth";
import { Chat } from "./pages/Chat";
import { FactCheck } from "./pages/FactCheck";
import { ServerUnreachable, SetupRequired } from "./pages/Gate";
import { Listen } from "./pages/Listen";
import { MeetingDetail } from "./pages/MeetingDetail";
import { Meetings } from "./pages/Meetings";
import { NewMeeting } from "./pages/NewMeeting";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      // Retry network hiccups, not "not found" or "sign in" answers
      retry: (failures, error) => failures < 2 && !(error instanceof ApiError && error.status >= 400 && error.status < 500),
    },
  },
});

function Splash() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <motion.div
        className="flex size-14 items-center justify-center rounded-2xl bg-brand-gradient text-white shadow-glow"
        animate={{ scale: [1, 1.06, 1], opacity: [0.85, 1, 0.85] }}
        transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
      >
        <NotebookPen className="size-6" />
      </motion.div>
    </div>
  );
}

/** Pages fade and slide as you move between them; each keeps its own location while leaving */
function AnimatedRoutes({ status }: { status: AppStatus }) {
  const location = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [location.pathname]);
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6, transition: { duration: 0.12 } }}
        transition={{ duration: 0.3, ease: EASE }}
      >
        <Routes location={location}>
          <Route path="/" element={<Navigate to="/meetings" replace />} />
          <Route path="/new" element={<NewMeeting status={status} />} />
          <Route path="/meetings" element={<Meetings />} />
          <Route path="/meetings/:meetingId" element={<MeetingDetail status={status} />} />
          <Route path="/action-items" element={<ActionItems />} />
          <Route path="/chat" element={<Chat status={status} />} />
          <Route path="/listen" element={<Listen status={status} />} />
          <Route path="/fact-check" element={<FactCheck />} />
          <Route path="/account" element={<Account />} />
          <Route path="*" element={<Navigate to="/meetings" replace />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

function Shell() {
  const status = useStatus();
  const auth = useAuth();

  if (status.isPending || auth.checking) return <Splash />;
  if (status.isError) return <ServerUnreachable message={status.error.message} onRetry={() => status.refetch()} />;

  const s = status.data;
  if (s.missing_config.length) return <SetupRequired status={s} />;
  if (auth.error) return <ServerUnreachable message={auth.error.message} onRetry={auth.retry} />;
  if (!auth.user) return <AuthRoutes status={s} />;

  return (
    <ModelProvider status={s}>
      <CommandPaletteProvider>
        <Layout status={s}>
          <AnimatedRoutes status={s} />
        </Layout>
      </CommandPaletteProvider>
    </ModelProvider>
  );
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <Toaster>
            <BrowserRouter>
              <AuthProvider>
                <Shell />
              </AuthProvider>
            </BrowserRouter>
          </Toaster>
        </ThemeProvider>
      </QueryClientProvider>
    </MotionConfig>
  );
}
