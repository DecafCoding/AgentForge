/**
 * React Query mutation hook for the multi-agent research workflow.
 */

import { useMutation } from "@tanstack/react-query";

import { runResearch } from "../lib/api";
import type { WorkflowResponse } from "../types/api";

export function useWorkflow() {
  return useMutation<WorkflowResponse, Error, string>({
    mutationFn: (query: string) => runResearch(query),
  });
}
