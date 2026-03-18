import type { Source } from "../../types/api";
import { Badge } from "../ui/badge";

interface SourceCardProps {
  source: Source;
}

export function SourceCard({ source }: SourceCardProps) {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-2 rounded-md border p-2 text-sm hover:bg-muted transition-colors"
    >
      <Badge variant="outline" className="shrink-0">
        Source
      </Badge>
      <span className="truncate">{source.title}</span>
    </a>
  );
}
