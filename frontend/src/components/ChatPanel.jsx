import { ArrowUp, Loader2, RotateCcw } from "lucide-react";
import { useState } from "react";

import { AnswerCard } from "@/components/AnswerCard";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from "@/components/ui/input-group";
import { Kbd } from "@/components/ui/kbd";
import { useAsk } from "@/hooks/useAsk";

const MIN_QUESTION_LENGTH = 3;

export function ChatPanel({ hasItems }) {
  const [question, setQuestion] = useState("");
  const { messages, loading, error, ask, reset } = useAsk();

  const canSend = !loading && question.trim().length >= MIN_QUESTION_LENGTH;

  const send = () => {
    if (!canSend) return;
    const trimmed = question.trim();
    setQuestion("");
    ask(trimmed);
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    send();
  };

  // Enter sends, shift+Enter keeps the newline.
  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Chat</CardTitle>
        <CardDescription>
          Each question is answered from your saved items only. Earlier turns are sent
          as context, so follow ups can refer back.
        </CardDescription>
        {messages.length > 0 && (
          <CardAction>
            <Button variant="ghost" size="sm" onClick={reset} disabled={loading}>
              <RotateCcw />
              Clear
            </Button>
          </CardAction>
        )}
      </CardHeader>

      <CardContent className="flex flex-col gap-5">
        {messages.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {hasItems
              ? "Ask something about what you have saved."
              : "Save a note or a URL in the Inbox tab first."}
          </p>
        )}

        {messages.map((message, index) =>
          message.role === "user" ? (
            <p
              key={index}
              className="self-end rounded-lg bg-accent px-3 py-2 text-sm text-accent-foreground"
            >
              {message.text}
            </p>
          ) : (
            <AnswerCard key={index} message={message} />
          ),
        )}

        {loading && (
          <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Searching and answering
          </span>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <form className="border-t pt-4" onSubmit={handleSubmit}>
          <InputGroup>
            <InputGroupTextarea
              required
              rows={3}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="What did the article say about chunking?"
            />
            <InputGroupAddon align="block-end" className="justify-between">
              <span className="text-xs">
                <Kbd>Enter</Kbd> to send, <Kbd>Shift</Kbd> <Kbd>Enter</Kbd> for a new line
              </span>
              <InputGroupButton
                type="submit"
                variant="default"
                size="icon-xs"
                disabled={!canSend}
                aria-label="Ask"
              >
                {loading ? <Loader2 className="animate-spin" /> : <ArrowUp />}
              </InputGroupButton>
            </InputGroupAddon>
          </InputGroup>
        </form>
      </CardContent>
    </Card>
  );
}
