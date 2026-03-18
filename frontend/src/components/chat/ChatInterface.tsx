import { useEffect, useRef, useState } from "react";

import { useAgent } from "../../hooks/useAgent";
import { ScrollArea } from "../ui/scroll-area";
import { InputBar } from "./InputBar";
import { MessageBubble, type Message } from "./MessageBubble";

export function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const agent = useAgent();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, agent.isPending]);

  const handleSend = async (question: string) => {
    setMessages((prev) => [...prev, { role: "user", content: question }]);

    try {
      const response = await agent.mutateAsync(question);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.answer,
          sources: response.sources,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, something went wrong. Please try again.",
        },
      ]);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <ScrollArea className="flex-1 p-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <p>Ask a question to get started.</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        {agent.isPending && <MessageBubble loading />}
        <div ref={bottomRef} />
      </ScrollArea>
      <InputBar onSend={handleSend} disabled={agent.isPending} />
    </div>
  );
}
