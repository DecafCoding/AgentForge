import type { Source } from "../../types/api";
import { Badge } from "../ui/badge";
import { Card } from "../ui/card";
import { Skeleton } from "../ui/skeleton";
import { SourceCard } from "./SourceCard";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
}

interface MessageBubbleProps {
  message?: Message;
  loading?: boolean;
}

export function MessageBubble({ message, loading }: MessageBubbleProps) {
  if (loading) {
    return (
      <div className="mb-4">
        <Skeleton className="h-4 w-3/4 mb-2" />
        <Skeleton className="h-4 w-1/2" />
      </div>
    );
  }

  if (!message) return null;

  return (
    <div className={`mb-4 ${message.role === "user" ? "flex justify-end" : ""}`}>
      <div className={message.role === "user" ? "max-w-[80%]" : "max-w-[90%]"}>
        <Badge
          variant={message.role === "user" ? "default" : "secondary"}
          className="mb-1"
        >
          {message.role === "user" ? "You" : "Agent"}
        </Badge>
        <Card className="p-3">
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          {message.sources && message.sources.length > 0 && (
            <div className="mt-3 space-y-1.5 border-t pt-2">
              {message.sources.map((source, i) => (
                <SourceCard key={i} source={source} />
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

export type { Message };
