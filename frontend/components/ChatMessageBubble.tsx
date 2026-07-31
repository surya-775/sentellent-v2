export interface Citation {
  type: string;
  label: string;
  url?: string;
  stock?: string;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
}

export default function ChatMessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-xl rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap ${
          isUser ? "bg-accent text-ink" : "bg-white/5 border border-white/10"
        }`}
      >
        <p>{message.content}</p>
        {message.citations && message.citations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-white/10 space-y-1">
            {message.citations.map((c, i) => (
              <p key={i} className="text-xs text-gray-400">
                [{i + 1}] {c.stock ? `${c.stock}: ` : ""}
                {c.url ? (
                  <a href={c.url} target="_blank" rel="noreferrer" className="underline hover:text-accent">
                    {c.label}
                  </a>
                ) : (
                  c.label
                )}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
