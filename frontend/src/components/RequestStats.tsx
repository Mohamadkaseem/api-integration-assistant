"use client";

import { useEffect, useState } from "react";

import { getRequestStats } from "@/lib/api";

// Shows one number from the Request Builder history on the dashboard.
export function RequestStat({ field }: { field: "total" | "successful" | "failed" }) {
  const [value, setValue] = useState("…");
  useEffect(() => {
    getRequestStats()
      .then((stats) => setValue(String(stats[field])))
      .catch(() => setValue("—"));
  }, [field]);
  return <>{value}</>;
}
