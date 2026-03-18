"use client";

import { useEffect, useRef, useCallback } from "react";
import { useAnalysisStore } from "./useAnalysisStore";
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
  const eventSourceRef = useRef<EventSource | null>(null);
  const retriesRef = useRef(0);

  const connect = useCallback(() => {
    if (!analysisId) return;

    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
    const es = new EventSource(`${baseUrl}/api/analyze/${analysisId}/stream`);
    eventSourceRef.current = es;

    // Backend sends NAMED events (event: tool_start\ndata: {...}\n\n).
    // EventSource.onmessage only fires for UNNAMED events, so we must
    // register a listener for each named event type.
    for (const eventType of SSE_EVENT_TYPES) {
      es.addEventListener(eventType, (evt: MessageEvent) => {
        try {
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
        setTimeout(connect, delay);
      } else {
        console.error("Max SSE retries reached, giving up.");
      }
    };
  }, [analysisId, handleSSEEvent]);

  useEffect(() => {
    connect();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      retriesRef.current = 0;
    };
  }, [connect]);
}
