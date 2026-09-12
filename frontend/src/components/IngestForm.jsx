import { Loader2 } from "lucide-react";
import { useState } from "react";

import { useIngest } from "@/hooks/useIngest";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

const SOURCE_TYPES = [
  { value: "note", label: "Note" },
  { value: "url", label: "URL" },
];

export function IngestForm({ onSaved }) {
  const [sourceType, setSourceType] = useState("note");
  const [content, setContent] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const { submit, saving, error } = useIngest(onSaved);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setConfirmation("");
    const item = await submit(sourceType, content.trim());
    if (item) {
      setContent("");
      setConfirmation(`Saved "${item.title}" as ${item.chunk_count} chunks`);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Add to inbox</CardTitle>
        <CardDescription>
          A plain note, or a URL fetched server side and converted to markdown.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="flex gap-2">
            {SOURCE_TYPES.map(({ value, label }) => (
              <Button
                key={value}
                type="button"
                size="sm"
                variant={sourceType === value ? "default" : "outline"}
                onClick={() => setSourceType(value)}
              >
                {label}
              </Button>
            ))}
          </div>

          {sourceType === "url" ? (
            <Input
              type="url"
              required
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder="https://example.com/article"
            />
          ) : (
            <Textarea
              required
              rows={5}
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder="Paste a note. Markdown headings become sections."
            />
          )}

          <div className="flex items-center gap-3">
            <Button type="submit" disabled={saving || !content.trim()}>
              {saving && <Loader2 className="animate-spin" />}
              Save
            </Button>
            {saving && sourceType === "url" && (
              <span className="text-sm text-muted-foreground">
                Fetching the page, this can take a while
              </span>
            )}
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {confirmation && !error && (
            <p className="text-sm text-muted-foreground">{confirmation}</p>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
