import { api } from "@/lib/api";

import { Chat } from "./chat";

export default async function ConversationPage(props: PageProps<"/assistant/[id]">) {
  const { id } = await props.params;
  const { q } = await props.searchParams;
  const conversation = await api.conversation(id);
  const firstPrompt = typeof q === "string" && conversation.transcript.length === 0 ? q : undefined;
  return <Chat initial={conversation} firstPrompt={firstPrompt} />;
}
