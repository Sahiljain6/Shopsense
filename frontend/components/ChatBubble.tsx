export default function ChatBubble({ role, text }: { role: "user" | "assistant"; text: string }) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm ${isUser ? "bg-blue-600 text-white" : "border border-slate-200 bg-white text-slate-800"}`}>
        {text}
      </div>
    </div>
  );
}
