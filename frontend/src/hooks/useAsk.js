import { useState } from "react";

import { api } from "@/api/client";

// Earlier messages sent as context. Capped so a long session does not grow the
// request without bound; the server caps it again.
const HISTORY_LIMIT = 6;

function toHistory(messages) {
  return messages.slice(-HISTORY_LIMIT).map((message) => ({
    role: message.role,
    text: message.role === "user" ? message.text : message.answer,
  }));
}

/**
 * Chat transcript state. The transcript is the history: what is shown is what
 * gets sent, so clearing it clears the context with it.
 */
export function useAsk() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const ask = async (question) => {
    const history = toHistory(messages);
    setMessages((current) => [...current, { role: "user", text: question }]);
    setLoading(true);
    try {
      const result = await api.ask(question, history);
      setMessages((current) => [...current, { role: "assistant", ...result }]);
      setError("");
    } catch (cause) {
      setError(cause.message);
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setMessages([]);
    setError("");
  };

  return { messages, loading, error, ask, reset };
}
