"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { LoadingPage } from "@/components/ui/Spinner";

export default function Home() {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading) {
      if (user) {
        router.replace("/ibkr");
      } else {
        router.replace("/login");
      }
    }
  }, [user, loading, router]);

  return <LoadingPage />;
}
