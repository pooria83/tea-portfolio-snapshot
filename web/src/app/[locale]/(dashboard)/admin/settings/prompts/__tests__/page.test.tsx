import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

import PromptsPage from "../page";
import type { PromptTemplateResponse } from "@/types/llm";

const messages = {
  "settings.prompts": {
    title: "Prompt Templates",
    description: "Manage the prompts",
    prePrompt: "Description Pre-Prompt",
    prePromptDesc: "Before product details",
    endingPrompt: "Description Ending Prompt",
    endingPromptDesc: "After product details",
    chatAssistant: "Chat Assistant",
    chatAssistantDesc: "Assistant instructions",
    parseQuery: "Query Parser",
    parseQueryDesc: "Parser instructions",
    summarize: "Conversation Summarizer",
    summarizeDesc: "Summarizer instructions",
    titleLabel: "Conversation Title",
    titleDesc: "Title instructions",
    saved: "Prompt templates saved successfully",
    save: "Save Changes",
    saving: "Saving...",
  },
  common: { loading: "Loading...", error: "Something went wrong" },
};

const promptData: PromptTemplateResponse = {
  pre_prompt: "pre-prompt-v1",
  ending_prompt: "ending-prompt-v1",
  chat_assistant: "chat-assistant-v1",
  parse_query: "parse-query-v1",
  summarize: "summarize-v1",
  title: "title-v1",
};

const updatePromptTemplates = vi.fn();
const toastError = vi.fn();
const toastSuccess = vi.fn();

let queryResult: { data?: PromptTemplateResponse; isLoading: boolean } = {
  data: promptData,
  isLoading: false,
};
let mutationResult: { isLoading: boolean } = { isLoading: false };

vi.mock("@/store/api/adminApi", () => ({
  useGetPromptTemplatesQuery: () => queryResult,
  useUpdatePromptTemplatesMutation: () => [updatePromptTemplates, mutationResult],
}));

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => {
    const table = messages[namespace as keyof typeof messages] ?? {};
    return (key: string) => (table as Record<string, string>)[key] ?? key;
  },
}));

vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccess(...args),
    error: (...args: unknown[]) => toastError(...args),
  },
}));

function wrapper({ children }: { children: ReactNode }) {
  return <div>{children}</div>;
}

describe("PromptsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryResult = { data: promptData, isLoading: false };
    mutationResult = { isLoading: false };
    updatePromptTemplates.mockImplementation(() => ({ unwrap: async () => promptData }));
  });

  it("should render all six prompt cards with current values", async () => {
    render(<PromptsPage />, { wrapper });
    await waitFor(() => {
      const textareas = screen.getAllByRole("textbox") as HTMLTextAreaElement[];
      expect(textareas).toHaveLength(6);
      expect(textareas[0]!.value).toBe("pre-prompt-v1");
      expect(textareas[1]!.value).toBe("ending-prompt-v1");
      expect(textareas[2]!.value).toBe("chat-assistant-v1");
      expect(textareas[3]!.value).toBe("parse-query-v1");
      expect(textareas[4]!.value).toBe("summarize-v1");
      expect(textareas[5]!.value).toBe("title-v1");
    });
    expect(screen.getByText("Chat Assistant")).toBeTruthy();
    expect(screen.getByText("Conversation Title")).toBeTruthy();
  });

  it("should show loading state", () => {
    queryResult = { isLoading: true };
    render(<PromptsPage />, { wrapper });
    expect(screen.getByText("Loading...")).toBeTruthy();
  });

  it("should save edited prompts with all six values", async () => {
    render(<PromptsPage />, { wrapper });
    await waitFor(() => {
      expect((screen.getAllByRole("textbox")[2] as HTMLTextAreaElement).value).toBe(
        "chat-assistant-v1",
      );
    });
    const textareas = screen.getAllByRole("textbox");
    fireEvent.change(textareas[2]!, { target: { value: "chat-assistant-edited" } });
    fireEvent.click(screen.getByText("Save Changes"));

    await waitFor(() => {
      expect(updatePromptTemplates).toHaveBeenCalledWith({
        pre_prompt: "pre-prompt-v1",
        ending_prompt: "ending-prompt-v1",
        chat_assistant: "chat-assistant-edited",
        parse_query: "parse-query-v1",
        summarize: "summarize-v1",
        title: "title-v1",
      });
    });
    expect(toastSuccess).toHaveBeenCalledWith("Prompt templates saved successfully");
  });

  it("should show error toast when save fails", async () => {
    updatePromptTemplates.mockImplementation(() => ({
      unwrap: async () => {
        throw new Error("boom");
      },
    }));
    render(<PromptsPage />, { wrapper });
    fireEvent.click(screen.getByText("Save Changes"));

    await waitFor(() => {
      expect(toastError).toHaveBeenCalled();
    });
  });
});
