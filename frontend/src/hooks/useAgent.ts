/**
 * React Query mutation hook for the single-agent endpoint.
 */

import { useMutation } from "@tanstack/react-query";

import { askAgent } from "../lib/api";
import type { AskResponse } from "../types/api";

export function useAgent() {
  return useMutation<AskResponse, Error, string>({
    mutationFn: (question: string) => askAgent(question),
  });
}
