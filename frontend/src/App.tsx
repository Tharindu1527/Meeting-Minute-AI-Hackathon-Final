import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { NotebookPen } from "lucide-react";
import { AnimatePresence, MotionConfig, motion } from "motion/react";
import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router";
import { Layout } from "./components/Layout";
import { Toaster } from "./components/Toaster";
import { ApiError, getToken, setToken, setUnauthorizedHandler } from "./lib/api";
import { ModelProvider, useStatus } from "./lib/hooks";
import { EASE } from "./lib/motion";
import type { AppStatus } from "./lib/types";
import { ActionItems } from "./pages/ActionItems";
import { Chat } from "./pages/Chat";
import { FactCheck } from "./pages/FactCheck";
import { Login, ServerUnreachable, SetupRequired } from "./pages/Gate";
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
          <Route path="*" element={<Navigate to="/meetings" replace />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

function Shell() {
  const status = useStatus();
  const client = useQueryClient();
  const [signedIn, setSignedIn] = useState(Boolean(getToken()));

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setSignedIn(false);
      client.clear();
    });
    return () => setUnauthorizedHandler(null);
  }, [client]);

  if (status.isPending) return <Splash />;
  if (status.isError) return <ServerUnreachable message={status.error.message} onRetry={() => status.refetch()} />;

  const s = status.data;
  if (s.missing_config.length) return <SetupRequired status={s} />;
  if (s.auth_required && !signedIn) return <Login onSignedIn={() => setSignedIn(true)} />;

  const signOut = s.auth_required
    ? () => {
        setToken(null);
        client.clear();
        setSignedIn(false);
      }
    : undefined;

  return (
    <ModelProvider status={s}>
      <Layout status={s} onSignOut={signOut}>
        <AnimatedRoutes status={s} />
      </Layout>
    </ModelProvider>
  );
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <QueryClientProvider client={queryClient}>
        <Toaster>
          <BrowserRouter>
            <Shell />
          </BrowserRouter>
        </Toaster>
      </QueryClientProvider>
    </MotionConfig>
  );
}
