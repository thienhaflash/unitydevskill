/* Reusable FlowDrawer component embedded by every generated flow page. */
const FlowDrawer = (() => {
  const escapeText = (value) => {
    const element = document.createElement('div');
    element.textContent = value ?? '';
    return element.innerHTML;
  };

  function mount(host) {
    host.innerHTML = '<aside id="drawer" class="flow-drawer-panel" data-component="flow-drawer"><button class="drawer-toggle" data-action="collapse" aria-label="Collapse graph list">‹</button><nav class="flow-list" data-flow-list></nav></aside>';
    const root = host.querySelector('[data-component="flow-drawer"]');
    const tooltip = document.createElement('div');
    tooltip.className = 'flow-tooltip';
    tooltip.setAttribute('role', 'tooltip');
    document.body.appendChild(tooltip);
    root._flowTooltip = tooltip;
    if (!root._tooltipFocusBound) {
      root._tooltipFocusBound = true;
      root.addEventListener('focusin', (e) => {
        const button = e.target.closest?.('[data-flow],[data-block]');
        if (button) showTooltipForButton(root, button);
      });
      root.addEventListener('focusout', (e) => {
        if (!root.contains(e.relatedTarget)) hideTooltipForRoot(root);
      });
    }
    return root;
  }

  function hideTooltipForRoot(root) {
    root._flowTooltip?.classList.remove('visible');
  }

  function showTooltipForButton(root, button) {
    const tooltip = root._flowTooltip;
    if (!tooltip || !button) return;
    if (!root.classList.contains('collapsed')) return;
    const text = button.dataset.tooltip || button.getAttribute('aria-label') || '';
    if (!text) return;
    tooltip.textContent = text;
    tooltip.classList.add('visible');
    const rect = button.getBoundingClientRect();
    tooltip.style.left = `${rect.right + 10}px`;
    tooltip.style.top = `${rect.top + (rect.height - tooltip.offsetHeight) / 2}px`;
  }

  function update(root, flows, active, collapsed, onSelect, onCollapse, options = {}) {
    root.classList.toggle('collapsed', collapsed);
    const toggle = root.querySelector('[data-action="collapse"]');
    toggle.textContent = collapsed ? '›' : '‹';
    toggle.setAttribute('aria-label', collapsed ? 'Show graph list' : 'Collapse graph list');
    toggle.onclick = onCollapse;

    const list = root.querySelector('[data-flow-list]');
    const tooltip = root._flowTooltip;
    const hideTooltip = () => hideTooltipForRoot(root);
    const showTooltip = (button, text) => {
      if (text) button.dataset.tooltip = text;
      showTooltipForButton(root, button);
    };
    list.innerHTML = flows.map((flow) => {
      const number = flow.title.match(/^\d+/)?.[0] || '';
      const title = flow.title.replace(/^\d+\s*·?\s*/, '');
      const label = `${number} ${title}`.trim();
      return `<button class="flow-button ${flow.id === active ? 'active' : ''}" data-flow="${escapeText(flow.id)}" data-tooltip="${escapeText(label)}" aria-label="${escapeText(label)}"><span class="flow-number">${escapeText(number)}</span><span class="flow-title">${escapeText(title)}</span></button>`;
    }).join('');
    const blocks = options.blocks || [];
    if (blocks.length) {
      const items = blocks.map((block) => {
        const label = `${block.title} · sub-graph`;
        const activeClass = block.id === options.activeBlock ? 'active' : '';
        return `<button class="block-button ${activeClass}" data-block="${escapeText(block.id)}" data-tooltip="${escapeText(label)}" aria-label="${escapeText(label)}"><span class="block-mark">⊞</span><span class="block-title">${escapeText(block.title)}</span></button>`;
      }).join('');
      const labelHtml = collapsed ? '' : '<div class="block-list-label">Sub-graphs</div>';
      list.insertAdjacentHTML('beforeend', `<div class="block-list">${labelHtml}${items}</div>`);
    }

    const navItems = () => [...list.querySelectorAll('[data-flow],[data-block]')];
    const syncRovingTab = () => {
      const items = navItems();
      items.forEach((item) => {
        item.tabIndex = -1;
      });
      const activeBtn =
        list.querySelector(`[data-flow="${active}"]`) ||
        (options.activeBlock ? list.querySelector(`[data-block="${options.activeBlock}"]`) : null) ||
        items[0];
      if (activeBtn) activeBtn.tabIndex = 0;
    };
    syncRovingTab();

    list.querySelectorAll('[data-flow]').forEach((button) => {
      button.onclick = () => onSelect(button.dataset.flow);
      button.onpointerenter = () => showTooltip(button, button.dataset.tooltip || '');
      button.onpointermove = () => showTooltip(button, button.dataset.tooltip || '');
      button.onpointerleave = hideTooltip;
    });
    list.querySelectorAll('[data-block]').forEach((button) => {
      button.onclick = () => options.onSelectBlock?.(button.dataset.block);
      button.onpointerenter = () => showTooltip(button, button.dataset.tooltip || '');
      button.onpointermove = () => showTooltip(button, button.dataset.tooltip || '');
      button.onpointerleave = hideTooltip;
    });

    root._flowDrawerSelect = {
      activeFlowId: active,
      activeBlockId: options.activeBlock || null,
      onFlow: onSelect,
      onBlock: (id) => options.onSelectBlock?.(id),
    };

    const focusedNav = list.querySelector('[data-flow]:focus,[data-block]:focus');
    if (focusedNav) showTooltipForButton(root, focusedNav);
    else hideTooltip();
  }

  function stepFlowSelection(root, delta) {
    const list = root.querySelector('[data-flow-list]');
    if (!list) return;
    const items = [...list.querySelectorAll('[data-flow],[data-block]')];
    if (!items.length) return;
    const select = root._flowDrawerSelect;
    let idx = items.indexOf(document.activeElement);
    if (idx < 0) idx = items.findIndex((el) => el.classList.contains('active'));
    if (idx < 0) idx = 0;
    const nextIdx = Math.max(0, Math.min(items.length - 1, idx + delta));
    const next = items[nextIdx];
    items.forEach((item) => {
      item.tabIndex = item === next ? 0 : -1;
    });
    next.focus({ preventScroll: true });
    if (!select) return;
    if (next.dataset.flow) {
      if (next.dataset.flow !== select.activeFlowId || select.activeBlockId) select.onFlow(next.dataset.flow);
      return;
    }
    if (next.dataset.block && next.dataset.block !== select.activeBlockId) select.onBlock(next.dataset.block);
  }

  function focusActiveItem(root) {
    const list = root.querySelector('[data-flow-list]');
    const btn =
      list?.querySelector('.flow-button.active, .block-button.active') ||
      list?.querySelector('[data-flow],[data-block]');
    if (!btn) return;
    list.querySelectorAll('[data-flow],[data-block]').forEach((item) => {
      item.tabIndex = item === btn ? 0 : -1;
    });
    btn.focus({ preventScroll: true });
    showTooltipForButton(root, btn);
  }

  return { mount, update, focusActiveItem, stepFlowSelection };
})();
