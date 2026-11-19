"use client";

import { useEffect, useState } from "react";

import { listProjects } from "@/lib/api";

// Shows the real number of saved projects on the dashboard.
export function ProjectCount() {
  const [count, setCount] = useState<string>("…");

  useEffect(() => {
    listProjects()
      .then((projects) => setCount(String(projects.length)))
      .catch(() => setCount("—"));
  }, []);

  return <>{count}</>;
}
