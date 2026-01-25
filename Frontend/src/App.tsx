import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "@/components/ThemeProvider";
import Index from "./pages/Index";
import ActivityLogs from "./pages/ActivityLogs";
import Leads from "./pages/Leads";
import LeadDetail from "./pages/LeadDetail";
import SystemHealth from "./pages/SystemHealth";
import EmailTemplates from "./pages/EmailTemplates";
import Analytics from "./pages/Analytics";
import Campaigns from "./pages/Campaigns";
import Pipeline from "./pages/Pipeline";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <ThemeProvider>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Index />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/leads" element={<Leads />} />
            <Route path="/leads/:id" element={<LeadDetail />} />
            <Route path="/campaigns" element={<Campaigns />} />
            <Route path="/pipeline" element={<Pipeline />} />
            <Route path="/activity" element={<ActivityLogs />} />
            <Route path="/email-templates" element={<EmailTemplates />} />
            <Route path="/health" element={<SystemHealth />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  </ThemeProvider>
);

export default App;
