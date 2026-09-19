// Component Library JS Bundle
// Auto-generated - do not edit directly

// ==== BUTTON ====
/**
 * Button Component Behavior
 * Handles loading states, keyboard interaction
 */

class ButtonComponent {
  constructor(element) {
    this.element = element;
    this.originalContent = null;
    this.bindEvents();
  }

  bindEvents() {
    // Keyboard activation for Enter/Space
    this.element.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        this.element.click();
      }
    });

    // Prevent form submit if button has type="button"
    if (this.element.type === 'button') {
      this.element.addEventListener('click', (e) => {
        if (this.element.disabled) e.preventDefault();
      });
    }
  }

  setLoading(loading) {
    if (loading) {
      if (!this.originalContent) {
        this.originalContent = this.element.innerHTML;
      }
      this.element.disabled = true;
      this.element.setAttribute('aria-busy', 'true');
      this.element.innerHTML = this.originalContent.replace(
        '<span class="btn-label">',
        '<span class="btn-spinner" aria-hidden="true">⟳</span><span class="btn-label">'
      );
    } else {
      this.element.disabled = false;
      this.element.setAttribute('aria-busy', 'false');
      if (this.originalContent) {
        this.element.innerHTML = this.originalContent;
        this.originalContent = null;
      }
    }
  }

  static init(selector = '.btn') {
    document.querySelectorAll(selector).forEach(el => new ButtonComponent(el));
  }
}

// Auto-init on DOM ready
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    ButtonComponent.init();
  });
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ButtonComponent;
}

// ==== MODAL ====
/**
 * Modal Component Behavior
 * Handles focus trapping, ESC key, backdrop click, scroll lock
 */

class ModalComponent {
  constructor(overlayElement) {
    this.overlay = overlayElement;
    this.content = overlayElement.querySelector('.modal-content');
    this.closeBtn = overlayElement.querySelector('.modal-close');
    this.previousActiveElement = null;
    this.focusableElements = [];
    this.bindEvents();
  }

  bindEvents() {
    // Close button
    if (this.closeBtn) {
      this.closeBtn.addEventListener('click', () => this.hide());
    }

    // Backdrop click
    this.overlay.addEventListener('click', (e) => {
      if (e.target === this.overlay) this.hide();
    });

    // ESC key
    this.keydownHandler = (e) => {
      if (e.key === 'Escape') this.hide();
      if (e.key === 'Tab') this.trapFocus(e);
    };
  }

  show() {
    this.previousActiveElement = document.activeElement;
    this.overlay.hidden = false;
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', this.keydownHandler);

    // Focus first focusable element
    setTimeout(() => this.focusFirstElement(), 0);
  }

  hide() {
    this.overlay.hidden = true;
    document.body.style.overflow = '';
    document.removeEventListener('keydown', this.keydownHandler);

    // Restore focus
    if (this.previousActiveElement) {
      this.previousActiveElement.focus();
    }
  }

  trapFocus(e) {
    this.updateFocusableElements();
    if (this.focusableElements.length === 0) return;

    const first = this.focusableElements[0];
    const last = this.focusableElements[this.focusableElements.length - 1];

    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  updateFocusableElements() {
    const selectors = [
      'button:not([disabled])',
      '[href]',
      'input:not([disabled])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      '[tabindex]:not([tabindex="-1"])'
    ];
    this.focusableElements = Array.from(
      this.content.querySelectorAll(selectors.join(','))
    ).filter(el => el.offsetParent !== null);
  }

  focusFirstElement() {
    this.updateFocusableElements();
    if (this.focusableElements.length > 0) {
      this.focusableElements[0].focus();
    }
  }

  static init(selector = '.modal-overlay') {
    document.querySelectorAll(selector).forEach(el => new ModalComponent(el));
  }

  static open(modalId) {
    const modal = document.getElementById(modalId);
    if (modal && modal._component) modal._component.show();
  }

  static close(modalId) {
    const modal = document.getElementById(modalId);
    if (modal && modal._component) modal._component.hide();
  }
}

// Auto-init and attach to DOM elements
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.modal-overlay').forEach(el => {
      el._component = new ModalComponent(el);
    });
  });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = ModalComponent;
}

// ==== DROPDOWN ====
/**
 * Dropdown Component Behavior
 * Handles keyboard navigation, focus management, positioning
 */

class DropdownComponent {
  constructor(dropdownElement) {
    this.dropdown = dropdownElement;
    this.trigger = dropdownElement.querySelector('[data-dropdown-trigger]');
    this.menu = dropdownElement.querySelector('.dropdown-menu');
    this.items = [];
    this.isOpen = false;
    this.bindEvents();
  }

  bindEvents() {
    if (!this.trigger || !this.menu) return;

    // Toggle on click
    this.trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggle();
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
      if (this.isOpen && !this.dropdown.contains(e.target)) {
        this.close();
      }
    });

    // Keyboard navigation
    this.trigger.addEventListener('keydown', (e) => this.handleTriggerKeydown(e));
    this.menu.addEventListener('keydown', (e) => this.handleMenuKeydown(e));

    // Close on Escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isOpen) {
        this.close();
        this.trigger.focus();
      }
    });
  }

  handleTriggerKeydown(e) {
    if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      this.open();
      this.focusFirstItem();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      this.open();
      this.focusLastItem();
    }
  }

  handleMenuKeydown(e) {
    const enabledItems = this.items.filter(item => !item.disabled);
    const currentIndex = enabledItems.findIndex(item => item === document.activeElement);

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const nextIndex = (currentIndex + 1) % enabledItems.length;
      enabledItems[nextIndex].focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prevIndex = (currentIndex - 1 + enabledItems.length) % enabledItems.length;
      enabledItems[prevIndex].focus();
    } else if (e.key === 'Home') {
      e.preventDefault();
      enabledItems[0].focus();
    } else if (e.key === 'End') {
      e.preventDefault();
      enabledItems[enabledItems.length - 1].focus();
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      document.activeElement.click();
      this.close();
      this.trigger.focus();
    } else if (e.key === 'Tab') {
      this.close();
    } else if (e.key.length === 1) {
      // Type-ahead search
      this.typeAhead(e.key);
    }
  }

  typeAhead(char) {
    const searchChar = char.toLowerCase();
    const enabledItems = this.items.filter(item => !item.disabled);
    const currentIndex = enabledItems.findIndex(item => item === document.activeElement);
    const startIndex = (currentIndex + 1) % enabledItems.length;

    for (let i = 0; i < enabledItems.length; i++) {
      const index = (startIndex + i) % enabledItems.length;
      const label = enabledItems[index].textContent.trim().toLowerCase();
      if (label.startsWith(searchChar)) {
        enabledItems[index].focus();
        break;
      }
    }
  }

  open() {
    if (this.isOpen) return;
    this.isOpen = true;
    this.menu.hidden = false;
    this.trigger.setAttribute('aria-expanded', 'true');
    this.updateItems();
    this.positionMenu();
  }

  close() {
    if (!this.isOpen) return;
    this.isOpen = false;
    this.menu.hidden = true;
    this.trigger.setAttribute('aria-expanded', 'false');
  }

  toggle() {
    if (this.isOpen) this.close();
    else this.open();
  }

  updateItems() {
    this.items = Array.from(this.menu.querySelectorAll('.dropdown-item:not(.dropdown-item-disabled)'));
  }

  focusFirstItem() {
    this.updateItems();
    if (this.items.length > 0) this.items[0].focus();
  }

  focusLastItem() {
    this.updateItems();
    if (this.items.length > 0) this.items[this.items.length - 1].focus();
  }

  positionMenu() {
    // Basic positioning - could be enhanced with Popper.js
    const rect = this.trigger.getBoundingClientRect();
    const menuRect = this.menu.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    // Horizontal flip
    if (rect.left + menuRect.width > viewportWidth) {
      this.menu.style.left = 'auto';
      this.menu.style.right = '0';
    }

    // Vertical flip
    if (rect.bottom + menuRect.height > viewportHeight && rect.top > menuRect.height) {
      this.menu.style.top = 'auto';
      this.menu.style.bottom = '100%';
      this.menu.style.marginTop = '0';
      this.menu.style.marginBottom = '4px';
    }
  }

  static init(selector = '.dropdown') {
    document.querySelectorAll(selector).forEach(el => new DropdownComponent(el));
  }
}

// Auto-init
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    DropdownComponent.init();
  });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = DropdownComponent;
}

// ==== TOOLTIP ====
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

// ==== TABS ====
/**
 * Tabs Component Behavior
 * Handles keyboard navigation, automatic indicator positioning
 */

class TabsComponent {
  constructor(tabsElement) {
    this.tabs = tabsElement;
    this.triggers = tabsElement.querySelectorAll('.tabs-trigger');
    this.panels = tabsElement.querySelectorAll('.tabs-panel');
    this.indicator = tabsElement.querySelector('.tabs-indicator');
    this.orientation = tabsElement.getAttribute('aria-orientation') || 'horizontal';
    this.bindEvents();
    this.updateIndicator();
  }

  bindEvents() {
    this.triggers.forEach((trigger, index) => {
      trigger.addEventListener('click', () => this.activate(index));
      trigger.addEventListener('keydown', (e) => this.handleKeydown(e, index));
    });
  }

  handleKeydown(e, index) {
    const total = this.triggers.length;
    let newIndex = index;

    if (this.orientation === 'horizontal') {
      if (e.key === 'ArrowRight') newIndex = (index + 1) % total;
      else if (e.key === 'ArrowLeft') newIndex = (index - 1 + total) % total;
      else if (e.key === 'Home') newIndex = 0;
      else if (e.key === 'End') newIndex = total - 1;
      else return;
    } else {
      if (e.key === 'ArrowDown') newIndex = (index + 1) % total;
      else if (e.key === 'ArrowUp') newIndex = (index - 1 + total) % total;
      else if (e.key === 'Home') newIndex = 0;
      else if (e.key === 'End') newIndex = total - 1;
      else return;
    }

    e.preventDefault();
    this.activate(newIndex);
    this.triggers[newIndex].focus();
  }

  activate(index) {
    this.triggers.forEach((trigger, i) => {
      const selected = i === index;
      trigger.setAttribute('aria-selected', selected);
      trigger.tabIndex = selected ? 0 : -1;
      if (selected) trigger.classList.add('tabs-trigger-active');
      else trigger.classList.remove('tabs-trigger-active');
    });

    this.panels.forEach((panel, i) => {
      const selected = i === index;
      if (selected) {
        panel.hidden = false;
        panel.classList.add('tabs-panel-active');
      } else {
        panel.hidden = true;
        panel.classList.remove('tabs-panel-active');
      }
    });

    this.updateIndicator();
  }

  updateIndicator() {
    if (!this.indicator) return;

    const activeTrigger = this.tabs.querySelector('.tabs-trigger[aria-selected="true"]');
    if (!activeTrigger) return;

    const listRect = this.tabs.querySelector('.tabs-list').getBoundingClientRect();
    const triggerRect = activeTrigger.getBoundingClientRect();

    if (this.orientation === 'vertical') {
      this.indicator.style.height = `${triggerRect.height}px`;
      this.indicator.style.width = '';
      this.indicator.style.top = `${triggerRect.top - listRect.top}px`;
      this.indicator.style.left = '';
      this.indicator.style.transform = 'none';
    } else {
      this.indicator.style.width = `${triggerRect.width}px`;
      this.indicator.style.height = '';
      this.indicator.style.left = `${triggerRect.left - listRect.left}px`;
      this.indicator.style.top = '';
      this.indicator.style.transform = 'none';
    }
  }

  static init(selector = '.tabs') {
    document.querySelectorAll(selector).forEach(el => new TabsComponent(el));
  }

  static activate(tabsId, index) {
    const tabs = document.getElementById(tabsId);
    if (tabs && tabs._component) tabs._component.activate(index);
  }
}

// Auto-init and attach
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.tabs').forEach(el => {
      el._component = new TabsComponent(el);
    });

    // Reposition indicator on resize
    let resizeTimeout;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(() => {
        document.querySelectorAll('.tabs').forEach(el => {
          if (el._component) el._component.updateIndicator();
        });
      }, 100);
    });
  });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = TabsComponent;
}

// ==== ACCORDION ====
/**
 * Accordion Component Behavior
 * Handles smooth height animations, keyboard navigation, multiple open support
 */

class AccordionComponent {
  constructor(accordionElement) {
    this.accordion = accordionElement;
    this.items = accordionElement.querySelectorAll('.accordion-item');
    this.allowMultiple = accordionElement.hasAttribute('data-multiple');
    this.triggers = [];
    this.contents = [];
    this.init();
  }

  init() {
    this.items.forEach((item, index) => {
      const trigger = item.querySelector('.accordion-trigger');
      const content = item.querySelector('.accordion-content');

      if (trigger && content) {
        this.triggers.push(trigger);
        this.contents.push(content);

        trigger.addEventListener('click', () => this.toggle(index));
        trigger.addEventListener('keydown', (e) => this.handleKeydown(e, index));

        // Set initial state
        const isOpen = trigger.getAttribute('aria-expanded') === 'true';
        if (isOpen) {
          this.openItem(index, false);
        }
      }
    });

    // Handle resize
    window.addEventListener('resize', () => this.updateOpenHeights());
  }

  handleKeydown(e, index) {
    const total = this.triggers.length;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      this.triggers[(index + 1) % total].focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      this.triggers[(index - 1 + total) % total].focus();
    } else if (e.key === 'Home') {
      e.preventDefault();
      this.triggers[0].focus();
    } else if (e.key === 'End') {
      e.preventDefault();
      this.triggers[total - 1].focus();
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      this.toggle(index);
    }
  }

  toggle(index) {
    const trigger = this.triggers[index];
    const isOpen = trigger.getAttribute('aria-expanded') === 'true';

    if (isOpen) {
      this.close(index);
    } else {
      this.open(index);
    }
  }

  open(index, animate = true) {
    if (!this.allowMultiple) {
      this.closeAll(index);
    }

    const trigger = this.triggers[index];
    const content = this.contents[index];

    trigger.setAttribute('aria-expanded', 'true');
    content.hidden = false;

    if (animate) {
      this.animateHeight(content, 'open');
    } else {
      content.style.maxHeight = content.scrollHeight + 'px';
      content.style.paddingTop = '';
      content.style.paddingBottom = '';
    }
  }

  close(index, animate = true) {
    const trigger = this.triggers[index];
    const content = this.contents[index];

    trigger.setAttribute('aria-expanded', 'false');

    if (animate) {
      this.animateHeight(content, 'close');
    } else {
      content.hidden = true;
      content.style.maxHeight = '0';
      content.style.paddingTop = '0';
      content.style.paddingBottom = '0';
    }
  }

  closeAll(exceptIndex = -1) {
    this.triggers.forEach((trigger, i) => {
      if (i !== exceptIndex && trigger.getAttribute('aria-expanded') === 'true') {
        this.close(i);
      }
    });
  }

  animateHeight(content, direction) {
    if (direction === 'open') {
      content.hidden = false;
      content.style.maxHeight = '0';
      content.style.paddingTop = '0';
      content.style.paddingBottom = '0';

      // Force reflow
      content.offsetHeight;

      const targetHeight = content.scrollHeight;
      content.style.maxHeight = targetHeight + 'px';
      content.style.paddingTop = '';
      content.style.paddingBottom = '';

      content.addEventListener('transitionend', () => {
        if (content.style.maxHeight !== '0px') {
          content.style.maxHeight = 'none';
        }
      }, { once: true });
    } else {
      content.style.maxHeight = content.scrollHeight + 'px';
      content.offsetHeight;
      content.style.maxHeight = '0';
      content.style.paddingTop = '0';
      content.style.paddingBottom = '0';

      content.addEventListener('transitionend', () => {
        if (content.style.maxHeight === '0px') {
          content.hidden = true;
          content.style.maxHeight = '';
          content.style.paddingTop = '';
          content.style.paddingBottom = '';
        }
      }, { once: true });
    }
  }

  updateOpenHeights() {
    this.contents.forEach((content, i) => {
      if (!content.hidden && content.style.maxHeight !== 'none') {
        content.style.maxHeight = content.scrollHeight + 'px';
      }
    });
  }

  static init(selector = '.accordion') {
    document.querySelectorAll(selector).forEach(el => new AccordionComponent(el));
  }
}

// Auto-init
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    AccordionComponent.init();
  });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = AccordionComponent;
}

// Auto-initialize all components
document.addEventListener('DOMContentLoaded', () => {
  if (typeof ButtonComponent !== 'undefined') ButtonComponent.init();
  if (typeof ModalComponent !== 'undefined') ModalComponent.init();
  if (typeof DropdownComponent !== 'undefined') DropdownComponent.init();
  if (typeof TooltipComponent !== 'undefined') TooltipComponent.init();
  if (typeof TabsComponent !== 'undefined') TabsComponent.init();
  if (typeof AccordionComponent !== 'undefined') AccordionComponent.init();
});