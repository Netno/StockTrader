import Sidebar from "@/components/layout/Sidebar";
import PaperTradingBanner from "@/components/layout/PaperTradingBanner";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Spacer that pushes content below the fixed mobile top bar */}
        <div className="md:hidden h-[52px] shrink-0" />
        <PaperTradingBanner />
        <main className="flex-1 overflow-y-auto p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
