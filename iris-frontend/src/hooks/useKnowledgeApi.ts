"use client";

import { useState, useEffect, useCallback } from "react";
import type { KnowledgeDocument } from "@/types/knowledge";
import * as api from "@/utils/api";

export function useKnowledgeApi() {
  const [docs, setDocs] = useState<KnowledgeDocument[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<KnowledgeDocument | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDocs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getKnowledgeDocs();
      setDocs(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  const selectDoc = useCallback(async (docId: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getKnowledgeDoc(docId);
      setSelectedDoc(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load document");
    } finally {
      setLoading(false);
    }
  }, []);

  const uploadNote = useCallback(
    async (title: string, content: string, company?: string, tags?: string[]) => {
      setUploading(true);
      setError(null);
      try {
        await api.uploadKnowledgeNote({ title, content, company, tags });
        await fetchDocs();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to upload note");
      } finally {
        setUploading(false);
      }
    },
    [fetchDocs]
  );

  const uploadUrl = useCallback(
    async (url: string, title?: string, company?: string, tags?: string[]) => {
      setUploading(true);
      setError(null);
      try {
        await api.uploadKnowledgeUrl({ url, title, company, tags });
        await fetchDocs();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to upload URL");
      } finally {
        setUploading(false);
      }
    },
    [fetchDocs]
  );

  const uploadFile = useCallback(
    async (file: File, title?: string, company?: string, tags?: string[]) => {
      setUploading(true);
      setError(null);
      try {
        await api.uploadKnowledgeFile(file, { title, company, tags });
        await fetchDocs();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to upload file");
      } finally {
        setUploading(false);
      }
    },
    [fetchDocs]
  );

  const deleteDoc = useCallback(
    async (docId: string) => {
      setError(null);
      try {
        await api.deleteKnowledgeDoc(docId);
        if (selectedDoc?.id === docId) {
          setSelectedDoc(null);
        }
        await fetchDocs();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to delete document");
      }
    },
    [selectedDoc, fetchDocs]
  );

  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

  return {
    docs,
    selectedDoc,
    loading,
    uploading,
    error,
    fetchDocs,
    selectDoc,
    uploadNote,
    uploadUrl,
    uploadFile,
    deleteDoc,
  };
}
