import React, { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { AiQueryPanel } from "./AiQueryPanel";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  X,
  Send,
  Bot,
  Loader2,
  Maximize2,
  Minimize2,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { aiApi, ChatMessage } from "../../api/ai";
import { cn } from "../../lib/utils";
import { useAiStore } from "../../stores/use-ai-store";

export const ChatAssistant: React.FC = () => {
  const { t } = useTranslation();
  const {
    isOpen,
    toggleOpen,
    isExpanded,
    toggleExpanded,
    messages,
    addMessage,
    clearHistory,
    status,
    checkStatus,
  } = useAiStore();

  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Poll for status while open and not yet ready (store handles the initial check on open)
  useEffect(() => {
    if (!isOpen || status === "ready") return;
    const interval = setInterval(checkStatus, 5000);
    return () => clearInterval(interval);
  }, [isOpen, status, checkStatus]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  const handleSendMessage = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = { role: "user", content: input };
    addMessage(userMessage);
    setInput("");
    setIsLoading(true);

    try {
      const response = await aiApi.chat({
        message: input,
        history: messages,
      });

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: response.response,
      };
      addMessage(assistantMessage);
    } catch (error) {
      console.error("AI Chat Error:", error);
      toast.error(t("ai.error"));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed bottom-24 right-6 z-[9999]">
      {/* Toggle Button */}
      {!isOpen && (
        <motion.button
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          onClick={toggleOpen}
          className="w-16 h-16 rounded-full bg-accent text-bg-base shadow-lg shadow-accent/40 flex items-center justify-center group relative overflow-hidden ring-4 ring-bg-base"
        >
          <div className="absolute inset-0 bg-gradient-to-tr from-accent/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
          <Sparkles className="w-8 h-8 relative z-10" />
        </motion.button>
      )}

      {/* Chat Window */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{
              opacity: 0,
              scale: 0.8,
              y: 100,
              transformOrigin: "bottom right",
            }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.8, y: 100 }}
            className={cn(
              "bg-surface/80 backdrop-blur-xl shadow-2xl rounded-[32px] border border-border flex flex-col overflow-hidden transition-all duration-300",
              isExpanded
                ? "w-[800px] h-[85vh] max-h-[1000px]"
                : "w-[420px] h-[650px]",
            )}
          >
            {/* Header */}
            <div className="p-6 bg-elevated/40 border-b border-border flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-accent/20 flex items-center justify-center border border-accent/40 shadow-lg">
                  <Sparkles className="w-5 h-5 text-accent" />
                </div>
                <div>
                  <h3 className="font-bold text-lg leading-none tracking-tight text-primary mb-1.5">
                    {t("ai.title")}
                  </h3>
                  <div className="flex items-center gap-1.5">
                    {status === "ready" && (
                      <>
                        <span className="w-1.5 h-1.5 rounded-full bg-success shadow-sm animate-pulse" />
                        <span className="text-[10px] font-bold text-success uppercase tracking-widest">
                          {t("ai.ready")}
                        </span>
                      </>
                    )}
                    {status === "loading" && (
                      <>
                        <span className="w-1.5 h-1.5 rounded-full bg-warning shadow-sm animate-pulse" />
                        <span className="text-[10px] font-bold text-warning uppercase tracking-widest">
                          {t("ai.initializing")}
                        </span>
                      </>
                    )}
                    {status === "error" && (
                      <>
                        <span className="w-1.5 h-1.5 rounded-full bg-danger shadow-sm" />
                        <span className="text-[10px] font-bold text-danger uppercase tracking-widest">
                          {t("common.status")}
                        </span>
                      </>
                    )}
                    {status === "offline" && (
                      <>
                        <span className="w-1.5 h-1.5 rounded-full bg-secondary" />
                        <span className="text-[10px] font-bold text-secondary uppercase tracking-widest">
                          {t("ai.connecting")}
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={clearHistory}
                  className="p-2.5 hover:bg-elevated rounded-xl transition-colors text-secondary hover:text-danger"
                  title={t("ai.clear_chat")}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
                <button
                  onClick={toggleExpanded}
                  className="p-2.5 hover:bg-elevated rounded-xl transition-colors text-secondary hover:text-primary"
                >
                  {isExpanded ? (
                    <Minimize2 className="w-4 h-4" />
                  ) : (
                    <Maximize2 className="w-4 h-4" />
                  )}
                </button>
                <button
                  onClick={toggleOpen}
                  className="p-2.5 hover:bg-elevated rounded-xl transition-colors text-secondary hover:text-primary"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Suggestion Chips */}
            {messages.length === 0 && (
              <div className="px-6 py-4 flex gap-2 overflow-x-auto custom-scrollbar border-b border-border">
                <button
                  onClick={() => setInput(t("ai.quick_fleet_health"))}
                  className="bg-accent/10 border border-accent/20 px-4 py-2 rounded-xl text-[11px] font-bold whitespace-nowrap text-accent hover:bg-accent/20 transition-all uppercase tracking-tight"
                >
                  {t("ai.quick_fleet_health")}
                </button>
                <button
                  onClick={() => setInput(t("ai.quick_best_route"))}
                  className="bg-accent/10 border border-accent/20 px-4 py-2 rounded-xl text-[11px] font-bold whitespace-nowrap text-accent hover:bg-accent/20 transition-all uppercase tracking-tight"
                >
                  {t("ai.quick_best_route")}
                </button>
                <button
                  onClick={() => setInput(t("ai.quick_maintenance"))}
                  className="bg-accent/10 border border-accent/20 px-4 py-2 rounded-xl text-[11px] font-bold whitespace-nowrap text-accent hover:bg-accent/20 transition-all uppercase tracking-tight"
                >
                  {t("ai.quick_maintenance")}
                </button>
              </div>
            )}

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar bg-transparent">
              {/* Faz 9 — kategori-farkında sorgu paneli (grafik + aksiyon + ses) */}
              <AiQueryPanel />
              {messages.map((msg: ChatMessage, idx: number) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={cn(
                    "flex flex-col gap-2",
                    msg.role === "user" ? "items-end" : "items-start",
                  )}
                >
                  <div
                    className={cn(
                      "px-5 py-4 text-sm max-w-[85%] shadow-xl rounded-[24px]",
                      msg.role === "user"
                        ? "bg-accent text-bg-base rounded-tr-sm font-bold shadow-lg shadow-accent/20"
                        : "bg-elevated text-primary rounded-tl-sm border border-border leading-relaxed",
                    )}
                  >
                    {msg.role === "assistant" && (
                      <div className="flex items-center gap-2 text-accent mb-3">
                        <Bot className="w-4 h-4" />
                        <span className="text-[10px] font-black uppercase tracking-widest">
                          LojiNext AI
                        </span>
                      </div>
                    )}
                    {msg.content}
                  </div>
                </motion.div>
              ))}
              {isLoading && (
                <div className="flex flex-col items-start gap-2 max-w-[85%]">
                  <div className="bg-elevated text-accent px-5 py-4 rounded-2xl rounded-tl-none border border-border flex items-center gap-3">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span className="text-[10px] font-black uppercase tracking-widest">
                      {t("ai.thinking")}
                    </span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <form
              onSubmit={handleSendMessage}
              className="p-5 bg-elevated/40 border-t border-border flex items-center gap-3 shrink-0"
            >
              <div className="flex-1 relative">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={t("ai.placeholder")}
                  className="w-full bg-surface border border-border rounded-2xl pl-5 pr-12 py-3.5 text-sm text-primary placeholder-secondary focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/30 transition-all shadow-inner"
                  disabled={isLoading}
                />
                <div className="absolute right-4 top-1/2 -translate-y-1/2 opacity-50">
                  <Sparkles className="w-4 h-4 text-accent" />
                </div>
              </div>
              <button
                type="submit"
                disabled={!input.trim() || isLoading}
                className="w-[52px] h-[52px] rounded-2xl bg-accent text-bg-base flex items-center justify-center shadow-lg shadow-accent/20 hover:scale-105 active:scale-95 disabled:opacity-50 disabled:scale-100 transition-all shrink-0"
              >
                <Send className="w-5 h-5 ml-1" />
              </button>
            </form>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
