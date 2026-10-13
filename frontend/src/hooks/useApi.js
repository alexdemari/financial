import { useEffect, useState } from "react";

export function useApi(url, refreshMs = 60_000) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = await response.json();
        if (active) { setData(payload); setError(null); }
      } catch (caught) {
        if (active) setError(caught);
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    const interval = window.setInterval(load, refreshMs);
    return () => { active = false; window.clearInterval(interval); };
  }, [url, refreshMs]);
  return { data, loading, error };
}
