"use client";

import { useEffect, ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Nav } from "@/components/layout/Nav";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { LoadingPage } from "@/components/ui/Spinner";

export default function AuthenticatedLayout({
  children,
}: {
  children: ReactNode;
}) {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [user, loading, router]);

  if (loading) {
    return <LoadingPage />;
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Nav />
      <ErrorBanner />
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-4">
        {children}
      </main>
    </div>
  );
}
