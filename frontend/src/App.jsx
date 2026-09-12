import { Inbox, MessagesSquare } from "lucide-react";

import { ChatPanel } from "@/components/ChatPanel";
import { IngestForm } from "@/components/IngestForm";
import { ItemList } from "@/components/ItemList";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useItems } from "@/hooks/useItems";

export default function App() {
  const { items, loading, error, refresh } = useItems();

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card">
        <div className="mx-auto max-w-3xl px-6 py-5">
          <h1 className="font-heading text-xl font-semibold">AI Knowledge Inbox</h1>
          <p className="text-sm text-muted-foreground">
            Save notes and URLs, then ask questions answered from what you saved.
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-8">
        <Tabs defaultValue="inbox">
          <TabsList>
            <TabsTrigger value="inbox">
              <Inbox />
              Inbox
            </TabsTrigger>
            <TabsTrigger value="chat">
              <MessagesSquare />
              Chat
            </TabsTrigger>
          </TabsList>

          <TabsContent value="inbox" className="mt-6 flex flex-col gap-6">
            <IngestForm onSaved={refresh} />
            <ItemList items={items} loading={loading} error={error} />
          </TabsContent>

          <TabsContent value="chat" className="mt-6">
            <ChatPanel hasItems={items.length > 0} />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
