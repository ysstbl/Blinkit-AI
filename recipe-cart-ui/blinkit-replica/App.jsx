import { useState } from 'react';
import { Sparkles } from 'lucide-react';
import './blinkitReplica.css';

const categories = [
  { name: 'Vegetables & Fruits', emoji: '🥬' },
  { name: 'Dairy & Breakfast', emoji: '🥛' },
  { name: 'Munchies', emoji: '🍟' },
  { name: 'Cold Drinks', emoji: '🥤' },
  { name: 'Instant Food', emoji: '🍲' },
  { name: 'Bakery', emoji: '🥐' },
  { name: 'Tea & Coffee', emoji: '☕' },
  { name: 'Grocery', emoji: '🛒' },
];

const deals = [
  { title: 'Up to 60% OFF', subtitle: 'On breakfast essentials', accent: 'yellow' },
  { title: 'Flat 20% OFF', subtitle: 'On fresh veggies', accent: 'green' },
  { title: 'Free delivery', subtitle: 'On orders above ₹199', accent: 'orange' },
];

const products = [
  { name: 'Farmley Almonds', weight: '1 kg', price: 499, tag: 'Best Seller', category: 'Grocery', accent: 'amber' },
  { name: 'Coca-Cola', weight: '600 ml', price: 92, tag: 'Cold', category: 'Cold Drinks', accent: 'red' },
  { name: 'Paneer', weight: '200 g', price: 110, tag: 'Fresh', category: 'Dairy & Breakfast', accent: 'green' },
  { name: 'Strawberries', weight: '250 g', price: 178, tag: 'Seasonal', category: 'Vegetables & Fruits', accent: 'pink' },
  { name: 'Brown Bread', weight: '400 g', price: 69, tag: 'Bakery', category: 'Bakery', accent: 'gold' },
  { name: 'Mango', weight: '1 kg', price: 149, tag: 'Popular', category: 'Vegetables & Fruits', accent: 'orange' },
  { name: 'Yogurt', weight: '400 g', price: 60, tag: 'Dairy', category: 'Dairy & Breakfast', accent: 'sky' },
  { name: 'Potato Chips', weight: '150 g', price: 45, tag: 'Crunchy', category: 'Munchies', accent: 'purple' },
];

function getProductEmoji(name) {
  if (name.startsWith('Coca')) return '🥤';
  if (name.startsWith('Paneer')) return '🧀';
  if (name.startsWith('Farmley')) return '🥜';
  if (name.startsWith('Strawberries')) return '🍓';
  if (name.startsWith('Brown')) return '🍞';
  if (name.startsWith('Mango')) return '🥭';
  if (name.startsWith('Yogurt')) return '🥣';
  return '🍟';
}

export default function BlinkitReplicaApp({
  showCart = false,
  cartItems = [],
  onAddToCart,
  onRemoveFromCart,
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState('All');
  const [lastAdded, setLastAdded] = useState('');

  const visibleProducts = products.filter((product) => {
    const matchesCategory = activeCategory === 'All' || product.category === activeCategory;
    const matchesSearch = product.name.toLowerCase().includes(searchQuery.toLowerCase().trim());
    return matchesCategory && matchesSearch;
  });

  const cartTotal = cartItems.reduce((total, product) => total + product.price, 0);

  const addToCart = (product) => {
    onAddToCart(product);
    setLastAdded(product.name);
    window.setTimeout(() => setLastAdded(''), 1800);
  };

  const resetFilters = () => {
    setSearchQuery('');
    setActiveCategory('All');
  };

  const navigateTo = (path) => {
    window.history.pushState({}, '', path);
    window.dispatchEvent(new PopStateEvent('popstate'));
  };

  return (
    <div className="blinkit-replica-shell">
      <div className="blinkit-app">
        <header className="blinkit-header">
          <div className="brand-block">
            <div className="blinkit-logo">Blinkit</div>
            <div className="delivery-block">
              <span className="delivery-label">Delivery in</span>
              <strong>8 minutes</strong>
            </div>
          </div>

          <div className="header-actions">
            <label className="search-box">
              <span className="search-icon">⌕</span>
              <input
                type="search"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search for groceries"
                aria-label="Search for groceries"
              />
              {searchQuery && (
                <button type="button" className="clear-search" onClick={() => setSearchQuery('')} aria-label="Clear search">
                  x
                </button>
              )}
            </label>
            <button type="button" className="profile-button">Login</button>
          </div>
        </header>

        <main className="blinkit-main">
          <section className="top-strip">
            <div className="location-pill">
              <span className="location-dot" />
              <div>
                <small>Delivering to</small>
                <strong>Sector 62, Noida</strong>
              </div>
            </div>
            <button type="button" className="mini-cart-pill" onClick={() => navigateTo('/cart')}>
              <span>🛒</span>
              <strong>{cartItems.length ? `${cartItems.length} item${cartItems.length === 1 ? '' : 's'} · ₹${cartTotal}` : 'Your cart'}</strong>
            </button>
          </section>

          {showCart ? (
            <CartView items={cartItems} cartTotal={cartTotal} onRemove={onRemoveFromCart} onContinue={() => navigateTo('/blinkit')} />
          ) : (
            <>
          <section className="hero-banner">
            <div className="hero-copy">
              <span className="eyebrow">Fresh picks</span>
              <h1>Summer staples, delivered fast</h1>
              <p>Stock up on produce, snacks, and essentials from your nearby store.</p>
            </div>
            <div className="hero-visual" aria-hidden="true">
              <div className="produce-card produce-1">🥬</div>
              <div className="produce-card produce-2">🍋</div>
              <div className="produce-card produce-3">🍉</div>
            </div>
          </section>

          <section className="ai-assistant-banner" aria-labelledby="ai-assistant-title">
            <div className="ai-assistant-copy">
              <span className="ai-assistant-eyebrow">Blinkit AI</span>
              <h2 id="ai-assistant-title">Not sure what to buy?</h2>
              <p>Tell our AI what you want to cook and get a ready-to-review checklist.</p>
            </div>
            <button
              type="button"
              className="ai-assistant-button"
              onClick={() => window.location.assign('/assistant')}
            >
              Ask AI <span aria-hidden="true">-&gt;</span>
            </button>
          </section>

          <section className="categories-section" aria-label="Browse categories">
            <button
              type="button"
              className={`category-item ${activeCategory === 'All' ? 'active' : ''}`}
              onClick={() => setActiveCategory('All')}
            >
              <div className="category-icon">✦</div>
              <span>All picks</span>
            </button>
            {categories.map((category) => (
              <button
                type="button"
                key={category.name}
                className={`category-item ${activeCategory === category.name ? 'active' : ''}`}
                onClick={() => setActiveCategory(category.name)}
              >
                <div className="category-icon">{category.emoji}</div>
                <span>{category.name}</span>
              </button>
            ))}
          </section>

          <section className="deal-strip">
            {deals.map((deal) => (
              <div key={deal.title} className={`deal-card ${deal.accent}`}>
                <strong>{deal.title}</strong>
                <span>{deal.subtitle}</span>
              </div>
            ))}
          </section>

          <section className="section-header">
            <div>
              <span className="section-tag">{activeCategory === 'All' ? 'Featured' : 'Browsing'}</span>
              <h2>{activeCategory === 'All' ? 'Best sellers' : activeCategory}</h2>
            </div>
            <button type="button" onClick={resetFilters}>See all</button>
          </section>

          <section className="product-grid">
            {visibleProducts.map((product) => (
              <article key={product.name} className="product-card">
                <div className={`product-art ${product.accent}`}>
                  <span>{getProductEmoji(product.name)}</span>
                </div>
                <div className="product-meta">
                  <span className="product-tag">{product.tag}</span>
                  <h3>{product.name}</h3>
                  <p>{product.weight}</p>
                </div>

                <div className="price-row">
                  <strong>₹{product.price}</strong>
                  <div className="product-actions">
                    <button
                      type="button"
                      className="ask-ai-product-button"
                      aria-label={`Ask AI what you can make with ${product.name}`}
                      title={`What can I make with ${product.name}?`}
                      onClick={() => window.location.assign(`/assistant?prompt=${encodeURIComponent(`What can I make with ${product.name}`)}`)}
                    >
                      <Sparkles aria-hidden="true" />
                      <span>Ask AI</span>
                    </button>
                    <button type="button" onClick={() => addToCart(product)}>Add</button>
                  </div>
                </div>
              </article>
            ))}
            {!visibleProducts.length && (
              <div className="empty-state">
                <span className="empty-state-icon">⌕</span>
                <strong>No matching picks yet</strong>
                <p>Try another search or browse all products.</p>
                <button type="button" onClick={resetFilters}>Show all products</button>
              </div>
            )}
          </section>
            </>
          )}
        </main>
      </div>
      {lastAdded && <div className="toast" role="status">Added {lastAdded} to your cart</div>}
    </div>
  );
}

function CartView({ items, cartTotal, onRemove, onContinue }) {
  return (
    <section className="cart-view" aria-labelledby="cart-title">
      <div className="cart-view-header">
        <div>
          <span className="section-tag">Ready when you are</span>
          <h1 id="cart-title">Your cart</h1>
        </div>
        <button type="button" className="continue-shopping" onClick={onContinue}>Continue shopping</button>
      </div>

      {items.length ? (
        <>
          <div className="cart-list">
            {items.map((item, index) => (
              <article className="cart-row" key={`${item.name}-${index}`}>
                <div className={`cart-row-art ${item.accent}`}>{getProductEmoji(item.name)}</div>
                <div className="cart-row-details">
                  <strong>{item.name}</strong>
                  <span>{item.weight} · {item.tag}</span>
                </div>
                <strong className="cart-row-price">₹{item.price}</strong>
                <button type="button" className="remove-cart-item" onClick={() => onRemove(index)} aria-label={`Remove ${item.name}`}>
                  x
                </button>
              </article>
            ))}
          </div>
          <div className="cart-summary">
            <div>
              <span>Subtotal</span>
              <strong>₹{cartTotal}</strong>
            </div>
            <button type="button" className="checkout-button">Proceed to checkout <span aria-hidden="true">-&gt;</span></button>
          </div>
        </>
      ) : (
        <div className="cart-empty-state">
          <span className="cart-empty-icon">🛒</span>
          <h2>Your cart is waiting</h2>
          <p>Add a few fresh picks and they will appear here.</p>
          <button type="button" className="checkout-button" onClick={onContinue}>Browse products</button>
        </div>
      )}
    </section>
  );
}
