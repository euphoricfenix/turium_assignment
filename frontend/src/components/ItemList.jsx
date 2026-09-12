import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const VISIBLE_LIMIT = 3;

function describe(items, visibleCount, showAll) {
  if (items.length === 0) return "Nothing saved yet";
  if (showAll || items.length <= VISIBLE_LIMIT) return `All ${items.length}`;
  return `${visibleCount} most recent of ${items.length}`;
}

export function ItemList({ items, loading, error }) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? items : items.slice(0, VISIBLE_LIMIT);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Saved items</CardTitle>
        <CardDescription>{describe(items, visible.length, showAll)}</CardDescription>
        {items.length > VISIBLE_LIMIT && (
          <CardAction>
            <Button variant="ghost" size="sm" onClick={() => setShowAll((current) => !current)}>
              {showAll ? "Show recent" : `Show all ${items.length}`}
            </Button>
          </CardAction>
        )}
      </CardHeader>

      <CardContent>
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {!error && !loading && items.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No items yet. Add a note or a URL above and it will show up here.
          </p>
        )}

        <ul className="divide-y">
          {visible.map((item) => (
            <li key={item.id} className="flex flex-col gap-1.5 py-3 first:pt-0 last:pb-0">
              <div className="flex items-center gap-2">
                <Badge variant="secondary">{item.source_type}</Badge>
                <span className="text-sm font-medium">{item.title}</span>
              </div>
              {item.source_url && (
                <a
                  href={item.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="truncate text-xs text-muted-foreground underline-offset-2 hover:underline"
                >
                  {item.source_url}
                </a>
              )}
              <p className="line-clamp-2 text-xs text-muted-foreground">{item.preview}</p>
              <p className="text-xs text-muted-foreground/80">
                {item.chunk_count} chunks - {item.created_at}
              </p>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
