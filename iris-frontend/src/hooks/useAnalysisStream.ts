"use client";

import { useEffect, useRef, useCallback } from "react";
import { useAnalysisStore } from "./useAnalysisStore";
import { probeSession, getHistoryDetail } from "@/utils/api";
import type { SSEEvent, SSEEventType } from "@/types/api";

const MAX_RETRIES = 5;
const BASE_BACKOFF_MS = 1000;

/**
 * All named SSE event types the backend can send.
 * We register a listener for each one.
 */
const SSE_EVENT_TYPES: SSEEventType[] = [
  "tool_start",
  "tool_end",
  "text_delta",
  "text",
  "context_compacted",
  "retry",
  "error",
  "system",
  "steering",
  "user_input_needed",
  "analysis_complete",
  "done",
];

export function useAnalysisStream(analysisId: string | null) {
  const handleSSEEvent = useAnalysisStore((s) => s.handleSSEEvent);
  const loadSnapshot = useAnalysisStore((s) => s.loadSnapshot);
  const pageState = useAnalysisStore((s) => s.pageState);
  const eventSourceRef = useRef<EventSource | null>(null);
  const retriesRef = useRef(0);
  const initializedRef = useRef(false);

  const connectSSE = useCallback(
    (id: string) => {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const es = new EventSource(`${baseUrl}/api/analyze/${id}/stream`);
      eventSourceRef.current = es;

      for (const eventType of SSE_EVENT_TYPES) {
        es.addEventListener(eventType, (evt: MessageEvent) => {
          try {
            if (evt.data === undefined || evt.data === null) return;
            const data = JSON.parse(evt.data);
            const sseEvent: SSEEvent = {
              type: eventType,
              data,
              timestamp: Date.now(),
            };
            handleSSEEvent(sseEvent);
            retriesRef.current = 0;

            // "done" is the stream sentinel — close connection
            if (eventType === "done") {
              es.close();
              eventSourceRef.current = null;
            }
          } catch (err) {
            console.error(`Failed to parse SSE event [${eventType}]:`, err);
          }
        });
      }

      es.onerror = () => {
        es.close();
        eventSourceRef.current = null;

        if (retriesRef.current < MAX_RETRIES) {
          const delay = BASE_BACKOFF_MS * Math.pow(2, retriesRef.current);
          retriesRef.current += 1;
          setTimeout(() => connectSSE(id), delay);
        } else {
          console.error("Max SSE retries reached, giving up.");
        }
      };
    },
    [handleSSEEvent]
  );

  // Initial connection: probe to check if live or replay
  useEffect(() => {
    if (!analysisId || initializedRef.current) return;
    initializedRef.current = true;

    (async () => {
      const probe = await probeSession(analysisId);
      if (probe.live) {
        if (probe.query) {
          useAnalysisStore.setState({ analysisQuery: probe.query });
        }
        connectSSE(analysisId);
      } else {
        try {
          const snapshot = await getHistoryDetail(analysisId);
          loadSnapshot(snapshot);
        } catch {
          console.error("Analysis not found");
          useAnalysisStore.setState({ pageState: "COMPLETE" });
        }
      }
    })();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      retriesRef.current = 0;
      initializedRef.current = false;
    };
  }, [analysisId, connectSSE, loadSnapshot]);

  // Reconnect SSE when pageState goes back to RUNNING (multi-turn continuation)
  useEffect(() => {
    if (
      analysisId &&
      initializedRef.current &&
      pageState === "RUNNING" &&
      !eventSourceRef.current
    ) {
      retriesRef.current = 0;
      connectSSE(analysisId);
    }
  }, [analysisId, pageState, connectSSE]);
}
