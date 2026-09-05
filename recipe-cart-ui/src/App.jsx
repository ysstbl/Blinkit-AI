import React, { useState } from "react";
import { ShoppingCart, RefreshCw, AlertCircle } from "lucide-react";

export default function App() {
  const [prompt, setPrompt] = useState("Pasta Arrabiata for 2, low spice...");
  const [cart, setCart] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSearch = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/recipe-to-cart", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      
      if (!response.ok) throw new Error("Failed to fetch matches");
      const data = await response.json();
      setCart(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const calculateTotal = () => {
    return cart.reduce((total, item) => total + (item.selected_sku?.price || 0), 0);
  };

  return (
    <div className="min-h-screen bg-neutral-50 font-sans text-neutral-900 p-6 md:p-12">
      <div className="max-w-2xl mx-auto space-y-8">
        
        <header>
          <h1 className="text-2xl font-semibold tracking-tight">Recipe to Cart</h1>
          <p className="text-neutral-500 mt-1">Convert your recipe ideas into active grocery orders.</p>
        </header>

        <section className="bg-white p-2 rounded-xl border border-neutral-200 shadow-sm flex items-center">
          <input
            className="flex-1 p-3 outline-none bg-transparent placeholder:text-neutral-400"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="What are you cooking today?"
          />
          <button
            onClick={handleSearch}
            disabled={isLoading}
            className="bg-neutral-900 text-white px-6 py-3 rounded-lg font-medium hover:bg-neutral-800 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {isLoading && <RefreshCw className="w-4 h-4 animate-spin" />}
            Generate
          </button>
        </section>

        {error && <p className="text-red-500 text-sm">{error}</p>}

        {cart.length > 0 && (
          <div className="space-y-4">
            <h2 className="text-sm font-medium text-neutral-500 uppercase tracking-widest">Ingredients</h2>
            
            <div className="grid gap-3">
              {cart.map((item, idx) => (
                <div key={idx} className="bg-white p-4 rounded-xl border border-neutral-200 shadow-sm">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-sm text-neutral-500 mb-1 capitalize">{item.canonical_name} • {item.quantity}</p>
                      <p className="font-medium">{item.selected_sku?.name || "No item found"}</p>
                    </div>
                    <span className="font-semibold text-lg">
                      ₹{item.selected_sku?.price || 0}
                    </span>
                  </div>

                  {item.is_substituted && (
                    <div className="mt-3 flex items-center gap-2 text-xs font-medium text-amber-700 bg-amber-50 px-3 py-2 rounded-md border border-amber-100">
                      <AlertCircle className="w-4 h-4" />
                      <span>Replaced out-of-stock item: <span className="line-through text-amber-600/70">{item.original_sku?.name}</span></span>
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="flex justify-between items-center bg-white p-6 rounded-xl border border-neutral-200 shadow-sm mt-6">
              <div>
                <p className="text-sm text-neutral-500 font-medium">Estimated Total</p>
                <p className="text-2xl font-bold">₹{calculateTotal()}</p>
              </div>
              <button className="bg-emerald-600 hover:bg-emerald-700 text-white px-8 py-3 rounded-lg font-medium shadow-sm flex items-center gap-2 transition-colors">
                <ShoppingCart className="w-5 h-5" />
                Checkout
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}