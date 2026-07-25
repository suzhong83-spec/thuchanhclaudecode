const CART_KEY = 'coffeeshop_cart';

/* ===== Cart storage ===== */
function getCart() {
  try {
    const raw = JSON.parse(localStorage.getItem(CART_KEY));
    return Array.isArray(raw) ? raw : [];
  } catch (err) {
    return [];
  }
}

function saveCart(cart) {
  localStorage.setItem(CART_KEY, JSON.stringify(cart));
  updateCartBadge();
}

function addToCart(product, quantity) {
  quantity = Math.max(1, Number(quantity) || 1);
  const cart = getCart();
  const existing = cart.find((i) => String(i.id) === String(product.id));
  if (existing) {
    existing.quantity += quantity;
  } else {
    cart.push({
      id: product.id,
      name: product.name,
      price: Number(product.price),
      image: product.image,
      quantity,
    });
  }
  saveCart(cart);
  renderCartDrawer();
  openCartDrawer();
}

function updateCartItemQty(productId, quantity) {
  let cart = getCart();
  quantity = Number(quantity);
  if (quantity <= 0) {
    cart = cart.filter((i) => String(i.id) !== String(productId));
  } else {
    const item = cart.find((i) => String(i.id) === String(productId));
    if (item) item.quantity = quantity;
  }
  saveCart(cart);
  renderCartDrawer();
}

function removeFromCart(productId) {
  updateCartItemQty(productId, 0);
}

function cartCount() {
  return getCart().reduce((sum, i) => sum + i.quantity, 0);
}

function cartTotal() {
  return getCart().reduce((sum, i) => sum + i.quantity * i.price, 0);
}

function updateCartBadge() {
  const count = cartCount();
  document.querySelectorAll('.cart-badge').forEach((el) => {
    el.textContent = count;
    el.classList.toggle('show', count > 0);
  });
}

/* ===== Drawer shell ===== */
function ensureCartDrawer() {
  let overlay = document.querySelector('.cart-drawer-overlay');
  if (overlay) return overlay;

  overlay = document.createElement('div');
  overlay.className = 'cart-drawer-overlay';
  overlay.innerHTML = `
    <div class="cart-drawer">
      <div class="cart-drawer-header">
        <h3 class="cart-drawer-title">Giỏ hàng của bạn</h3>
        <button type="button" class="cart-drawer-close" aria-label="Đóng">&times;</button>
      </div>
      <div class="cart-drawer-body"></div>
      <div class="cart-drawer-footer"></div>
    </div>`;
  document.body.appendChild(overlay);

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay || e.target.classList.contains('cart-drawer-close')) {
      closeCartDrawer();
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeCartDrawer();
  });

  document.querySelectorAll('.cart-toggle').forEach((btn) => {
    btn.addEventListener('click', () => {
      renderCartDrawer();
      openCartDrawer();
    });
  });

  return overlay;
}

function openCartDrawer() {
  ensureCartDrawer().classList.add('open');
}

function closeCartDrawer() {
  document.querySelector('.cart-drawer-overlay')?.classList.remove('open');
}

/* ===== Cart view ===== */
function renderCartDrawer() {
  const overlay = ensureCartDrawer();
  const body = overlay.querySelector('.cart-drawer-body');
  const footer = overlay.querySelector('.cart-drawer-footer');
  const cart = getCart();

  if (!cart.length) {
    body.innerHTML = `<p class="cart-empty">Giỏ hàng của bạn đang trống.<br>Hãy chọn vài món thức uống yêu thích nhé!</p>`;
    footer.innerHTML = '';
    return;
  }

  body.innerHTML = cart
    .map(
      (item) => `
      <div class="cart-item" data-id="${item.id}">
        <img src="${resolveImage(item.image)}" alt="${item.name}">
        <div class="cart-item-info">
          <div class="cart-item-name">${item.name}</div>
          <div class="cart-item-price">${formatPrice(item.price)}</div>
        </div>
        <div class="qty-stepper">
          <button type="button" class="qty-btn" data-action="dec" aria-label="Giảm">−</button>
          <span>${item.quantity}</span>
          <button type="button" class="qty-btn" data-action="inc" aria-label="Tăng">+</button>
        </div>
        <button type="button" class="cart-item-remove" aria-label="Xóa">🗑</button>
      </div>`
    )
    .join('');

  footer.innerHTML = `
    <div class="cart-total-row">
      <span>Tổng cộng</span>
      <strong>${formatPrice(cartTotal())}</strong>
    </div>
    <button type="button" class="btn cart-checkout-btn">Tiến hành đặt hàng</button>`;

  body.querySelectorAll('.cart-item').forEach((el) => {
    const id = el.dataset.id;
    el.querySelector('[data-action="inc"]').addEventListener('click', () => {
      const item = cart.find((i) => String(i.id) === id);
      if (item) updateCartItemQty(id, item.quantity + 1);
    });
    el.querySelector('[data-action="dec"]').addEventListener('click', () => {
      const item = cart.find((i) => String(i.id) === id);
      if (item) updateCartItemQty(id, item.quantity - 1);
    });
    el.querySelector('.cart-item-remove').addEventListener('click', () => removeFromCart(id));
  });

  footer.querySelector('.cart-checkout-btn').addEventListener('click', renderCheckoutForm);
}

/* ===== Checkout view ===== */
function renderCheckoutForm() {
  const overlay = ensureCartDrawer();
  const body = overlay.querySelector('.cart-drawer-body');
  const footer = overlay.querySelector('.cart-drawer-footer');
  const cart = getCart();

  body.innerHTML = `
    <form class="checkout-form" id="checkout-form" novalidate>
      <div class="form-group">
        <label for="checkout-name">Họ tên *</label>
        <input type="text" id="checkout-name" name="name" required>
        <div class="form-error" data-error-for="name"></div>
      </div>
      <div class="form-group">
        <label for="checkout-phone">Số điện thoại *</label>
        <input type="tel" id="checkout-phone" name="phone" required>
        <div class="form-error" data-error-for="phone"></div>
      </div>
      <div class="form-group">
        <label for="checkout-email">Email</label>
        <input type="email" id="checkout-email" name="email">
        <div class="form-error" data-error-for="email"></div>
      </div>
      <div class="form-group">
        <label for="checkout-note">Ghi chú</label>
        <textarea id="checkout-note" name="note" rows="3" placeholder="Ví dụ: giao trước 18h, ít đá..."></textarea>
      </div>
    </form>
    <div class="checkout-summary">
      ${cart
        .map(
          (i) => `
        <div class="checkout-summary-row">
          <span>${i.name} × ${i.quantity}</span>
          <span>${formatPrice(i.price * i.quantity)}</span>
        </div>`
        )
        .join('')}
    </div>`;

  footer.innerHTML = `
    <div class="cart-total-row">
      <span>Tổng cộng</span>
      <strong>${formatPrice(cartTotal())}</strong>
    </div>
    <div class="checkout-actions">
      <button type="button" class="btn-secondary-cart cart-back-btn">← Quay lại giỏ hàng</button>
      <button type="submit" form="checkout-form" class="btn cart-submit-btn">Đặt hàng</button>
    </div>`;

  footer.querySelector('.cart-back-btn').addEventListener('click', renderCartDrawer);

  const form = body.querySelector('#checkout-form');
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    submitOrder(form);
  });
}

async function submitOrder(form) {
  const name = form.name.value.trim();
  const phone = form.phone.value.trim();
  const email = form.email.value.trim();
  const note = form.note.value.trim();

  const setError = (field, msg) => {
    const el = form.querySelector(`[data-error-for="${field}"]`);
    if (el) el.textContent = msg || '';
  };

  let valid = true;
  if (!name) {
    setError('name', 'Vui lòng nhập họ tên.');
    valid = false;
  } else {
    setError('name', '');
  }

  const phonePattern = /^[0-9]{9,11}$/;
  if (!phonePattern.test(phone)) {
    setError('phone', 'Số điện thoại không hợp lệ (9-11 chữ số).');
    valid = false;
  } else {
    setError('phone', '');
  }

  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (email && !emailPattern.test(email)) {
    setError('email', 'Email không hợp lệ.');
    valid = false;
  } else {
    setError('email', '');
  }

  if (!valid) return;

  const payload = {
    customer_name: name,
    customer_phone: phone,
    customer_email: email,
    note,
    items: getCart().map((i) => ({ product_id: i.id, quantity: i.quantity })),
  };

  const submitBtn = document.querySelector('.cart-submit-btn');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Đang xử lý...';
  }

  try {
    const res = await fetch('/api/orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (res.ok) {
      localStorage.removeItem(CART_KEY);
      updateCartBadge();
      renderOrderSuccess(data.order_id);
    } else {
      alert(data.error || 'Đã có lỗi xảy ra, vui lòng thử lại.');
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Đặt hàng';
      }
    }
  } catch (err) {
    alert('Không thể kết nối máy chủ, vui lòng thử lại sau.');
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Đặt hàng';
    }
    console.error(err);
  }
}

function renderOrderSuccess(orderId) {
  const overlay = ensureCartDrawer();
  const body = overlay.querySelector('.cart-drawer-body');
  const footer = overlay.querySelector('.cart-drawer-footer');

  body.innerHTML = `
    <div class="order-success">
      <div class="order-success-icon">✓</div>
      <h4>Đặt hàng thành công!</h4>
      <p>Mã đơn hàng của bạn là <strong>#${orderId}</strong>. Chúng tôi sẽ liên hệ để xác nhận sớm nhất.</p>
    </div>`;
  footer.innerHTML = `<button type="button" class="btn cart-continue-btn">Tiếp tục mua sắm</button>`;
  footer.querySelector('.cart-continue-btn').addEventListener('click', closeCartDrawer);
}

document.addEventListener('DOMContentLoaded', () => {
  ensureCartDrawer();
  updateCartBadge();
});
