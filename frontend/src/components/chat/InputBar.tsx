import { useState } from "react";

import { Button } from "../ui/button";
import { Input } from "../ui/input";

interface InputBarProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function InputBar({ onSend, disabled }: InputBarProps) {
  const [value, setValue] = useState("");

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex gap-2 border-t p-4">
      <Input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask a question..."
        disabled={disabled}
        className="flex-1"
      />
      <Button onClick={handleSubmit} disabled={disabled || !value.trim()}>
        Send
      </Button>
    </div>
  );
}
