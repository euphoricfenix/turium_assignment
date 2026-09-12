import { useState } from "react";

import { api } from "@/api/client";

export function useIngest(onSaved) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const submit = async (sourceType, content) => {
    setSaving(true);
    try {
      const item = await api.ingest(sourceType, content);
      setError("");
      await onSaved?.();
      return item;
    } catch (cause) {
      setError(cause.message);
      return null;
    } finally {
      setSaving(false);
    }
  };

  return { submit, saving, error };
}
