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
  { name: 'Farmley Almonds', weight: '1 kg', price: 499, tag: 'Best Seller', accent: 'amber' },
  { name: 'Coca-Cola', weight: '600 ml', price: 92, tag: 'Cold', accent: 'red' },
  { name: 'Paneer', weight: '200 g', price: 110, tag: 'Fresh', accent: 'green' },
  { name: 'Strawberries', weight: '250 g', price: 178, tag: 'Seasonal', accent: 'pink' },
  { name: 'Brown Bread', weight: '400 g', price: 69, tag: 'Bakery', accent: 'gold' },
  { name: 'Mango', weight: '1 kg', price: 149, tag: 'Popular', accent: 'orange' },
  { name: 'Yogurt', weight: '400 g', price: 60, tag: 'Dairy', accent: 'sky' },
  { name: 'Potato Chips', weight: '150 g', price: 45, tag: 'Crunchy', accent: 'purple' },
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

export default function BlinkitReplicaApp() {
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
            <div className="search-box">
              <span className="search-icon">⌕</span>
              <span>Search for groceries</span>
            </div>
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
            <div className="mini-cart-pill">
              <span>🛒</span>
              <strong>₹ 1,264</strong>
            </div>
          </section>

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

          <section className="categories-section">
            {categories.map((category) => (
              <div key={category.name} className="category-item">
                <div className="category-icon">{category.emoji}</div>
                <span>{category.name}</span>
              </div>
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
              <span className="section-tag">Featured</span>
              <h2>Best sellers</h2>
            </div>
            <button type="button">See all</button>
          </section>

          <section className="product-grid">
            {products.map((product) => (
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
                  <button type="button">Add</button>
                </div>
              </article>
            ))}
          </section>
        </main>
      </div>
    </div>
  );
}
