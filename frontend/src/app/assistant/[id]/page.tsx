import { api } from "@/lib/api";

import { Chat } from "./chat";

export default async function ConversationPage(props: PageProps<"/assistant/[id]">) {
  const { id } = await props.params;
  const conversation = await api.conversation(id);
  return <Chat initial={conversation} />;
}
