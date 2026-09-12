import { ChevronDown } from "lucide-react";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

// Keeps the delimiters, so [2] survives the split as its own part.
const CITATION_TOKEN = /(\[\d+\])/g;

function CitationMark({ number }) {
  return (
    <span className="ml-0.5 inline-flex size-4 items-center justify-center rounded-full bg-primary/10 align-middle text-[10px] font-semibold tabular-nums text-primary">
      {number}
    </span>
  );
}

function AnswerText({ text }) {
  return (
    <p className="whitespace-pre-wrap text-sm leading-relaxed">
      {text.split(CITATION_TOKEN).map((part, index) => {
        const number = /^\[(\d+)\]$/.exec(part)?.[1];
        return number ? <CitationMark key={index} number={number} /> : part;
      })}
    </p>
  );
}

function Source({ source }) {
  return (
    <article className="flex flex-col gap-0.5 py-2 first:pt-0 last:pb-0">
      <div className="flex items-baseline justify-between gap-2">
        <span className="min-w-0 text-xs">
          <CitationMark number={source.citation} />
          <span className="ml-1.5 font-medium">{source.title}</span>
          {source.heading_path && (
            <span className="text-muted-foreground"> - {source.heading_path}</span>
          )}
        </span>
        <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{source.score}</span>
      </div>
      {source.source_url && (
        <a
          href={source.source_url}
          target="_blank"
          rel="noreferrer"
          className="truncate text-xs text-muted-foreground underline-offset-2 hover:underline"
        >
          {source.source_url}
        </a>
      )}
      <p className="text-xs leading-relaxed text-muted-foreground">{source.snippet}</p>
    </article>
  );
}

export function AnswerCard({ message }) {
  const { sources } = message;

  return (
    <div className="flex flex-col gap-3">
      <AnswerText text={message.answer} />

      {sources.length > 0 && (
        <Collapsible className="rounded-md border bg-background px-3">
          <CollapsibleTrigger className="group/sources flex w-full items-center gap-2 py-2 text-xs text-muted-foreground">
            <span>
              {sources.length} {sources.length === 1 ? "source" : "sources"}
            </span>
            <span className="flex items-center">
              {sources.map((source) => (
                <CitationMark key={source.citation} number={source.citation} />
              ))}
            </span>
            <ChevronDown className="ml-auto size-4 shrink-0 transition-transform group-data-[state=open]/sources:rotate-180" />
          </CollapsibleTrigger>
          <CollapsibleContent className="divide-y border-t pt-2 pb-3">
            {sources.map((source) => (
              <Source key={`${source.citation}-${source.item_id}`} source={source} />
            ))}
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  );
}
