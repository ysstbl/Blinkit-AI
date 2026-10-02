import { useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  ArrowUpRight,
  Bot,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Database,
  Gauge,
  GitBranch,
  Layers3,
  Radio,
  RefreshCw,
  Send,
  Server,
  ShoppingCart,
  Sparkles,
  TriangleAlert,
  User,
  X,
  Zap,
} from "lucide-react";
import BlinkitReplicaApp from "../blinkit-replica/App.jsx";

const apiBaseUrl = import.meta.env.VITE_API_URL || "";

function toCartProduct(item) {
  const sku = item.selected_sku;

  return {
    name: sku.name,
    weight: sku.pack_size,
    price: Number(sku.price),
    tag: item.is_substituted ? "Substitute" : "AI pick",
    category: sku.category,
    accent: "green",
  };
}

function getCurrentRoute() {
  if (window.location.pathname === "/cart") return "cart";
  if (window.location.pathname === "/dashboard") return "dashboard";
  if (window.location.pathname === "/assistant") return "main";
  return "blinkit";
}

export default function App() {
  const [route, setRoute] = useState(getCurrentRoute);
  const [input, setInput] = useState(() =>
    window.location.pathname === "/assistant"
      ? new URLSearchParams(window.location.search).get("prompt") || ""
      : ""
  );
  const [isSuggestedPrompt, setIsSuggestedPrompt] = useState(() =>
    window.location.pathname === "/assistant" &&
    Boolean(new URLSearchParams(window.location.search).get("prompt"))
  );
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      sender: "bot",
      type: "chat",
      text: "Hi! I'm your Blinkit AI assistant. You can ask if an item is in stock (e.g. 'Is paneer available?') or tell me what you'd like to cook!",
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [cartItems, setCartItems] = useState([]);

  useEffect(() => {
    const onPopState = () => setRoute(getCurrentRoute());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = (path) => {
    window.history.pushState({}, "", path);
    setRoute(
      path === "/assistant"
        ? "main"
        : path === "/cart"
          ? "cart"
          : path === "/dashboard"
            ? "dashboard"
            : "blinkit"
    );
  };

  if (route === "dashboard") return <ObservabilityDashboard onNavigate={navigate} />;

  if (route === "blinkit" || route === "cart") {
    return (
      <BlinkitReplicaApp
        showCart={route === "cart"}
        cartItems={cartItems}
        onAddToCart={(product) => setCartItems((currentCart) => [...currentCart, product])}
        onRemoveFromCart={(itemIndex) =>
          setCartItems((currentCart) => currentCart.filter((_, index) => index !== itemIndex))
        }
      />
    );
  }

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
      const response = await fetch(`${apiBaseUrl}/api/blinkit-assistant`, {
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
      } else if (resData.type === "checklist") {
        // Keep every result staged until the shopper submits the checklist.
        const initialItems = resData.data.map((item) => ({
          ...item,
          selected: Boolean(item.selected_sku) && !item.is_substituted && !item.is_pantry_staple,
        }));

        setMessages((prev) => [
          ...prev,
          {
            id: Date.now().toString() + "_cart",
            sender: "bot",
            type: "checklist",
            text: resData.message,
            items: initialItems,
          },
        ]);
      }
    } catch {
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

  const addSelectedToCart = (messageId) => {
    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== messageId) return msg;

        const selectedItems = msg.items
          .filter((item) => item.selected && item.selected_sku)
          .map(toCartProduct);
        setCartItems((currentCart) => [...currentCart, ...selectedItems]);

        return { ...msg, items: msg.items.filter((item) => !item.selected) };
      })
    );
  };

  const removeFromCart = (itemIndex) => {
    setCartItems((currentCart) => currentCart.filter((_, index) => index !== itemIndex));
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
    <>
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
        <div className="flex items-center gap-1.5 text-xs font-bold text-gray-700">
          <ShoppingCart className="w-4 h-4 text-[#0C831F]" />
          {cartItems.length} in cart
        </div>
      </header>
      <div className="flex justify-end px-4 pt-3">
        <button
          type="button"
          onClick={() => navigate("/blinkit")}
          className="bg-[#0C831F] text-white text-xs font-bold px-3 py-2 rounded-full shadow-sm"
        >
          Go to storefront
        </button>
      </div>

      {cartItems.length > 0 && (
        <section className="max-w-2xl w-full mx-auto px-4 pt-3">
          <div className="bg-white border border-gray-200 rounded-2xl p-3 shadow-xs">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-bold uppercase tracking-wider text-gray-600">Your cart</p>
              <p className="text-xs text-gray-500">{cartItems.length} item{cartItems.length === 1 ? "" : "s"}</p>
            </div>
            <div className="space-y-1.5">
              {cartItems.map((item, index) => (
                <div key={`${item.name}-${index}`} className="flex items-center justify-between text-sm">
                  <span className="text-gray-800">{item.name}</span>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">₹{item.price}</span>
                    <button
                      type="button"
                      onClick={() => removeFromCart(index)}
                      aria-label={`Remove ${item.name} from cart`}
                      className="p-1 text-gray-400 hover:text-red-600"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

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

              {msg.type === "checklist" && (
                <>
                  <div className="bg-white text-gray-800 border border-gray-200 rounded-2xl rounded-bl-xs p-3.5 text-sm leading-relaxed shadow-xs">
                    {msg.text}
                  </div>
                  <RecipeCartWidget
                    items={msg.items}
                    onToggleItem={(idx) => toggleItemSelection(msg.id, idx)}
                    onAddToCart={() => addSelectedToCart(msg.id)}
                  />
                </>
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
              onChange={(e) => {
                setInput(e.target.value);
                setIsSuggestedPrompt(false);
              }}
              placeholder="e.g., 'Is heavy cream in stock?' or 'Paneer Butter Masala for 2'"
              className={`w-full rounded-xl py-3 pl-4 pr-10 text-sm outline-none transition-colors transition-shadow duration-300 focus:ring-1 focus:ring-[#0C831F] ${
                isSuggestedPrompt
                  ? "bg-emerald-50 text-emerald-900 font-medium ring-2 ring-emerald-200"
                  : "bg-gray-100 text-gray-900 font-normal"
              }`}
            />
            <Sparkles
              className={`w-4 h-4 absolute right-3 top-3.5 pointer-events-none transition-colors duration-300 ${
                isSuggestedPrompt ? "text-[#0C831F]" : "text-amber-500"
              }`}
            />
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
    </>
  );
}

// Sub-component to render the interactive item tray
function RecipeCartWidget({ items, onToggleItem, onAddToCart }) {
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
          <span className="text-xs text-gray-400">Review before adding</span>
      </div>

      <div className="space-y-2">
        {items.map((item, idx) => (
          (() => {
            const suggestedSku = item.selected_sku || item.raw_matches?.[0];
            const hasUnavailableSuggestion = !item.selected_sku && Boolean(suggestedSku);

            return (
          <div
            key={idx}
            onClick={() => !hasUnavailableSuggestion && onToggleItem(idx)}
            className={`p-3 rounded-xl border transition-all cursor-pointer select-none ${
              item.selected ? "bg-white border-gray-200 shadow-xs" : "bg-gray-50 border-gray-100 opacity-60"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-start gap-2.5">
                <input
                  type="checkbox"
                  checked={item.selected}
                  disabled={hasUnavailableSuggestion}
                  readOnly
                  className="mt-1 h-4 w-4 rounded border-gray-300 text-[#0C831F] accent-[#0C831F]"
                />
                <div>
                  <p className="text-xs font-semibold text-gray-500 capitalize">
                    {item.canonical_name} ({item.quantity})
                  </p>
                  <p className="text-sm font-medium text-gray-900">
                    {suggestedSku?.name || "We could not find a suitable catalog option yet"}
                  </p>
                  {hasUnavailableSuggestion && (
                    <p className="text-xs text-amber-700 mt-1">
                      Suggested alternative, currently unavailable
                    </p>
                  )}
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
                  {item.substitution_reason || "Suggested substitute:"}{" "}
                  <span className="line-through opacity-70">
                    {item.original_sku?.name}
                  </span>
                </span>
              </div>
            )}
          </div>
            );
          })()
        ))}
      </div>

      {/* Cart Total & Action */}
      <div className="pt-2 flex justify-between items-center">
        <div>
          <p className="text-[11px] text-gray-500">Selected total</p>
          <p className="text-base font-bold text-gray-900">₹{total}</p>
        </div>
        <button
          onClick={onAddToCart}
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

const dashboardRanges = ["15m", "1h", "24h", "7d"];

const dashboardData = {
  "15m": {
    requests: "1,284",
    requestChange: "+8.2%",
    p50: "284 ms",
    p95: "742 ms",
    p99: "1.84 s",
    errorRate: "1.8%",
    gemini: "612 ms",
    huggingFace: "188 ms",
    postgres: "42 ms",
    recipe: "496 ms",
    chart: [34, 39, 36, 44, 42, 54, 48, 52, 46, 61, 57, 65, 58, 69, 64, 72],
  },
  "1h": {
    requests: "5,906",
    requestChange: "+4.7%",
    p50: "301 ms",
    p95: "781 ms",
    p99: "1.92 s",
    errorRate: "2.1%",
    gemini: "648 ms",
    huggingFace: "201 ms",
    postgres: "47 ms",
    recipe: "518 ms",
    chart: [31, 35, 40, 37, 44, 47, 43, 51, 55, 52, 58, 61, 56, 63, 68, 64],
  },
  "24h": {
    requests: "42,812",
    requestChange: "+12.4%",
    p50: "296 ms",
    p95: "768 ms",
    p99: "1.88 s",
    errorRate: "2.4%",
    gemini: "631 ms",
    huggingFace: "196 ms",
    postgres: "45 ms",
    recipe: "507 ms",
    chart: [28, 33, 30, 41, 38, 47, 45, 53, 49, 58, 55, 63, 60, 67, 64, 71],
  },
  "7d": {
    requests: "286,440",
    requestChange: "+16.8%",
    p50: "312 ms",
    p95: "804 ms",
    p99: "2.06 s",
    errorRate: "2.7%",
    gemini: "679 ms",
    huggingFace: "214 ms",
    postgres: "51 ms",
    recipe: "534 ms",
    chart: [35, 29, 38, 42, 39, 48, 44, 55, 52, 58, 54, 65, 61, 69, 66, 74],
  },
};

function MetricSparkline({ points, color = "#176b5b" }) {
  const max = Math.max(...points);
  const min = Math.min(...points);
  const coordinates = points
    .map((point, index) => {
      const x = (index / (points.length - 1)) * 180;
      const y = 42 - ((point - min) / Math.max(max - min, 1)) * 30;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg className="metric-sparkline" viewBox="0 0 180 48" role="img" aria-label="Metric trend">
      <polyline points={coordinates} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ObservabilityDashboard({ onNavigate }) {
  const [range, setRange] = useState("24h");
  const data = dashboardData[range];

  return (
    <div className="observability-shell">
      <header className="observability-header">
        <div className="observability-brand">
          <div className="brand-mark"><Activity size={18} /></div>
          <div>
            <p className="eyebrow">Blinkit AI / Observability</p>
            <h1>System pulse</h1>
          </div>
        </div>
        <div className="observability-actions">
          <span className="live-indicator"><span /> Live data</span>
          <button className="dashboard-button dashboard-button-secondary" type="button" onClick={() => onNavigate("/blinkit")}>
            <ShoppingCart size={15} /> Storefront
          </button>
          <button className="dashboard-button dashboard-button-primary" type="button" onClick={() => onNavigate("/assistant")}>
            Open assistant <ArrowUpRight size={15} />
          </button>
        </div>
      </header>

      <main className="observability-content">
        <section className="dashboard-intro">
          <div>
            <p className="eyebrow">Friday, October 2, 2026</p>
            <h2>Everything is moving.</h2>
            <p className="dashboard-subtitle">A clear read on requests, model calls, and recipe generation.</p>
          </div>
          <div className="range-control" role="group" aria-label="Time range">
            {dashboardRanges.map((option) => (
              <button key={option} type="button" className={range === option ? "active" : ""} onClick={() => setRange(option)}>
                {option}
              </button>
            ))}
            <button type="button" className="range-calendar" aria-label="Select custom date range"><ChevronDown size={15} /></button>
          </div>
        </section>

        <section className="metric-card-grid" aria-label="Key metrics">
          <MetricCard icon={<Gauge size={17} />} label="API p95 latency" value={data.p95} detail={`p50 ${data.p50} / p99 ${data.p99}`} trend="+3.1%" tone="green" sparkline={data.chart} />
          <MetricCard icon={<Zap size={17} />} label="Gemini latency" value={data.gemini} detail="generation span" trend="-6.4%" tone="amber" sparkline={data.chart.map((point) => point - 7)} />
          <MetricCard icon={<Layers3 size={17} />} label="Hugging Face latency" value={data.huggingFace} detail="embedding span" trend="-2.8%" tone="blue" sparkline={data.chart.map((point) => point - 14)} />
          <MetricCard icon={<Database size={17} />} label="PostgreSQL query" value={data.postgres} detail="average duration" trend="+1.4%" tone="slate" sparkline={data.chart.map((point) => point - 22)} />
        </section>

        <section className="dashboard-grid dashboard-grid-main">
          <article className="panel latency-panel">
            <PanelHeading icon={<Activity size={16} />} title="API latency" meta="milliseconds" action="View traces" />
            <div className="latency-summary"><strong>{data.p95}</strong><span>p95 request duration</span><span className="positive">{data.requestChange} volume</span></div>
            <div className="large-chart">
              <div className="chart-y-labels"><span>2s</span><span>1s</span><span>500ms</span><span>0</span></div>
              <div className="chart-area">
                <div className="chart-grid-lines"><i /><i /><i /><i /></div>
                <MetricSparkline points={data.chart} color="#176b5b" />
                <div className="chart-x-labels"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>Now</span></div>
              </div>
            </div>
            <div className="legend-row"><span><i className="legend-dot green" /> p50 <strong>{data.p50}</strong></span><span><i className="legend-dot gold" /> p95 <strong>{data.p95}</strong></span><span><i className="legend-dot coral" /> p99 <strong>{data.p99}</strong></span></div>
          </article>

          <article className="panel health-panel">
            <PanelHeading icon={<Radio size={16} />} title="Request health" meta="by intent" action="Inspect errors" />
            <div className="health-rate"><strong>{data.errorRate}</strong><span>error rate</span><span className="negative"><TriangleAlert size={13} /> +0.3%</span></div>
            <div className="intent-list">
              <IntentRow label="Recipe extraction" value="1.1%" width="38%" color="green" />
              <IntentRow label="Inventory query" value="0.6%" width="22%" color="gold" />
              <IntentRow label="Catalog query" value="3.8%" width="68%" color="coral" />
              <IntentRow label="General chat" value="0.2%" width="12%" color="blue" />
            </div>
            <div className="health-footer"><span><CheckCircle2 size={14} /> 97.6% successful requests</span><strong>{data.requests} requests</strong></div>
          </article>
        </section>

        <section className="dashboard-grid dashboard-grid-secondary">
          <article className="panel provider-panel">
            <PanelHeading icon={<Server size={16} />} title="Dependency latency" meta="average duration" action="Open spans" />
            <ProviderRow label="Gemini" detail="gemini-3.1-flash-lite" value={data.gemini} width="82%" color="gold" />
            <ProviderRow label="Hugging Face" detail="all-MiniLM-L6-v2" value={data.huggingFace} width="32%" color="blue" />
            <ProviderRow label="PostgreSQL" detail="pgvector / catalog" value={data.postgres} width="16%" color="green" />
          </article>
          <article className="panel recipe-panel">
            <PanelHeading icon={<GitBranch size={16} />} title="Recipe complexity" meta="latency versus ingredients" action="Explore" />
            <div className="recipe-stat"><strong>{data.recipe}</strong><span>average recipe latency</span><span className="positive">-4.2%</span></div>
            <div className="scatter-chart">
              {[{ x: 10, y: 67 }, { x: 24, y: 58 }, { x: 37, y: 54 }, { x: 51, y: 42 }, { x: 65, y: 36 }, { x: 77, y: 28 }, { x: 91, y: 20 }].map((point) => <i key={`${point.x}-${point.y}`} style={{ left: `${point.x}%`, bottom: `${point.y}%` }} />)}
              <span className="axis-y">latency</span><span className="axis-x">ingredient count</span>
            </div>
          </article>
        </section>

        <section className="panel traces-panel">
          <PanelHeading icon={<Clock3 size={16} />} title="Recent traces" meta="latest request activity" action="See all traces" />
          <div className="trace-table-wrap"><table className="trace-table"><thead><tr><th>Trace</th><th>Intent</th><th>Route</th><th>Duration</th><th>Database</th><th>Status</th></tr></thead><tbody>
            <TraceRow id="tr_9f83a1" intent="Recipe extraction" route="POST /api/blinkit-assistant" duration="438 ms" database="34 ms" status="200" />
            <TraceRow id="tr_9f82dd" intent="Catalog query" route="POST /api/blinkit-assistant" duration="1.12 s" database="86 ms" status="500" error />
            <TraceRow id="tr_9f8210" intent="Inventory query" route="POST /api/blinkit-assistant" duration="291 ms" database="28 ms" status="200" />
          </tbody></table></div>
        </section>
      </main>
    </div>
  );
}

function MetricCard({ icon, label, value, detail, trend, tone, sparkline }) {
  return <article className={`metric-card tone-${tone}`}><div className="metric-card-top"><span className="metric-icon">{icon}</span><span className={trend.startsWith("-") ? "positive" : "negative"}>{trend}</span></div><p>{label}</p><strong>{value}</strong><div className="metric-card-bottom"><span>{detail}</span><MetricSparkline points={sparkline} color="currentColor" /></div></article>;
}

function PanelHeading({ icon, title, meta, action }) {
  return <div className="panel-heading"><div className="panel-title"><span>{icon}</span><div><h3>{title}</h3><p>{meta}</p></div></div><button type="button">{action}<ArrowUpRight size={14} /></button></div>;
}

function IntentRow({ label, value, width, color }) {
  return <div className="intent-row"><div><span>{label}</span><strong>{value}</strong></div><div className="intent-track"><i className={color} style={{ width }} /></div></div>;
}

function ProviderRow({ label, detail, value, width, color }) {
  return <div className="provider-row"><div className="provider-label"><strong>{label}</strong><span>{detail}</span></div><div className="provider-track"><i className={color} style={{ width }} /></div><strong className="provider-value">{value}</strong></div>;
}

function TraceRow({ id, intent, route, duration, database, status, error }) {
  return <tr><td><span className="trace-id"><span className={`trace-status ${error ? "error" : ""}`} />{id}</span></td><td>{intent}</td><td className="route-cell">{route}</td><td>{duration}</td><td>{database}</td><td><span className={`status-pill ${error ? "status-error" : "status-ok"}`}>{status}</span></td></tr>;
}