import React, { useState } from "react";
import { Search, Sparkles, Send, AlertCircle, ShoppingCart, RefreshCw, Bot, User } from "lucide-react";

export default function App() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      sender: "bot",
      type: "chat",
      text: "Hi! I'm your Blinkit AI assistant. You can ask if an item is in stock (e.g. 'Is paneer available?') or tell me what you'd like to cook!",
    },
  ]);
  const [loading, setLoading] = useState(false);

  const handleSend = async (e) => {
    e?.preventDefault();
    if (!input.trim() || loading) return;

    const userQuery = input.trim();
    setInput("");

    // Append user query to conversation history
    const userMsg = {
      id: Date.now().toString(),
      sender: "user",
      type: "text",
      text: userQuery,
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const response = await fetch("/api/blinkit-assistant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: userQuery }),
      });

      if (!response.ok) throw new Error("Failed to process request");
      const resData = await response.json();

      if (resData.type === "chat") {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now().toString() + "_bot",
            sender: "bot",
            type: "chat",
            text: resData.message,
          },
        ]);
      } else if (resData.type === "recipe_cart") {
        // Initialize active selections: main items selected, staples unselected
        const initialItems = resData.data.map((item) => ({
          ...item,
          selected: !item.is_pantry_staple,
        }));

        setMessages((prev) => [
          ...prev,
          {
            id: Date.now().toString() + "_cart",
            sender: "bot",
            type: "recipe_cart",
            items: initialItems,
          },
        ]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString() + "_err",
          sender: "bot",
          type: "chat",
          text: "Sorry, I ran into an error processing that request. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const toggleItemSelection = (messageId, itemIdx) => {
    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== messageId) return msg;
        const newItems = [...msg.items];
        newItems[itemIdx] = {
          ...newItems[itemIdx],
          selected: !newItems[itemIdx].selected,
        };
        return { ...msg, items: newItems };
      })
    );
  };

  return (
    <div className="min-h-screen bg-[#F4F6F9] font-sans flex flex-col text-[#1C1C1C]">
      {/* Blinkit-Themed Header */}
      <header className="bg-white px-4 py-3 border-b border-gray-200 sticky top-0 z-20 flex justify-between items-center shadow-xs">
        <div>
          <div className="flex items-center gap-1.5">
            <span className="bg-[#F8CB46] text-[#1C1C1C] text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded">
              Blinkit AI
            </span>
            <h1 className="font-bold text-sm">Delivery in 8 minutes</h1>
          </div>
          <p className="text-xs text-gray-500">Smart Recipe & Inventory Assistant</p>
        </div>
      </header>

      {/* Conversation Thread */}
      <main className="flex-1 max-w-2xl w-full mx-auto p-4 space-y-4 overflow-y-auto pb-28">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-2.5 ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.sender === "bot" && (
              <div className="w-8 h-8 rounded-full bg-[#0C831F] text-white flex items-center justify-center shrink-0 mt-0.5">
                <Bot className="w-4 h-4" />
              </div>
            )}

            <div className="max-w-[88%] space-y-2">
              {/* Conversational Text Messages */}
              {msg.type === "chat" || msg.type === "text" ? (
                <div
                  className={`p-3.5 rounded-2xl text-sm leading-relaxed ${
                    msg.sender === "user"
                      ? "bg-[#0C831F] text-white rounded-br-xs"
                      : "bg-white text-gray-800 border border-gray-200 rounded-bl-xs shadow-xs"
                  }`}
                >
                  {msg.text}
                </div>
              ) : null}

              {/* Recipe Cart Cards Message */}
              {msg.type === "recipe_cart" && (
                <RecipeCartWidget
                  items={msg.items}
                  onToggleItem={(idx) => toggleItemSelection(msg.id, idx)}
                />
              )}
            </div>

            {msg.sender === "user" && (
              <div className="w-8 h-8 rounded-full bg-gray-200 text-gray-700 flex items-center justify-center shrink-0 mt-0.5">
                <User className="w-4 h-4" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-2.5 items-center text-xs text-gray-500 italic">
            <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#0C831F]" />
            Searching dark store catalog...
          </div>
        )}
      </main>

      {/* Chat Prompt Footer */}
      <footer className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-3 z-30">
        <form onSubmit={handleSend} className="max-w-2xl mx-auto flex items-center gap-2">
          <div className="relative flex-1">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g., 'Is heavy cream in stock?' or 'Paneer Butter Masala for 2'"
              className="w-full bg-gray-100 rounded-xl py-3 pl-4 pr-10 text-sm outline-none focus:ring-1 focus:ring-[#0C831F]"
            />
            <Sparkles className="w-4 h-4 text-amber-500 absolute right-3 top-3.5 pointer-events-none" />
          </div>
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="p-3 bg-[#0C831F] hover:bg-[#0a6b19] disabled:opacity-50 text-white rounded-xl transition-colors shrink-0"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </footer>
    </div>
  );
}

// Sub-component to render the interactive item tray
function RecipeCartWidget({ items, onToggleItem }) {
  const selectedCount = items.filter((i) => i.selected).length;
  const total = items
    .filter((i) => i.selected)
    .reduce((sum, i) => sum + (i.selected_sku?.price || 0), 0);

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-4 shadow-sm space-y-3">
      <div className="flex justify-between items-center pb-2 border-b border-gray-100">
        <span className="text-xs font-bold uppercase tracking-wider text-gray-600">
          Recipe Ingredients ({items.length})
        </span>
        <span className="text-xs text-gray-400">Pantry items deselected by default</span>
      </div>

      <div className="space-y-2">
        {items.map((item, idx) => (
          <div
            key={idx}
            onClick={() => onToggleItem(idx)}
            className={`p-3 rounded-xl border transition-all cursor-pointer select-none ${
              item.selected ? "bg-white border-gray-200 shadow-xs" : "bg-gray-50 border-gray-100 opacity-60"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-start gap-2.5">
                <input
                  type="checkbox"
                  checked={item.selected}
                  readOnly
                  className="mt-1 h-4 w-4 rounded border-gray-300 text-[#0C831F] accent-[#0C831F]"
                />
                <div>
                  <p className="text-xs font-semibold text-gray-500 capitalize">
                    {item.canonical_name} ({item.quantity})
                  </p>
                  <p className="text-sm font-medium text-gray-900">
                    {item.selected_sku?.name || "No direct SKU found"}
                  </p>
                </div>
              </div>
              <span className="text-sm font-bold text-gray-900 shrink-0">
                ₹{item.selected_sku?.price || 0}
              </span>
            </div>

            {/* Substitution Alert Tray */}
            {item.is_substituted && (
              <div className="mt-2.5 flex items-center gap-1.5 text-xs text-amber-800 bg-amber-50 px-2.5 py-1.5 rounded-lg border border-amber-200">
                <AlertCircle className="w-3.5 h-3.5 shrink-0 text-amber-600" />
                <span>
                  Replaced out of stock:{" "}
                  <span className="line-through opacity-70">
                    {item.original_sku?.name}
                  </span>
                </span>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Cart Total & Action */}
      <div className="pt-2 flex justify-between items-center">
        <div>
          <p className="text-[11px] text-gray-500">Selected total</p>
          <p className="text-base font-bold text-gray-900">₹{total}</p>
        </div>
        <button
          onClick={() => alert(`Added ${selectedCount} items to your cart!`)}
          disabled={selectedCount === 0}
          className="bg-[#0C831F] hover:bg-[#0a6b19] disabled:opacity-50 text-white text-xs font-bold uppercase tracking-wider py-2.5 px-4 rounded-xl flex items-center gap-2 shadow-xs transition-colors"
        >
          <ShoppingCart className="w-4 h-4" />
          Add ({selectedCount}) to Cart
        </button>
      </div>
    </div>
  );
}