"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// Redirect to main IBKR page which shows positions
export default function PositionsPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/ibkr");
  }, [router]);

  return null;
}
