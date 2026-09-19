/**
 * Tooltip Component Behavior
 * Handles hover, focus, click triggers with proper positioning
 */

class TooltipComponent {
  constructor(triggerElement, options = {}) {
    this.trigger = triggerElement;
    this.options = {
      content: options.content || triggerElement.getAttribute('data-tooltip') || triggerElement.title,
      placement: options.placement || 'top',
      trigger: options.trigger || 'hover',
      delay: options.delay || 200,
      ...options
    };
    this.tooltip = null;
    this.showTimeout = null;
    this.hideTimeout = null;
    this.init();
  }

  init() {
    // Remove native title to prevent double tooltips
    if (this.trigger.hasAttribute('title')) {
      this.trigger.removeAttribute('title');
    }

    this.createTooltip();
    this.bindEvents();
  }

  createTooltip() {
    this.tooltip = document.createElement('div');
    this.tooltip.className = 'tooltip';
    this.tooltip.id = `tooltip-${Math.random().toString(36).substr(2, 9)}`;
    this.tooltip.setAttribute('role', 'tooltip');
    this.tooltip.setAttribute('data-placement', this.options.placement);
    this.tooltip.hidden = true;
    this.tooltip.innerHTML = `
      <div class="tooltip-arrow" aria-hidden="true"></div>
      <div class="tooltip-content">${this.options.content}</div>
    `;
    document.body.appendChild(this.tooltip);

    // Associate with trigger for accessibility
    this.trigger.setAttribute('aria-describedby', this.tooltip.id);
  }

  bindEvents() {
    const { trigger } = this.options;

    if (trigger === 'hover' || trigger === 'hover-focus') {
      this.trigger.addEventListener('mouseenter', () => this.show());
      this.trigger.addEventListener('mouseleave', () => this.hide());
    }

    if (trigger === 'focus' || trigger === 'hover-focus') {
      this.trigger.addEventListener('focus', () => this.show());
      this.trigger.addEventListener('blur', () => this.hide());
    }

    if (trigger === 'click') {
      this.trigger.addEventListener('click', (e) => {
        e.preventDefault();
        this.toggle();
      });

      document.addEventListener('click', (e) => {
        if (this.isVisible && !this.trigger.contains(e.target) && !this.tooltip.contains(e.target)) {
          this.hide();
        }
      });
    }

    // Keyboard
    this.trigger.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isVisible) {
        this.hide();
      }
    });

    // Cleanup on destroy
    this.trigger.addEventListener('remove', () => this.destroy(), { once: true });
  }

  show() {
    if (this.showTimeout) clearTimeout(this.showTimeout);
    if (this.hideTimeout) clearTimeout(this.hideTimeout);

    this.showTimeout = setTimeout(() => {
      this.position();
      this.tooltip.hidden = false;
      this.isVisible = true;
    }, this.options.delay);
  }

  hide() {
    if (this.showTimeout) clearTimeout(this.showTimeout);
    if (this.hideTimeout) clearTimeout(this.hideTimeout);

    this.hideTimeout = setTimeout(() => {
      this.tooltip.hidden = true;
      this.isVisible = false;
    }, this.options.delay);
  }

  toggle() {
    if (this.isVisible) this.hide();
    else this.show();
  }

  position() {
    if (!this.tooltip || !this.trigger) return;

    const triggerRect = this.trigger.getBoundingClientRect();
    const tooltipRect = this.tooltip.getBoundingClientRect();
    const { placement } = this.options;
    const gap = 8;

    let top = 0, left = 0;

    switch (placement) {
      case 'top':
        top = triggerRect.top - tooltipRect.height - gap;
        left = triggerRect.left + (triggerRect.width - tooltipRect.width) / 2;
        break;
      case 'bottom':
        top = triggerRect.bottom + gap;
        left = triggerRect.left + (triggerRect.width - tooltipRect.width) / 2;
        break;
      case 'left':
        top = triggerRect.top + (triggerRect.height - tooltipRect.height) / 2;
        left = triggerRect.left - tooltipRect.width - gap;
        break;
      case 'right':
        top = triggerRect.top + (triggerRect.height - tooltipRect.height) / 2;
        left = triggerRect.right + gap;
        break;
    }

    // Keep in viewport
    const viewportPadding = 8;
    if (left < viewportPadding) left = viewportPadding;
    if (left + tooltipRect.width > window.innerWidth - viewportPadding) {
      left = window.innerWidth - tooltipRect.width - viewportPadding;
    }
    if (top < viewportPadding) top = viewportPadding;
    if (top + tooltipRect.height > window.innerHeight - viewportPadding) {
      top = window.innerHeight - tooltipRect.height - viewportPadding;
    }

    this.tooltip.style.top = `${top + window.scrollY}px`;
    this.tooltip.style.left = `${left + window.scrollX}px`;
  }

  updateContent(content) {
    this.options.content = content;
    const contentEl = this.tooltip?.querySelector('.tooltip-content');
    if (contentEl) contentEl.innerHTML = content;
  }

  destroy() {
    if (this.showTimeout) clearTimeout(this.showTimeout);
    if (this.hideTimeout) clearTimeout(this.hideTimeout);
    if (this.tooltip) {
      this.tooltip.remove();
      this.tooltip = null;
    }
    this.trigger.removeAttribute('aria-describedby');
  }

  static init(selector = '[data-tooltip]', options = {}) {
    document.querySelectorAll(selector).forEach(el => {
      if (!el._tooltip) {
        el._tooltip = new TooltipComponent(el, options);
      }
    });
  }
}

// Auto-init
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    TooltipComponent.init();
  });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = TooltipComponent;
}