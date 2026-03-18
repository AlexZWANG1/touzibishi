"use client";

import { useState, useEffect, useCallback } from "react";
import type { MemoryTree, MemoryType, MemoryFileContent, MemoryViewMode } from "@/types/memory";
import * as api from "@/utils/api";

interface SelectedFile {
  memoryType: MemoryType;
  filename: string;
}

export function useMemoryApi() {
  const [tree, setTree] = useState<MemoryTree>({
    companies: [],
    sectors: [],
    patterns: [],
    calibration: [],
  });
  const [selectedFile, setSelectedFile] = useState<SelectedFile | null>(null);
  const [fileContent, setFileContent] = useState<MemoryFileContent | null>(null);
  const [viewMode, setViewMode] = useState<MemoryViewMode>("render");
  const [editContent, setEditContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTree = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getMemoryTree();
      setTree(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load memory tree");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchFile = useCallback(async (memoryType: MemoryType, filename: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getMemoryFile(memoryType, filename);
      setFileContent(data);
      setEditContent(data.content);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load file");
    } finally {
      setLoading(false);
    }
  }, []);

  const selectFile = useCallback(
    (memoryType: MemoryType, filename: string) => {
      setSelectedFile({ memoryType, filename });
      setViewMode("render");
      fetchFile(memoryType, filename);
    },
    [fetchFile]
  );

  const saveFile = useCallback(async () => {
    if (!selectedFile) return;
    setSaving(true);
    setError(null);
    try {
      await api.updateMemoryFile(selectedFile.memoryType, selectedFile.filename, editContent);
      setFileContent((prev) =>
        prev ? { ...prev, content: editContent } : null
      );
      setViewMode("render");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save file");
    } finally {
      setSaving(false);
    }
  }, [selectedFile, editContent]);

  const deleteFile = useCallback(async () => {
    if (!selectedFile) return;
    setError(null);
    try {
      await api.deleteMemoryFile(selectedFile.memoryType, selectedFile.filename);
      setSelectedFile(null);
      setFileContent(null);
      await fetchTree();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete file");
    }
  }, [selectedFile, fetchTree]);

  useEffect(() => {
    fetchTree();
  }, [fetchTree]);

  return {
    tree,
    selectedFile,
    fileContent,
    viewMode,
    editContent,
    loading,
    saving,
    error,
    selectFile,
    setViewMode,
    setEditContent,
    saveFile,
    deleteFile,
    refreshTree: fetchTree,
  };
}
